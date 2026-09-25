"""Display-oriented Frequency Track viewport policy for the Web editor.

The core FrequencyTrackStore keeps every derived track.  This module changes only
how many tracks are returned to one Web viewport: long/strong tracks receive
higher display priority, zoomed-out views get a tighter point budget, and LOD
keeps or drops whole tracks instead of producing a wall of equally prominent
segments.  No track data is deleted from the store and transcription still uses
full-resolution data.
"""

from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from core.frequency_tracks import (
    FrequencyTrackRegion,
    FrequencyTrackStore,
    _PACKED_TRACK_POINT_DTYPE,
)


_ORIGINAL_QUERY_REGION = FrequencyTrackStore.query_region


def display_priority(duration: float, average_magnitude: float, maximum_magnitude: float) -> float:
    """Return a deterministic display-only priority in the 0..1 range."""
    avg = max(0.0, min(1.0, float(average_magnitude)))
    peak = max(0.0, min(1.0, float(maximum_magnitude)))
    strength = 0.7 * math.sqrt(avg) + 0.3 * math.sqrt(peak)
    duration_weight = max(0.15, min(1.0, float(duration) / 0.30))
    return max(0.0, min(1.0, strength * duration_weight))


def _display_point_limit(requested_limit: int, span_seconds: float) -> int:
    """Tighten the existing backend point budget as the viewport zooms out."""
    requested = max(256, int(requested_limit))
    if span_seconds <= 8.0:
        return requested
    if span_seconds <= 30.0:
        return max(2_500, min(requested, int(requested * 0.50)))
    return max(2_000, min(requested, int(requested / 3.0)))


def _sample_run(run: np.ndarray, step: int) -> np.ndarray:
    if step <= 1 or run.size <= 2:
        return run
    chosen = run[::step]
    if chosen[-1] != run[-1]:
        chosen = np.concatenate((chosen, run[-1:]))
    return chosen


def readable_frequency_track_region(
    store: Any,
    start_time: float,
    end_time: float,
    minimum_midi: float,
    maximum_midi: float,
    *,
    max_points: int = 30_000,
) -> FrequencyTrackRegion:
    """Return a readability-first viewport without mutating the Track Store.

    Up to 8 seconds all visible tracks are retained and only point decimation is
    used when necessary.  Wider views apply whole-track LOD using duration and
    magnitude.  This keeps the view deterministic while avoiding the dense
    "fence" effect from thousands of similarly prominent short tracks.
    """
    started = time.perf_counter()
    start = max(0.0, float(start_time))
    end = max(start, float(end_time))
    midi_min = max(0.0, min(127.0, float(minimum_midi)))
    midi_max = max(midi_min, min(127.0, float(maximum_midi)))
    requested_limit = max(256, min(65_000, int(max_points)))
    display_limit = _display_point_limit(requested_limit, end - start)

    if end <= start or midi_max <= midi_min or not int(store.point_count):
        return FrequencyTrackRegion(b"", 0, 0, 1.0, time.perf_counter() - started)

    visible_tracks = np.flatnonzero(
        (store.track_start_times <= end) & (store.track_end_times >= start)
    )
    groups: list[tuple[int, list[np.ndarray], int, float]] = []
    raw_points = 0

    for track_id_value in visible_tracks:
        track_id = int(track_id_value)
        lo = int(store.track_offsets[track_id])
        hi = int(store.track_offsets[track_id + 1])
        times = store.point_times[lo:hi]
        left = lo + int(np.searchsorted(times, start, side="left"))
        right = lo + int(np.searchsorted(times, end, side="right"))
        if right <= left:
            continue

        local = np.flatnonzero(
            (store.point_midi[left:right] >= midi_min)
            & (store.point_midi[left:right] <= midi_max)
        )
        if not local.size:
            continue

        absolute = local.astype(np.int64, copy=False) + left
        split_at = np.flatnonzero(np.diff(absolute) > 1) + 1
        runs = [run for run in np.split(absolute, split_at) if run.size]
        if not runs:
            continue

        point_count = sum(int(run.size) for run in runs)
        duration = float(store.track_end_times[track_id] - store.track_start_times[track_id])
        priority = display_priority(
            duration,
            float(store.track_average_magnitudes[track_id]),
            float(store.track_max_magnitudes[track_id]),
        )
        groups.append((track_id, runs, point_count, priority))
        raw_points += point_count

    if not groups:
        return FrequencyTrackRegion(b"", 0, 0, 1.0, time.perf_counter() - started)

    # Preserve the core query's temporal decimation behavior first.  For wider
    # views the second stage below spends the tighter display budget by whole
    # track so low-priority fragments do not pepper the viewport.
    base_stride = max(1, int(math.ceil(raw_points / requested_limit)))
    sampled_groups: list[tuple[int, list[np.ndarray], int, float]] = []
    for track_id, runs, _point_count, priority in groups:
        sampled_runs = [_sample_run(run, base_stride) for run in runs]
        sampled_count = sum(int(run.size) for run in sampled_runs)
        sampled_groups.append((track_id, sampled_runs, sampled_count, priority))

    if end - start <= 8.0:
        # Zoomed in: keep every track.  If endpoint preservation pushed us a
        # little over budget, increase the stride globally rather than dropping
        # weak tracks.
        stride = base_stride
        kept = sampled_groups
        total = sum(item[2] for item in kept)
        while total > display_limit and stride < raw_points:
            stride = max(stride + 1, int(math.ceil(stride * 1.25)))
            kept = []
            for track_id, runs, _count, priority in groups:
                sampled_runs = [_sample_run(run, stride) for run in runs]
                count = sum(int(run.size) for run in sampled_runs)
                kept.append((track_id, sampled_runs, count, priority))
            total = sum(item[2] for item in kept)
    else:
        ranked = sorted(sampled_groups, key=lambda item: (-item[3], item[0]))
        kept = []
        remaining = display_limit
        for item in ranked:
            count = item[2]
            if count <= remaining or not kept:
                kept.append(item)
                remaining -= min(remaining, count)
            if remaining <= 0:
                break

    kept.sort(key=lambda item: item[0])
    returned = sum(item[2] for item in kept)
    if returned <= 0:
        return FrequencyTrackRegion(b"", 0, 0, 1.0, time.perf_counter() - started)

    packed = np.empty(returned, dtype=_PACKED_TRACK_POINT_DTYPE)
    cursor = 0
    returned_track_ids: set[int] = set()
    for track_id, runs, _count, _priority in kept:
        for run in runs:
            count = int(run.size)
            if not count:
                continue
            target = packed[cursor : cursor + count]
            target["track"] = track_id
            target["time"] = store.point_times[run]
            target["midi"] = store.point_midi[run]
            target["magnitude"] = np.clip(
                np.rint(store.point_magnitudes[run] * 255.0), 1, 255
            ).astype(np.uint8)
            target["duration"] = float(
                store.track_end_times[track_id] - store.track_start_times[track_id]
            )
            target["flags"] = 0
            target["flags"][0] = 1
            cursor += count
        returned_track_ids.add(track_id)

    return FrequencyTrackRegion(
        packed_points=packed[:cursor].tobytes(order="C"),
        returned_tracks=len(returned_track_ids),
        returned_points=cursor,
        decimation_level=max(1.0, raw_points / max(1, cursor)),
        query_seconds=time.perf_counter() - started,
    )


def install_frequency_track_display_policy() -> None:
    """Install the Web-only readability policy once."""
    if getattr(FrequencyTrackStore, "_web_readability_policy_installed", False):
        return
    FrequencyTrackStore.query_region = readable_frequency_track_region  # type: ignore[method-assign]
    FrequencyTrackStore._web_readability_policy_installed = True  # type: ignore[attr-defined]

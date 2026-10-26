"""Compact frequency-track derivation for the Vorbis Direct spectrum store.

Tracks connect nearby local spectrum maxima across time.  They are display and
inspection data only: no fundamental estimation, harmonic suppression, noise
classification, or conversion to editor Notes is performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time

import numpy as np

from core.vorbis_spectrum_store import VorbisSpectrumStore, _readonly


TRACK_STORE_VERSION = 1
MAX_TRACK_VIEWPORT_POINTS = 30_000
_PACKED_TRACK_POINT_DTYPE = np.dtype(
    [
        ("track", "<u4"),
        ("time", "<f4"),
        ("midi", "<f4"),
        ("magnitude", "u1"),
        ("duration", "<f4"),
        ("flags", "u1"),
    ],
    align=False,
)


@dataclass(frozen=True)
class FrequencyTrackSettings:
    base_tolerance_cents: float = 75.0
    maximum_gap_seconds: float = 0.075
    maximum_tolerance_cents: float = 300.0
    resolution_tolerance_scale: float = 1.1


@dataclass(frozen=True)
class FrequencyTrackStats:
    total_tracks: int
    total_points: int
    average_duration: float
    longest_duration: float
    generation_seconds: float
    store_memory_bytes: int
    base_tolerance_cents: float
    maximum_gap_seconds: float
    maximum_tolerance_cents: float

    def to_dict(self) -> dict[str, int | float | str]:
        return {
            "totalTrackCount": self.total_tracks,
            "totalTrackPoints": self.total_points,
            "averageTrackDuration": self.average_duration,
            "longestTrackDuration": self.longest_duration,
            "trackGenerationSeconds": self.generation_seconds,
            "trackStoreMemoryBytes": self.store_memory_bytes,
            "trackBaseToleranceCents": self.base_tolerance_cents,
            "trackMaximumGapMs": self.maximum_gap_seconds * 1000.0,
            "trackMaximumToleranceCents": self.maximum_tolerance_cents,
            "trackStoreVersion": TRACK_STORE_VERSION,
        }


@dataclass(frozen=True)
class FrequencyTrackRegion:
    packed_points: bytes
    returned_tracks: int
    returned_points: int
    decimation_level: float
    query_seconds: float


@dataclass(frozen=True)
class FrequencyTrackStore:
    """Track points grouped contiguously by implicit integer track id."""

    point_times: np.ndarray
    point_midi: np.ndarray
    point_magnitudes: np.ndarray
    track_offsets: np.ndarray
    track_start_times: np.ndarray
    track_end_times: np.ndarray
    track_average_magnitudes: np.ndarray
    track_max_magnitudes: np.ndarray
    source_fingerprint: tuple[object, ...]
    settings: FrequencyTrackSettings
    stats: FrequencyTrackStats

    @property
    def track_count(self) -> int:
        return max(0, int(self.track_offsets.size) - 1)

    @property
    def point_count(self) -> int:
        return int(self.point_times.size)

    @property
    def memory_bytes(self) -> int:
        return int(
            self.point_times.nbytes
            + self.point_midi.nbytes
            + self.point_magnitudes.nbytes
            + self.track_offsets.nbytes
            + self.track_start_times.nbytes
            + self.track_end_times.nbytes
            + self.track_average_magnitudes.nbytes
            + self.track_max_magnitudes.nbytes
        )

    def query_region(
        self,
        start_time: float,
        end_time: float,
        minimum_midi: float,
        maximum_midi: float,
        *,
        max_points: int = MAX_TRACK_VIEWPORT_POINTS,
    ) -> FrequencyTrackRegion:
        """Return bounded, decimated track segments inside one viewport."""
        started = time.perf_counter()
        start = max(0.0, float(start_time))
        end = max(start, float(end_time))
        midi_min = max(0.0, min(127.0, float(minimum_midi)))
        midi_max = max(midi_min, min(127.0, float(maximum_midi)))
        point_limit = max(256, min(65_000, int(max_points)))
        if end <= start or midi_max <= midi_min or not self.point_count:
            return FrequencyTrackRegion(b"", 0, 0, 1.0, time.perf_counter() - started)

        visible_tracks = np.flatnonzero(
            (self.track_start_times <= end) & (self.track_end_times >= start)
        )
        segments: list[tuple[int, np.ndarray, float]] = []
        raw_points = 0
        for track_id_value in visible_tracks:
            track_id = int(track_id_value)
            lo = int(self.track_offsets[track_id])
            hi = int(self.track_offsets[track_id + 1])
            times = self.point_times[lo:hi]
            left = lo + int(np.searchsorted(times, start, side="left"))
            right = lo + int(np.searchsorted(times, end, side="right"))
            if right <= left:
                continue
            local = np.flatnonzero(
                (self.point_midi[left:right] >= midi_min)
                & (self.point_midi[left:right] <= midi_max)
            )
            if not local.size:
                continue
            absolute = local.astype(np.int64, copy=False) + left
            split_at = np.flatnonzero(np.diff(absolute) > 1) + 1
            duration = float(self.track_end_times[track_id] - self.track_start_times[track_id])
            score = duration * (0.25 + float(self.track_max_magnitudes[track_id]))
            for run in np.split(absolute, split_at):
                if run.size:
                    segments.append((track_id, run, score))
                    raw_points += int(run.size)

        if not segments:
            return FrequencyTrackRegion(b"", 0, 0, 1.0, time.perf_counter() - started)

        stride = max(1, int(math.ceil(raw_points / point_limit)))

        def sample(run: np.ndarray, step: int) -> np.ndarray:
            if step <= 1 or run.size <= 2:
                return run
            chosen = run[::step]
            if chosen[-1] != run[-1]:
                chosen = np.concatenate((chosen, run[-1:]))
            return chosen

        sampled = [(track_id, sample(run, stride), score) for track_id, run, score in segments]
        while sum(int(run.size) for _track, run, _score in sampled) > point_limit and stride < raw_points:
            stride = max(stride + 1, int(math.ceil(stride * 1.25)))
            sampled = [(track_id, sample(run, stride), score) for track_id, run, score in segments]

        sampled.sort(key=lambda item: item[2], reverse=True)
        kept: list[tuple[int, np.ndarray, float]] = []
        remaining = point_limit
        for item in sampled:
            size = int(item[1].size)
            if size <= remaining:
                kept.append(item)
                remaining -= size
            if remaining <= 0:
                break
        kept.sort(key=lambda item: (item[0], int(item[1][0])))
        returned = sum(int(run.size) for _track, run, _score in kept)
        packed = np.empty(returned, dtype=_PACKED_TRACK_POINT_DTYPE)
        cursor = 0
        returned_track_ids: set[int] = set()
        for track_id, indices, _score in kept:
            count = int(indices.size)
            target = packed[cursor : cursor + count]
            target["track"] = track_id
            target["time"] = self.point_times[indices]
            target["midi"] = self.point_midi[indices]
            target["magnitude"] = np.clip(
                np.rint(self.point_magnitudes[indices] * 255.0), 1, 255
            ).astype(np.uint8)
            target["duration"] = float(
                self.track_end_times[track_id] - self.track_start_times[track_id]
            )
            target["flags"] = 0
            target["flags"][0] = 1
            cursor += count
            returned_track_ids.add(track_id)

        return FrequencyTrackRegion(
            packed_points=packed.tobytes(order="C"),
            returned_tracks=len(returned_track_ids),
            returned_points=returned,
            decimation_level=max(1.0, raw_points / max(1, returned)),
            query_seconds=time.perf_counter() - started,
        )


@dataclass
class _ActiveTrack:
    last_time: float
    last_midi: float
    last_magnitude: float
    tolerance_cents: float


def _validate_settings(settings: FrequencyTrackSettings) -> None:
    if settings.base_tolerance_cents <= 0.0:
        raise ValueError("base_tolerance_cents must be positive")
    if settings.maximum_gap_seconds < 0.0:
        raise ValueError("maximum_gap_seconds must not be negative")
    if settings.maximum_tolerance_cents < settings.base_tolerance_cents:
        raise ValueError("maximum_tolerance_cents must cover the base tolerance")
    if settings.resolution_tolerance_scale <= 0.0:
        raise ValueError("resolution_tolerance_scale must be positive")


def _plane_coordinates(
    block_size: int,
    sample_rate: int,
    settings: FrequencyTrackSettings,
) -> tuple[np.ndarray, np.ndarray]:
    frequencies = (
        np.arange(block_size // 2, dtype=np.float64) + 0.5
    ) * sample_rate / block_size
    midi = 69.0 + 12.0 * np.log2(frequencies / 440.0)
    upper = frequencies + sample_rate / block_size
    resolution = 1200.0 * np.log2(upper / frequencies)
    tolerance = np.maximum(
        settings.base_tolerance_cents,
        np.minimum(
            settings.maximum_tolerance_cents,
            resolution * settings.resolution_tolerance_scale,
        ),
    )
    return midi, tolerance


def _local_maxima(magnitudes: np.ndarray) -> np.ndarray:
    if not magnitudes.size:
        return np.empty(0, dtype=np.int64)
    if magnitudes.size == 1:
        return np.array([0], dtype=np.int64) if magnitudes[0] > 0.0 else np.empty(0, dtype=np.int64)
    keep = np.zeros(magnitudes.size, dtype=bool)
    keep[0] = magnitudes[0] > magnitudes[1]
    keep[-1] = magnitudes[-1] >= magnitudes[-2] and magnitudes[-1] > 0.0
    if magnitudes.size > 2:
        keep[1:-1] = (
            (magnitudes[1:-1] >= magnitudes[:-2])
            & (magnitudes[1:-1] > magnitudes[2:])
            & (magnitudes[1:-1] > 0.0)
        )
    return np.flatnonzero(keep)


def build_frequency_track_store(
    spectrum: VorbisSpectrumStore,
    *,
    settings: FrequencyTrackSettings | None = None,
) -> FrequencyTrackStore:
    """Build one reusable greedy track index from a compact spectrum store."""
    options = settings or FrequencyTrackSettings()
    _validate_settings(options)
    started = time.perf_counter()
    block_count = int(spectrum.center_times.size)
    plane_for_block = np.empty(block_count, dtype=np.int16)
    row_for_block = np.empty(block_count, dtype=np.int32)
    coordinates: list[tuple[np.ndarray, np.ndarray]] = []
    for plane_index, plane in enumerate(spectrum.planes):
        plane_for_block[plane.block_indices] = plane_index
        row_for_block[plane.block_indices] = np.arange(plane.block_indices.size, dtype=np.int32)
        coordinates.append(
            _plane_coordinates(plane.block_size, spectrum.stream_info.sample_rate, options)
        )

    time_chunks: list[np.ndarray] = []
    midi_chunks: list[np.ndarray] = []
    magnitude_chunks: list[np.ndarray] = []
    track_chunks: list[np.ndarray] = []
    active: dict[int, _ActiveTrack] = {}
    next_track_id = 0

    for block_index in range(block_count):
        frame_time = float(spectrum.center_times[block_index])
        expired = [
            track_id for track_id, track in active.items()
            if frame_time - track.last_time > options.maximum_gap_seconds
        ]
        for track_id in expired:
            del active[track_id]

        plane_index = int(plane_for_block[block_index])
        plane = spectrum.planes[plane_index]
        row = int(row_for_block[block_index])
        magnitudes = plane.magnitudes[row]
        maximum = float(plane.block_maxima[row])
        candidates = _local_maxima(magnitudes)
        if not candidates.size or maximum <= np.finfo(np.float32).tiny:
            continue
        frame_midi, frame_tolerance = coordinates[plane_index]
        valid = (
            (frame_midi[candidates] >= 0.0)
            & (frame_midi[candidates] <= 127.0)
            & np.isfinite(frame_midi[candidates])
        )
        candidates = candidates[valid]
        if not candidates.size:
            continue
        candidate_midi = frame_midi[candidates].astype(np.float32, copy=False)
        candidate_magnitude = (magnitudes[candidates] / maximum).astype(np.float32, copy=False)
        candidate_tolerance = frame_tolerance[candidates].astype(np.float32, copy=False)
        assignments = np.full(candidates.size, -1, dtype=np.int64)

        edges: list[tuple[float, float, int, int]] = []
        if active:
            for track_id, track in active.items():
                left = int(np.searchsorted(candidate_midi, track.last_midi - options.maximum_tolerance_cents / 100.0, side="left"))
                right = int(np.searchsorted(candidate_midi, track.last_midi + options.maximum_tolerance_cents / 100.0, side="right"))
                for candidate_index in range(left, right):
                    distance = abs(float(candidate_midi[candidate_index]) - track.last_midi) * 100.0
                    tolerance = max(track.tolerance_cents, float(candidate_tolerance[candidate_index]))
                    if distance <= tolerance:
                        magnitude_delta = abs(float(candidate_magnitude[candidate_index]) - track.last_magnitude)
                        edges.append((distance, magnitude_delta, track_id, candidate_index))
            edges.sort()

        used_tracks: set[int] = set()
        used_candidates: set[int] = set()
        for _distance, _magnitude_delta, track_id, candidate_index in edges:
            if track_id in used_tracks or candidate_index in used_candidates:
                continue
            assignments[candidate_index] = track_id
            used_tracks.add(track_id)
            used_candidates.add(candidate_index)

        for candidate_index in range(candidates.size):
            track_id = int(assignments[candidate_index])
            if track_id < 0:
                track_id = next_track_id
                next_track_id += 1
                assignments[candidate_index] = track_id
            active[track_id] = _ActiveTrack(
                last_time=frame_time,
                last_midi=float(candidate_midi[candidate_index]),
                last_magnitude=float(candidate_magnitude[candidate_index]),
                tolerance_cents=float(candidate_tolerance[candidate_index]),
            )

        time_chunks.append(np.full(candidates.size, frame_time, dtype=np.float32))
        midi_chunks.append(candidate_midi.copy())
        magnitude_chunks.append(candidate_magnitude.copy())
        track_chunks.append(assignments.astype(np.uint32, copy=False))

    if time_chunks:
        point_times = np.concatenate(time_chunks)
        point_midi = np.concatenate(midi_chunks)
        point_magnitudes = np.concatenate(magnitude_chunks)
        point_tracks = np.concatenate(track_chunks)
        order = np.argsort(point_tracks, kind="stable")
        point_times = point_times[order]
        point_midi = point_midi[order]
        point_magnitudes = point_magnitudes[order]
        counts = np.bincount(point_tracks, minlength=next_track_id).astype(np.uint64)
        offsets = np.empty(next_track_id + 1, dtype=np.uint64)
        offsets[0] = 0
        np.cumsum(counts, out=offsets[1:])
        starts = point_times[offsets[:-1].astype(np.int64)]
        ends = point_times[(offsets[1:] - 1).astype(np.int64)]
        average = np.add.reduceat(point_magnitudes, offsets[:-1].astype(np.int64)) / counts
        maxima = np.maximum.reduceat(point_magnitudes, offsets[:-1].astype(np.int64))
    else:
        point_times = np.empty(0, dtype=np.float32)
        point_midi = np.empty(0, dtype=np.float32)
        point_magnitudes = np.empty(0, dtype=np.float32)
        offsets = np.zeros(1, dtype=np.uint64)
        starts = ends = average = maxima = np.empty(0, dtype=np.float32)

    temporary = FrequencyTrackStore(
        point_times=_readonly(point_times.astype(np.float32, copy=False)),
        point_midi=_readonly(point_midi.astype(np.float32, copy=False)),
        point_magnitudes=_readonly(point_magnitudes.astype(np.float32, copy=False)),
        track_offsets=_readonly(offsets),
        track_start_times=_readonly(starts.astype(np.float32, copy=False)),
        track_end_times=_readonly(ends.astype(np.float32, copy=False)),
        track_average_magnitudes=_readonly(average.astype(np.float32, copy=False)),
        track_max_magnitudes=_readonly(maxima.astype(np.float32, copy=False)),
        source_fingerprint=(*spectrum.source_fingerprint, TRACK_STORE_VERSION, options),
        settings=options,
        stats=FrequencyTrackStats(0, 0, 0.0, 0.0, 0.0, 0, options.base_tolerance_cents, options.maximum_gap_seconds, options.maximum_tolerance_cents),
    )
    durations = temporary.track_end_times - temporary.track_start_times
    stats = FrequencyTrackStats(
        total_tracks=temporary.track_count,
        total_points=temporary.point_count,
        average_duration=float(np.mean(durations)) if durations.size else 0.0,
        longest_duration=float(np.max(durations)) if durations.size else 0.0,
        generation_seconds=time.perf_counter() - started,
        store_memory_bytes=temporary.memory_bytes,
        base_tolerance_cents=options.base_tolerance_cents,
        maximum_gap_seconds=options.maximum_gap_seconds,
        maximum_tolerance_cents=options.maximum_tolerance_cents,
    )
    return FrequencyTrackStore(
        point_times=temporary.point_times,
        point_midi=temporary.point_midi,
        point_magnitudes=temporary.point_magnitudes,
        track_offsets=temporary.track_offsets,
        track_start_times=temporary.track_start_times,
        track_end_times=temporary.track_end_times,
        track_average_magnitudes=temporary.track_average_magnitudes,
        track_max_magnitudes=temporary.track_max_magnitudes,
        source_fingerprint=temporary.source_fingerprint,
        settings=options,
        stats=stats,
    )

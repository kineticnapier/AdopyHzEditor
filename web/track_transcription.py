"""Frequency-track selection and transcription helpers for the Web editor.

Phase C keeps FrequencyTrackStore as read-only analysis data and only creates
normal editor Notes after an explicit user action.  The methods in this module
are installed onto EditingMixin so pywebview exposes them without coupling the
core track derivation code to the Web backend.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from core.note_model import Note
from web.editing import EditingMixin, MIN_NOTE_DURATION


_MAX_TRACK_SELECTION = 10_000


def _track_slice(store, track_id: int) -> tuple[int, int] | None:
    if track_id < 0 or track_id >= int(store.track_count):
        return None
    lo = int(store.track_offsets[track_id])
    hi = int(store.track_offsets[track_id + 1])
    if hi <= lo:
        return None
    return lo, hi


def _intersects_track_rect(
    store,
    track_id: int,
    start_time: float,
    end_time: float,
    minimum_midi: float,
    maximum_midi: float,
) -> bool:
    bounds = _track_slice(store, track_id)
    if bounds is None:
        return False
    lo, hi = bounds
    times = store.point_times[lo:hi]
    midis = store.point_midi[lo:hi]
    if not times.size:
        return False

    left = max(0, int(np.searchsorted(times, start_time, side="left")) - 1)
    right = min(times.size, int(np.searchsorted(times, end_time, side="right")) + 1)
    if right <= left:
        return False
    local_t = times[left:right]
    local_m = midis[left:right]

    point_hit = (
        (local_t >= start_time)
        & (local_t <= end_time)
        & (local_m >= minimum_midi)
        & (local_m <= maximum_midi)
    )
    if bool(np.any(point_hit)):
        return True

    if local_t.size < 2:
        return False
    for index in range(local_t.size - 1):
        t0 = float(local_t[index])
        t1 = float(local_t[index + 1])
        if max(t0, t1) < start_time or min(t0, t1) > end_time:
            continue
        m0 = float(local_m[index])
        m1 = float(local_m[index + 1])
        if max(m0, m1) >= minimum_midi and min(m0, m1) <= maximum_midi:
            return True
    return False


def _segment_arrays(
    store,
    track_id: int,
    start_time: float | None,
    end_time: float | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float] | None:
    bounds = _track_slice(store, track_id)
    if bounds is None:
        return None
    lo, hi = bounds
    all_times = np.asarray(store.point_times[lo:hi], dtype=np.float64)
    all_midis = np.asarray(store.point_midi[lo:hi], dtype=np.float64)
    all_magnitudes = np.asarray(store.point_magnitudes[lo:hi], dtype=np.float64)
    if not all_times.size:
        return None

    track_start = float(store.track_start_times[track_id])
    track_end = float(store.track_end_times[track_id])
    clip_start = track_start if start_time is None else max(track_start, float(start_time))
    clip_end = track_end if end_time is None else min(track_end, float(end_time))
    if clip_end < clip_start:
        return None

    if all_times.size == 1 or clip_end <= clip_start + 1e-12:
        t = clip_start
        midi = float(all_midis[0])
        magnitude = float(all_magnitudes[0])
        return (
            np.array([t], dtype=np.float64),
            np.array([midi], dtype=np.float64),
            np.array([magnitude], dtype=np.float64),
            clip_start,
            clip_end,
        )

    inside = (all_times > clip_start) & (all_times < clip_end)
    times = np.concatenate(
        (
            np.array([clip_start], dtype=np.float64),
            all_times[inside],
            np.array([clip_end], dtype=np.float64),
        )
    )
    midis = np.concatenate(
        (
            np.array([np.interp(clip_start, all_times, all_midis)], dtype=np.float64),
            all_midis[inside],
            np.array([np.interp(clip_end, all_times, all_midis)], dtype=np.float64),
        )
    )
    magnitudes = np.concatenate(
        (
            np.array([np.interp(clip_start, all_times, all_magnitudes)], dtype=np.float64),
            all_magnitudes[inside],
            np.array([np.interp(clip_end, all_times, all_magnitudes)], dtype=np.float64),
        )
    )

    keep = np.ones(times.size, dtype=bool)
    if times.size > 1:
        keep[1:] = np.diff(times) > 1e-12
    return times[keep], midis[keep], magnitudes[keep], clip_start, clip_end


def _minimum_note_span(start: float, end: float, duration: float) -> tuple[float, float]:
    start = max(0.0, min(float(duration), float(start)))
    end = max(start, min(float(duration), float(end)))
    if end - start >= MIN_NOTE_DURATION:
        return start, end
    end = min(float(duration), start + MIN_NOTE_DURATION)
    if end - start >= MIN_NOTE_DURATION:
        return start, end
    start = max(0.0, end - MIN_NOTE_DURATION)
    return start, end


def _velocity(magnitudes: np.ndarray) -> int:
    peak = float(np.max(magnitudes)) if magnitudes.size else 0.0
    return int(round(1.0 + 126.0 * max(0.0, min(1.0, peak))))


def _fixed_note(
    times: np.ndarray,
    midis: np.ndarray,
    magnitudes: np.ndarray,
    start: float,
    end: float,
    duration: float,
) -> Note | None:
    start, end = _minimum_note_span(start, end, duration)
    if end <= start:
        return None
    weights = np.maximum(magnitudes, 1e-6)
    # MIDI is affine in log(frequency), so this weighted MIDI mean is exactly
    # the magnitude-weighted geometric mean frequency requested by the UI spec.
    midi = float(np.average(midis, weights=weights))
    return Note(start, end, midi, _velocity(magnitudes)).normalized()


def _smooth_midis(midis: np.ndarray) -> np.ndarray:
    values = np.asarray(midis, dtype=np.float64)
    if values.size < 5:
        return values.copy()
    padded = np.pad(values, (2, 2), mode="edge")
    smooth = np.convolve(padded, np.ones(5, dtype=np.float64) / 5.0, mode="valid")
    smooth[0] = values[0]
    smooth[-1] = values[-1]
    return smooth


def _curve_controls(
    times: np.ndarray,
    midis: np.ndarray,
    magnitudes: np.ndarray,
) -> tuple[float, float, float, float]:
    smooth = _smooth_midis(midis)
    p0 = float(smooth[0])
    p3 = float(smooth[-1])
    if smooth.size < 4 or float(times[-1] - times[0]) <= 1e-12:
        delta = p3 - p0
        return p0, p0 + delta / 3.0, p0 + 2.0 * delta / 3.0, p3

    u = (times - times[0]) / max(1e-12, float(times[-1] - times[0]))
    one_minus = 1.0 - u
    b0 = one_minus**3
    b1 = 3.0 * one_minus**2 * u
    b2 = 3.0 * one_minus * u**2
    b3 = u**3
    target = smooth - b0 * p0 - b3 * p3
    matrix = np.column_stack((b1, b2))
    weights = np.sqrt(np.maximum(magnitudes, 0.05))
    try:
        solved, *_ = np.linalg.lstsq(matrix * weights[:, None], target * weights, rcond=None)
        p1, p2 = (float(solved[0]), float(solved[1]))
    except (np.linalg.LinAlgError, ValueError):
        delta = p3 - p0
        p1, p2 = p0 + delta / 3.0, p0 + 2.0 * delta / 3.0
    return tuple(max(0.0, min(127.0, value)) for value in (p0, p1, p2, p3))


def _curve_note(
    times: np.ndarray,
    midis: np.ndarray,
    magnitudes: np.ndarray,
    start: float,
    end: float,
    duration: float,
) -> Note | None:
    start, end = _minimum_note_span(start, end, duration)
    if end <= start:
        return None
    p0, p1, p2, p3 = _curve_controls(times, midis, magnitudes)
    return Note(
        start,
        end,
        p0,
        _velocity(magnitudes),
        "curve",
        p3,
        p1,
        p2,
        "bezier_pitch",
    ).normalized()


def find_frequency_tracks(
    self: EditingMixin,
    start_time: float,
    end_time: float,
    minimum_midi: float,
    maximum_midi: float,
) -> dict[str, Any]:
    """Return full-resolution track ids intersecting a transcription rectangle."""
    with self._lock:
        store = getattr(self, "frequency_track_store", None)
    if store is None:
        return {"trackIds": [], "status": "Frequency Tracks を先に解析してください"}

    start = max(0.0, float(start_time))
    end = max(start, float(end_time))
    midi_min = max(0.0, min(127.0, float(minimum_midi)))
    midi_max = max(midi_min, min(127.0, float(maximum_midi)))
    candidates = np.flatnonzero(
        (store.track_start_times <= end) & (store.track_end_times >= start)
    )
    found: list[int] = []
    truncated = False
    for value in candidates:
        track_id = int(value)
        if _intersects_track_rect(store, track_id, start, end, midi_min, midi_max):
            found.append(track_id)
            if len(found) >= _MAX_TRACK_SELECTION:
                truncated = True
                break
    suffix = "（上限10000本で打ち切り）" if truncated else ""
    return {
        "trackIds": found,
        "status": f"Frequency Track を{len(found)}本選択しました{suffix}",
    }


def create_notes_from_tracks(
    self: EditingMixin,
    track_ids: list[int],
    mode: str = "fixed",
    start_time: float | None = None,
    end_time: float | None = None,
) -> dict[str, Any]:
    """Create normal Notes from full-resolution track data as one undo step."""
    if not isinstance(track_ids, list):
        raise TypeError("track_ids must be an array")
    conversion_mode = str(mode).lower()
    if conversion_mode not in {"fixed", "curve"}:
        raise ValueError("mode must be 'fixed' or 'curve'")

    with self._lock:
        store = getattr(self, "frequency_track_store", None)
        if store is None:
            return {
                "notes": self._note_dicts(),
                "indices": [],
                "changed": False,
                "status": "Frequency Tracks を先に解析してください",
            }

        valid_ids = sorted(
            {
                int(value)
                for value in track_ids
                if isinstance(value, (int, np.integer))
                and 0 <= int(value) < int(store.track_count)
            }
        )
        if not valid_ids:
            return {
                "notes": self._note_dicts(),
                "indices": [],
                "changed": False,
                "status": "Track が選択されていません",
            }

        clip_start = None if start_time is None else max(0.0, float(start_time))
        clip_end = None if end_time is None else min(float(self.duration), float(end_time))
        if clip_start is not None and clip_end is not None and clip_end < clip_start:
            clip_start, clip_end = clip_end, clip_start

        created: list[Note] = []
        used_track_ids: list[int] = []
        for track_id in valid_ids:
            segment = _segment_arrays(store, track_id, clip_start, clip_end)
            if segment is None:
                continue
            times, midis, magnitudes, seg_start, seg_end = segment
            note = (
                _curve_note(times, midis, magnitudes, seg_start, seg_end, float(self.duration))
                if conversion_mode == "curve"
                else _fixed_note(times, midis, magnitudes, seg_start, seg_end, float(self.duration))
            )
            if note is None:
                continue
            created.append(note)
            used_track_ids.append(track_id)

        if not created:
            return {
                "notes": self._note_dicts(),
                "indices": [],
                "changed": False,
                "status": "指定範囲にNote化できるTrackがありません",
            }

        self._push_undo()
        first_index = len(self.notes)
        self.notes.extend(created)
        indices = list(range(first_index, first_index + len(created)))
        self._dirty = True
        self._sync_notes_to_player()
        label = "Curve Note" if conversion_mode == "curve" else "固定Note"
        self._status = f"Frequency Track {len(created)}本を{label}へ変換しました"
        return {
            "notes": self._note_dicts(),
            "indices": indices,
            "trackIds": used_track_ids,
            "changed": True,
            "status": self._status,
        }


def install_track_transcription() -> None:
    """Install Phase C methods once onto the shared editing mixin."""
    if getattr(EditingMixin, "_track_transcription_installed", False):
        return
    EditingMixin.find_frequency_tracks = find_frequency_tracks  # type: ignore[attr-defined]
    EditingMixin.create_notes_from_tracks = create_notes_from_tracks  # type: ignore[attr-defined]
    EditingMixin._track_transcription_installed = True  # type: ignore[attr-defined]

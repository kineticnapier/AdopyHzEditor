"""Web bridge for the kick pitch tracking prototype.

``analyze_kick_pitch`` runs :mod:`core.pitch_tracking` on a short region of the
decoded audio and keeps the result as read-only analysis data (like the
Frequency Track store).  ``create_notes_from_kick_pitch`` turns chosen
candidate tracks into normal Curve Notes in one undo step, reusing the Bezier
fit of the Frequency Track transcription path.  One cubic Bezier rarely fits
a whole kick sweep within a few cents, so the confident part of a track is
split recursively until every segment stays inside ``max_error_cents``.
"""

from __future__ import annotations

from dataclasses import replace
import math
from typing import Any

import numpy as np

from core.note_model import Note, hz_to_midi
from core.pitch_tracking import METHODS, PitchTrackingResult, PitchTrackingSettings, analyze_pitch_region
from web.track_transcription import _minimum_note_span, _smooth_midis, _velocity


DEFAULT_MAX_ERROR_CENTS = 5.0
DEFAULT_MIN_CONFIDENCE = 0.5
MAX_CURVE_SEGMENTS_PER_TRACK = 256


def _bezier_midis(times: np.ndarray, controls: tuple[float, float, float, float]) -> np.ndarray:
    p0, p1, p2, p3 = controls
    span = float(times[-1] - times[0])
    u = (times - times[0]) / span if span > 0 else np.zeros_like(times)
    v = 1.0 - u
    return v**3 * p0 + 3 * v**2 * u * p1 + 3 * v * u**2 * p2 + u**3 * p3


def _fit_controls(times: np.ndarray, midis: np.ndarray, weights: np.ndarray) -> tuple[float, float, float, float]:
    """Weighted least-squares cubic Bezier with fixed end points.

    Same model as ``web.track_transcription._curve_controls`` (time-uniform
    ``bezier_pitch``), but without its internal 5-point smoothing: the input
    here is already the smoothed reference, and smoothing short split
    segments again would bend their ends.
    """
    p0 = float(midis[0])
    p3 = float(midis[-1])
    span = float(times[-1] - times[0])
    l1 = p0 + (p3 - p0) / 3.0  # controls of the straight line p0 -> p3
    l2 = p0 + 2.0 * (p3 - p0) / 3.0
    if midis.size < 3 or span <= 1e-12:
        return p0, l1, l2, p3
    u = (times - times[0]) / span
    v = 1.0 - u
    b1 = 3.0 * v**2 * u
    b2 = 3.0 * v * u**2
    # Solve for the deviation from the straight line so an under-determined
    # 3-point segment gets the smallest bend that passes through its middle.
    target = midis - (v**3 * p0 + b1 * l1 + b2 * l2 + u**3 * p3)
    w = np.sqrt(np.maximum(weights, 0.05))
    solved, *_ = np.linalg.lstsq(np.column_stack((b1, b2)) * w[:, None], target * w, rcond=None)
    return p0, l1 + float(solved[0]), l2 + float(solved[1]), p3


def _reference_midis(midis: np.ndarray) -> np.ndarray:
    if midis.size < 3:
        return midis.copy()
    padded = np.pad(midis, 1, mode="edge")
    median = np.median(np.stack((padded[:-2], padded[1:-1], padded[2:])), axis=0)
    return _smooth_midis(median)


def fit_curve_segments(
    times: np.ndarray,
    midis: np.ndarray,
    weights: np.ndarray,
    *,
    max_error_cents: float = DEFAULT_MAX_ERROR_CENTS,
    max_segments: int = MAX_CURVE_SEGMENTS_PER_TRACK,
) -> list[tuple[int, int, tuple[float, float, float, float], float]]:
    """Split one continuous run into Bezier segments within the error bound.

    Returns ``(first_index, last_index, controls, max_error_cents)`` per
    segment.  Adjacent segments share their boundary sample, so the resulting
    Curve Notes join without a pitch step.  The error is measured against a
    lightly smoothed reference (3-point median, then the same 5-point mean the
    Frequency Track fit uses, about 5 ms at a 1 ms hop) so the fit does not
    chase frame-to-frame estimator jitter.
    """
    times = np.asarray(times, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    midis = _reference_midis(np.asarray(midis, dtype=np.float64))
    out: list[tuple[int, int, tuple[float, float, float, float], float]] = []
    pending = [(0, times.size - 1)]
    while pending:
        lo, hi = pending.pop()
        sl = slice(lo, hi + 1)
        controls = _fit_controls(times[sl], midis[sl], weights[sl])
        error = np.abs(_bezier_midis(times[sl], controls) - midis[sl]) * 100.0
        worst = float(error.max()) if error.size else 0.0
        if worst > max_error_cents and hi - lo >= 4 and len(out) + len(pending) + 2 <= max_segments:
            # Split at the worst interior sample; both halves keep >= 3 points.
            mid = lo + 2 + int(np.argmax(error[2:-2]))
            pending.append((mid, hi))
            pending.append((lo, mid))
            continue
        out.append((lo, hi, controls, worst))
    out.sort(key=lambda item: item[0])
    return out


def _confident_runs(times: np.ndarray, confidence: np.ndarray, min_confidence: float, max_gap: float) -> list[list[int]]:
    """Index lists of confident points; a hole longer than ``max_gap`` splits.

    Low-confidence points inside a short hole are dropped from the fit, never
    used; longer holes end the run so unreliable stretches are not bridged.
    """
    ok = np.flatnonzero(confidence >= min_confidence)
    runs: list[list[int]] = []
    current: list[int] = []
    for index in ok:
        index = int(index)
        if current and times[index] - times[current[-1]] > max_gap:
            runs.append(current)
            current = []
        current.append(index)
    if current:
        runs.append(current)
    return [run for run in runs if len(run) >= 2]


class KickPitchMixin:
    """pywebview API surface for the kick pitch prototype."""

    kick_pitch_result: PitchTrackingResult | None = None

    def analyze_kick_pitch(
        self,
        start_time: float,
        end_time: float,
        min_hz: float = 25.0,
        max_hz: float = 500.0,
        hop_ms: float = 1.0,
        method: str = "harmonic",
    ) -> dict[str, Any]:
        with self._lock:
            audio_path = self.audio_path
            source_generation = self._source_generation
        player = self.player
        with player.lock:
            samples = player.audio
            sample_rate = int(player.sr)
        if not audio_path or samples is None or not len(samples):
            return {"available": False, "status": "音源を開いてください"}
        if str(method) not in METHODS:
            raise ValueError(f"method must be one of {METHODS}")
        start = max(0.0, float(start_time))
        end = max(start, float(end_time))
        duration = len(samples) / sample_rate
        end = min(end, duration)
        defaults = PitchTrackingSettings()
        if end - start < 0.01:
            return {"available": False, "status": "解析範囲が短すぎます（10ms以上）"}
        if end - start > defaults.max_region_seconds:
            return {
                "available": False,
                "status": f"解析範囲は{defaults.max_region_seconds:g}秒以内にしてください",
            }
        settings = replace(
            defaults,
            method=str(method),
            min_hz=max(10.0, float(min_hz)),
            max_hz=max(float(min_hz) * 1.5, min(2000.0, float(max_hz))),
            hop_seconds=min(0.02, max(0.0001, float(hop_ms) / 1000.0)),
        )
        result = analyze_pitch_region(samples, sample_rate, start, end, settings)
        with self._lock:
            if source_generation != self._source_generation or audio_path != self.audio_path:
                return {"available": False, "status": "音源が変更されたため解析結果を破棄しました"}
            self.kick_pitch_result = result
            primary = (
                result.candidates[result.primary_index]
                if result.primary_index is not None
                else None
            )
            self._status = (
                f"キック音高: 候補{len(result.candidates)}本"
                + (f"、主候補 {float(np.median(primary.hz)):.1f} Hz" if primary is not None else "")
                + f"（{result.stats['frameCount']}フレーム, {result.stats['analysisSeconds']:.2f}s）"
            )
            status = self._status
        payload = result.to_dict()
        payload.update(available=True, status=status)
        return payload

    def clear_kick_pitch(self) -> dict[str, Any]:
        with self._lock:
            self.kick_pitch_result = None
        return {"available": False}

    def create_notes_from_kick_pitch(
        self,
        candidate_ids: list[int],
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        max_error_cents: float = DEFAULT_MAX_ERROR_CENTS,
    ) -> dict[str, Any]:
        if not isinstance(candidate_ids, list):
            raise TypeError("candidate_ids must be an array")
        with self._lock:
            result = self.kick_pitch_result
            if result is None:
                return {
                    "notes": self._note_dicts(),
                    "indices": [],
                    "changed": False,
                    "status": "キック音高を先に解析してください",
                }
            by_id = {c.id: c for c in result.candidates}
            chosen = [by_id[int(v)] for v in candidate_ids if isinstance(v, (int, np.integer)) and int(v) in by_id]
            threshold = min(1.0, max(0.0, float(min_confidence)))
            tolerance = min(100.0, max(0.5, float(max_error_cents)))
            gap = float(result.stats.get("hopSeconds", 0.001)) * 3.5  # <= 2 missing frames
            created: list[Note] = []
            worst_error = 0.0
            for candidate in chosen:
                midis = np.array([hz_to_midi(float(h)) for h in candidate.hz])
                for run in _confident_runs(candidate.times, candidate.confidence, threshold, gap):
                    t = candidate.times[run]
                    m = midis[run]
                    w = candidate.confidence[run]
                    s = candidate.strength[run]
                    for a, b, controls, error in fit_curve_segments(t, m, w, max_error_cents=tolerance):
                        start, end = _minimum_note_span(float(t[a]), float(t[b]), float(self.duration))
                        if end <= start:
                            continue
                        p0, p1, p2, p3 = (max(0.0, min(127.0, value)) for value in controls)
                        created.append(
                            Note(start, end, p0, _velocity(s[a : b + 1]), "curve", p3, p1, p2, "bezier_pitch").normalized()
                        )
                        worst_error = max(worst_error, error)
            if not created:
                return {
                    "notes": self._note_dicts(),
                    "indices": [],
                    "changed": False,
                    "status": "信頼度の条件を満たす区間がありません",
                }
            self._push_undo()
            first_index = len(self.notes)
            self.notes.extend(created)
            self._dirty = True
            self._sync_notes_to_player()
            self._status = (
                f"キック音高 {len(chosen)}本から Curve Note {len(created)}個を作成"
                f"（最大誤差 {worst_error:.1f} cent）"
            )
            return {
                "notes": self._note_dicts(),
                "indices": list(range(first_index, first_index + len(created))),
                "changed": True,
                "maxErrorCents": worst_error if math.isfinite(worst_error) else None,
                "status": self._status,
            }

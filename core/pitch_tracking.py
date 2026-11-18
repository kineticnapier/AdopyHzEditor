"""Short-region pitch tracking for kick drums (Hardstyle Piep / Zaag kicks).

The editor's CQT and Vorbis Direct layers show *where* energy is; this module
answers a narrower question for one user-selected region: what is the
continuous fundamental-frequency trajectory, how strong is it, and how much can
each estimate be trusted.

Four estimators are available so they can be compared on the same frames:

``peak``
    Frequency of the strongest FFT bin (no interpolation).  Baseline only.
``phase``
    Phase-vocoder instantaneous frequency of the strongest peak, computed from
    the phase difference of two time windows ``lag`` samples apart (the method
    used by Bistanium/wav_to_midi_pitch_bend, ``fft2midi.rs``).  ``lag = 1``
    makes the estimate unambiguous over the whole band; ``lag = N / 4``
    reproduces the reference hop-based formulation.
``multiwindow``
    ``phase`` evaluated with several window lengths per frame.  The shortest
    window that still holds ``min_periods`` periods of the estimate (and is not
    contradicted by a longer window) is used, giving short windows for the
    fast high-pitched attack and long windows for the low tail.
``harmonic``
    ``multiwindow`` plus harmonic grouping: phase-refined spectral peaks are
    explained as harmonics of a fundamental, so a strong 12th harmonic of a
    73 Hz kick (the "piep" at ~880 Hz) is attributed to 73 Hz instead of being
    reported as a separate pitch.  Peaks left unexplained are searched again
    and returned as independent candidate tracks.

Unlike the reference implementation no MIDI notes are produced: the output is
a frame-wise trajectory (time, Hz, strength, confidence, flags) plus linked
candidate tracks.  Unreliable frames are kept with low confidence and flags
rather than being bridged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import time
from typing import Any

import numpy as np


FLAG_LOW_ENERGY = 1
FLAG_ONSET = 2
FLAG_PHASE_INCONSISTENT = 4
FLAG_WINDOW_DISAGREE = 8
FLAG_PITCH_JUMP = 16
FLAG_NO_PITCH = 32

FLAG_NAMES = {
    FLAG_LOW_ENERGY: "lowEnergy",
    FLAG_ONSET: "onset",
    FLAG_PHASE_INCONSISTENT: "phaseInconsistent",
    FLAG_WINDOW_DISAGREE: "windowDisagree",
    FLAG_PITCH_JUMP: "pitchJump",
    FLAG_NO_PITCH: "noPitch",
}

METHODS = ("peak", "phase", "multiwindow", "harmonic")


@dataclass(frozen=True)
class PitchTrackingSettings:
    method: str = "harmonic"
    min_hz: float = 25.0
    max_hz: float = 500.0
    hop_seconds: float = 0.001
    window_seconds: tuple[float, ...] = (0.0125, 0.025, 0.05, 0.1)
    # Window used by the single-window methods ("peak" / "phase").
    single_window_seconds: float = 0.05
    # Phase-difference lag in analysis samples; 0 means N / 4 (reference style).
    phase_lag_samples: int = 1
    zero_padding: int = 2
    min_periods: float = 2.0
    min_periods_harmonic: float = 2.0  # 4.0 = steadier rich stationary tones, worse on fast sweeps
    harmonic_tolerance_cents: float = 35.0
    max_harmonic: int = 40
    max_components: int = 3
    peak_floor_db: float = -45.0
    energy_floor_db: float = -60.0
    onset_dynamic_db: float = 20.0
    max_slope_cents_per_second: float = 120_000.0
    link_tolerance_cents: float = 60.0
    link_min_confidence: float = 0.25
    max_link_gap_seconds: float = 0.04
    outlier_radius_seconds: float = 0.006
    outlier_cents: float = 300.0
    min_track_seconds: float = 0.012
    analysis_rate: float = 0.0  # 0 = choose from max_hz
    max_region_seconds: float = 10.0


@dataclass
class PitchFrames:
    times: np.ndarray
    hz: np.ndarray
    strength: np.ndarray
    confidence: np.ndarray
    flags: np.ndarray
    window_seconds: np.ndarray


@dataclass
class PitchCandidate:
    id: int
    role: str
    times: np.ndarray
    hz: np.ndarray
    strength: np.ndarray
    confidence: np.ndarray
    flags: np.ndarray
    harmonic_of: int | None = None
    harmonic_number: int | None = None

    @property
    def duration(self) -> float:
        return float(self.times[-1] - self.times[0]) if self.times.size else 0.0

    @property
    def score(self) -> float:
        return float(np.sum(self.strength * self.confidence))


@dataclass
class PitchTrackingResult:
    start: float
    end: float
    method: str
    frames: PitchFrames
    candidates: list[PitchCandidate]
    primary_index: int | None
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        def floats(values: np.ndarray, digits: int = 6) -> list[float | None]:
            out: list[float | None] = []
            for value in np.asarray(values, dtype=np.float64):
                out.append(round(float(value), digits) if math.isfinite(value) else None)
            return out

        def midi(values: np.ndarray) -> np.ndarray:
            with np.errstate(divide="ignore", invalid="ignore"):
                return 69.0 + 12.0 * np.log2(np.asarray(values, dtype=np.float64) / 440.0)

        return {
            "start": self.start,
            "end": self.end,
            "method": self.method,
            "flagNames": {str(bit): name for bit, name in FLAG_NAMES.items()},
            "frames": {
                "times": floats(self.frames.times),
                "hz": floats(self.frames.hz, 4),
                "midi": floats(midi(self.frames.hz), 4),
                "strength": floats(self.frames.strength, 4),
                "confidence": floats(self.frames.confidence, 4),
                "flags": [int(v) for v in self.frames.flags],
                "windowSeconds": floats(self.frames.window_seconds, 5),
            },
            "candidates": [
                {
                    "id": c.id,
                    "role": c.role,
                    "harmonicOf": c.harmonic_of,
                    "harmonicNumber": c.harmonic_number,
                    "duration": c.duration,
                    "medianHz": float(np.median(c.hz)) if c.hz.size else None,
                    "meanConfidence": float(np.mean(c.confidence)) if c.confidence.size else 0.0,
                    "times": floats(c.times),
                    "hz": floats(c.hz, 4),
                    "midi": floats(midi(c.hz), 4),
                    "strength": floats(c.strength, 4),
                    "confidence": floats(c.confidence, 4),
                    "flags": [int(v) for v in c.flags],
                }
                for c in self.candidates
            ],
            "primaryIndex": self.primary_index,
            "stats": dict(self.stats),
        }


# --------------------------------------------------------------------------
# Signal preparation


def _analysis_rate(sr: int, settings: PitchTrackingSettings) -> tuple[int, float]:
    """Return an integer decimation factor and the resulting analysis rate."""
    target = settings.analysis_rate or max(8000.0, 16.0 * settings.max_hz)
    factor = max(1, int(math.floor(sr / target)))
    return factor, sr / factor


def _mono(samples: np.ndarray) -> np.ndarray:
    y = np.asarray(samples, dtype=np.float64)
    if y.ndim == 2:
        y = y.mean(axis=1) if y.shape[1] <= 8 else y.mean(axis=0)
    return y.reshape(-1)


def _excerpt(y: np.ndarray, sr: int, start: float, end: float, margin: float) -> tuple[np.ndarray, int]:
    """Copy [start - margin, end + margin] seconds, zero-padding outside the audio."""
    first = int(math.floor((start - margin) * sr))
    last = int(math.ceil((end + margin) * sr))
    out = np.zeros(max(1, last - first), dtype=np.float64)
    lo = max(0, first)
    hi = min(y.size, last)
    if hi > lo:
        out[lo - first : hi - first] = y[lo:hi]
    return out, first


def _decimate(x: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return x
    from scipy.signal import resample_poly

    return resample_poly(x, 1, factor)


def _analytic(x: np.ndarray) -> np.ndarray:
    from scipy.signal import hilbert

    return hilbert(x)


def _transient_in_window(cumulative_energy: np.ndarray, centre: int, size: int, ratio: float) -> bool:
    """True when the window straddles an onset / offset.

    The inner 80 % of the window is split into four blocks; a block that is
    ``onset_dynamic_db`` quieter than the loudest one means part of the window
    is (near) silence, so its frequency estimate mixes attack and silence.
    The real signal is used because a Hilbert envelope pre-rings before an
    onset.
    """
    half = int(size * 0.4)
    edges = np.linspace(centre - half, centre + half, 5).astype(np.int64)
    blocks = np.diff(cumulative_energy[edges]) / np.maximum(np.diff(edges), 1)
    loudest = float(blocks.max())
    return loudest > 0.0 and float(blocks.min()) < loudest * ratio


# --------------------------------------------------------------------------
# Per-window spectral evidence


@dataclass
class _WindowEvidence:
    """Frame-wise estimates from one window length."""

    size: int
    seconds: float
    f0: np.ndarray            # primary estimate (Hz, NaN when none)
    strength: np.ndarray      # matched linear amplitude of the primary
    lobe: np.ndarray          # instantaneous-frequency consistency (0..1)
    harmonicity: np.ndarray   # explained / total band energy (0..1)
    rich: np.ndarray          # primary has audible harmonics 2..4
    energy: np.ndarray        # windowed mean square
    components: list[list[tuple[float, float, float]]]  # per frame (hz, strength, lobe)


def _frame_matrix(y_pad: np.ndarray, starts: np.ndarray, size: int) -> np.ndarray:
    view = np.lib.stride_tricks.sliding_window_view(y_pad, size)
    return view[starts]


def _local_peaks(mag: np.ndarray, lo: int, hi: int) -> np.ndarray:
    """Boolean matrix of strict local maxima within [lo, hi)."""
    peaks = np.zeros(mag.shape, dtype=bool)
    lo = max(1, lo)
    hi = min(mag.shape[1] - 1, hi)
    if hi <= lo:
        return peaks
    centre = mag[:, lo:hi]
    peaks[:, lo:hi] = (centre > mag[:, lo - 1 : hi - 1]) & (centre >= mag[:, lo + 1 : hi + 1])
    return peaks


def _cents(a: np.ndarray | float, b: np.ndarray | float) -> np.ndarray | float:
    return 1200.0 * np.log2(np.asarray(a, dtype=np.float64) / np.asarray(b, dtype=np.float64))


def _score_fundamentals(
    f0s: np.ndarray,
    freqs: np.ndarray,
    amps: np.ndarray,
    settings: PitchTrackingSettings,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Score candidate fundamentals against phase-refined peaks.

    Returns (score, matched amplitude sum, match mask[candidate, peak]).
    The score is the matched *energy* (weak noise peaks barely count) times
    the square root of the share of harmonics 1..min(4, highest match) that
    are present, which penalises sub-harmonic explanations, and halved when
    the candidate's own fundamental has no peak.
    """
    count = f0s.size
    by_amp = np.argsort(-amps, kind="stable")  # first match per h = strongest
    p_freqs = freqs[by_amp]
    p_amps = amps[by_amp]
    ratio = p_freqs[None, :] / f0s[:, None]
    h = np.rint(ratio)
    hc = np.maximum(h, 1.0)
    deviation = np.abs(1200.0 * np.log2(ratio / hc))
    # Never accept more than a quarter of the harmonic spacing: at high
    # harmonic numbers a fixed cents tolerance would match any noise peak.
    h_tol = np.minimum(settings.harmonic_tolerance_cents, 1200.0 * np.log2(1.0 + 0.25 / hc))
    mask_sorted = (h >= 1) & (h <= settings.max_harmonic) & (deviation <= h_tol)
    mask = np.zeros((count, freqs.size), dtype=bool)
    mask[:, by_amp] = mask_sorted
    score = np.full(count, -1.0)
    total = np.zeros(count)
    rows, cols = np.nonzero(mask_sorted)
    if not rows.size:
        return score, total, mask
    max_h = settings.max_harmonic + 1
    keys = rows * max_h + h[rows, cols].astype(np.int64)
    _unique, first = np.unique(keys, return_index=True)  # one peak per harmonic
    u_rows = rows[first]
    u_h = h[u_rows, cols[first]].astype(np.int64)
    u_amp = p_amps[cols[first]]
    total = np.bincount(u_rows, weights=u_amp, minlength=count)
    energy = np.bincount(u_rows, weights=u_amp * u_amp, minlength=count)
    top = np.zeros(count, dtype=np.int64)
    np.maximum.at(top, u_rows, u_h)
    presence = np.zeros((count, 5), dtype=np.float64)
    low = u_h <= 4
    presence[u_rows[low], u_h[low]] = 1.0
    low_count = np.clip(top, 1, 4)
    present = np.cumsum(presence[:, 1:], axis=1)[np.arange(count), low_count - 1]
    # A candidate whose own fundamental is silent is suspect (876 Hz alone must
    # not be read as harmonic 2 of a non-existent 438 Hz tone).
    fundamental = np.where(presence[:, 1] > 0, 1.0, 0.5)
    score = np.where(top > 0, energy * np.sqrt(present / low_count) * fundamental, -1.0)
    return score, total, mask


def _harmonic_search(
    freqs: np.ndarray,
    amps: np.ndarray,
    settings: PitchTrackingSettings,
    consistency: np.ndarray | None = None,
) -> tuple[float, float, np.ndarray] | None:
    """Best fundamental explaining the peaks, as (f0, matched amplitude, mask)."""
    if not freqs.size:
        return None
    order = np.argsort(-amps)
    seeds = order[: min(6, order.size)]
    candidates = [
        float(freqs[index]) / h
        for index in seeds
        for h in range(1, 9)
        if settings.min_hz <= float(freqs[index]) / h <= settings.max_hz
    ]
    if not candidates:
        return None
    f0s = np.asarray(candidates, dtype=np.float64)
    score, total, mask = _score_fundamentals(f0s, freqs, amps, settings)
    best_row = int(np.argmax(score))  # first maximum = strongest seed
    if score[best_row] <= 0.0:
        return None
    f0 = float(f0s[best_row])
    best_score = float(score[best_row])
    best_total = float(total[best_row])
    best_mask = mask[best_row]
    # Octave-up preference: if 2*f0 or 3*f0 explains almost the same energy,
    # the extra matches of f0 were weak (noise) peaks.
    ups = np.array([f0 * k for k in (3.0, 2.0) if f0 * k <= settings.max_hz])
    if ups.size:
        up_score, up_total, up_mask = _score_fundamentals(ups, freqs, amps, settings)
        for i in range(ups.size):
            if up_score[i] >= 0.85 * best_score:
                f0, best_total, best_mask = float(ups[i]), float(up_total[i]), up_mask[i]
                break
    # Refine from the matched, phase-accurate harmonics (low harmonics only so a
    # slightly inharmonic high partial cannot pull the estimate).
    h = np.rint(freqs / f0)
    use = best_mask & (h <= 8) & (h >= 1)
    if np.any(use):
        # Peaks disturbed by a neighbour's leakage show inconsistent
        # instantaneous frequency across their lobe; trust them less.
        weights = amps[use] * (1e-3 + (consistency[use] if consistency is not None else 1.0))
        f0 = float(np.exp(np.average(np.log(freqs[use] / h[use]), weights=weights)))
    return f0, best_total, best_mask


def _analyse_window(
    y_pad: np.ndarray,
    starts_centre: np.ndarray,
    size: int,
    rate: float,
    settings: PitchTrackingSettings,
    harmonic: bool,
) -> _WindowEvidence:
    frames = starts_centre.size
    nfft = int(size * max(1, settings.zero_padding))
    lag = settings.phase_lag_samples if settings.phase_lag_samples > 0 else max(1, size // 4)
    window = np.hanning(size)
    norm = 1.0 / float(window.sum())  # analytic signal: amplitude = |X| / sum(w)
    win_power = float(np.sum(window**2))
    bins = nfft // 2 + 1
    bin_hz = rate / nfft
    lo_bin = max(1, int(math.floor(settings.min_hz * 0.8 / bin_hz)))
    hi_bin = min(bins - 1, int(math.ceil(0.45 * rate / bin_hz)))
    search_hi = hi_bin if harmonic else min(hi_bin, int(math.ceil(settings.max_hz * 1.25 / bin_hz)))
    omega = 2.0 * np.pi * np.arange(bins) / nfft
    peak_floor = 10.0 ** (settings.peak_floor_db / 20.0)

    f0 = np.full(frames, np.nan)
    strength = np.zeros(frames)
    lobe = np.zeros(frames)
    harmonicity = np.zeros(frames)
    rich = np.zeros(frames, dtype=bool)
    energy = np.zeros(frames)
    components: list[list[tuple[float, float, float]]] = [[] for _ in range(frames)]

    chunk = 256
    for c0 in range(0, frames, chunk):
        idx = starts_centre[c0 : c0 + chunk]
        # y_pad is the analytic signal: no negative-frequency image, so low
        # notes stay unbiased even with only ~2 periods in the window.
        cur = _frame_matrix(y_pad, idx - size // 2, size) * window
        prev = _frame_matrix(y_pad, idx - size // 2 - lag, size) * window
        energy[c0 : c0 + idx.size] = np.sum(cur.real * cur.real, axis=1) / win_power
        spec = np.fft.fft(cur, nfft, axis=1)[:, :bins]
        spec_prev = np.fft.fft(prev, nfft, axis=1)[:, :bins]
        mag = np.abs(spec) * norm
        dphi = np.angle(spec * np.conj(spec_prev))
        if lag == 1:
            inst = dphi * rate / (2.0 * np.pi)
        else:
            dev = np.mod(dphi - omega * lag + np.pi, 2.0 * np.pi) - np.pi
            inst = (omega + dev / lag) * rate / (2.0 * np.pi)
        power = mag * mag
        band_power = np.sum(power[:, lo_bin:hi_bin], axis=1)
        peaks = _local_peaks(mag, lo_bin, search_hi)

        for row in range(idx.size):
            frame = c0 + row
            if band_power[row] <= 1e-20:
                continue
            row_mag = mag[row]
            cand = np.flatnonzero(peaks[row])
            if not cand.size:
                continue
            top = float(row_mag[cand].max())
            cand = cand[row_mag[cand] >= top * peak_floor]
            if cand.size > 24:
                cand = cand[np.argsort(-row_mag[cand])[:24]]
                cand.sort()
            amps = row_mag[cand]

            if settings.method == "peak":
                k = int(cand[np.argmax(amps)])
                if not (settings.min_hz <= k * bin_hz <= settings.max_hz * 1.25):
                    continue
                f0[frame] = k * bin_hz
                strength[frame] = row_mag[k]
                lobe[frame] = 1.0
                lobe_power = float(np.sum(power[row, max(0, k - 2 * settings.zero_padding) : k + 2 * settings.zero_padding + 1]))
                harmonicity[frame] = min(1.0, lobe_power / band_power[row])
                components[frame] = [(f0[frame], strength[frame], 1.0)]
                continue

            freqs = inst[row, cand]
            valid = (freqs > 0.0) & np.isfinite(freqs)
            if not np.any(valid):
                continue
            cand, amps, freqs = cand[valid], amps[valid], freqs[valid]
            # Instantaneous-frequency agreement across the main lobe: a single
            # stationary sinusoid yields the same frequency on neighbouring bins.
            left = inst[row, np.maximum(cand - 1, 0)]
            right = inst[row, np.minimum(cand + 1, bins - 1)]
            with np.errstate(divide="ignore", invalid="ignore"):
                spread = np.maximum(
                    np.abs(_cents(np.maximum(left, 1e-6), freqs)),
                    np.abs(_cents(np.maximum(right, 1e-6), freqs)),
                )
            spread = np.where(np.isfinite(spread), spread, 1e4)
            consistency = np.exp(-((spread / 40.0) ** 2))

            lobe_half = settings.zero_padding  # +-1 original bin around the peak

            def lobe_energy(bin_indices: np.ndarray) -> float:
                total = 0.0
                for k in bin_indices:
                    total += float(np.sum(power[row, max(0, k - lobe_half) : k + lobe_half + 1]))
                return total

            if not harmonic:
                in_range = (freqs >= settings.min_hz) & (freqs <= settings.max_hz)
                if not np.any(in_range):
                    continue
                pick = int(np.flatnonzero(in_range)[np.argmax(amps[in_range])])
                f0[frame] = freqs[pick]
                strength[frame] = amps[pick]
                lobe[frame] = consistency[pick]
                harmonicity[frame] = min(1.0, lobe_energy(cand[pick : pick + 1]) / band_power[row])
                components[frame] = [(float(freqs[pick]), float(amps[pick]), float(consistency[pick]))]
                continue

            remaining = np.ones(freqs.size, dtype=bool)
            primary_mask: np.ndarray | None = None
            frame_components: list[tuple[float, float, float]] = []
            strongest = float(amps.max())
            for component in range(settings.max_components):
                if not np.any(remaining):
                    break
                if component > 0 and float(amps[remaining].max()) < 0.2 * strongest:
                    break
                found = _harmonic_search(freqs[remaining], amps[remaining], settings, consistency[remaining])
                if found is None:
                    break
                comp_f0, comp_strength, sub_mask = found
                mask = np.zeros(freqs.size, dtype=bool)
                mask[np.flatnonzero(remaining)[sub_mask]] = True
                # Lobe consistency of the strongest low harmonic of this component.
                h = np.rint(freqs / comp_f0)
                low = mask & (h <= 4)
                ref = int(np.flatnonzero(low if np.any(low) else mask)[np.argmax(amps[low if np.any(low) else mask])])
                frame_components.append((comp_f0, comp_strength, float(consistency[ref])))
                if primary_mask is None:
                    primary_mask = mask
                    low_h = mask & (h >= 2) & (h <= 4)
                    rich[frame] = bool(np.any(amps[low_h] >= 0.1 * float(amps[mask].max())))
                remaining &= ~mask
            if not frame_components:
                continue
            components[frame] = frame_components
            f0[frame], strength[frame], lobe[frame] = frame_components[0]
            harmonicity[frame] = min(1.0, lobe_energy(cand[primary_mask]) / band_power[row])

    return _WindowEvidence(size, size / rate, f0, strength, lobe, harmonicity, rich, energy, components)


def _harmonicity_confidence(harmonicity: float) -> float:
    return float(np.clip((harmonicity - 0.3) / 0.4, 0.0, 1.0))


def _select_windows(
    evidence: list[_WindowEvidence],
    settings: PitchTrackingSettings,
) -> tuple[np.ndarray, np.ndarray]:
    """Per frame: chosen window index and agreement factor (0..1)."""
    frames = evidence[0].f0.size
    chosen = np.full(frames, -1, dtype=np.int64)
    agreement = np.zeros(frames)
    count = len(evidence)
    for frame in range(frames):
        estimates = [ev.f0[frame] for ev in evidence]
        # Adjacent harmonics leak into each other through Hann sidelobes
        # unless the window holds ~4 periods; a pure tone needs only ~2.
        trusted = [
            math.isfinite(f)
            and f * ev.seconds
            >= (settings.min_periods_harmonic if ev.rich[frame] else settings.min_periods)
            for f, ev in zip(estimates, evidence)
        ]
        eligible: list[int] = []
        for i in range(count):
            if not trusted[i]:
                continue
            contradicted = False
            for j in range(i + 1, count):
                if not trusted[j] or evidence[j].lobe[frame] < 0.6:
                    continue
                ratio = estimates[i] / estimates[j]
                k = round(ratio)
                if k >= 2 and abs(1200.0 * math.log2(ratio / k)) <= 50.0:
                    contradicted = True  # a longer window sees a sub-harmonic
                    break
            if not contradicted:
                eligible.append(i)
        pick = -1
        if eligible:
            # Shortest window whose own quality is close to the best one: short
            # windows for clean sweeps, longer ones when harmonics need to be
            # resolved (Hann needs ~4 periods to separate adjacent harmonics).
            quality = [
                evidence[i].lobe[frame] * _harmonicity_confidence(evidence[i].harmonicity[frame])
                for i in eligible
            ]
            best = max(quality)
            pick = next(i for i, q in zip(eligible, quality) if q >= 0.85 * best)
        if pick < 0:
            finite = [i for i in range(count) if math.isfinite(estimates[i])]
            if not finite:
                continue
            pick = finite[-1]
            agreement[frame] = 0.3
        else:
            others = [
                abs(1200.0 * math.log2(estimates[j] / estimates[pick]))
                for j in range(pick + 1, count)
                if trusted[j]
            ]
            if others:
                agreement[frame] = math.exp(-((min(others) / 150.0) ** 2))
            else:
                agreement[frame] = 1.0
        chosen[frame] = pick
    return chosen, agreement


# --------------------------------------------------------------------------
# Linking frames into candidate tracks


def _link_candidates(
    times: np.ndarray,
    components: list[list[tuple[float, float, float]]],
    settings: PitchTrackingSettings,
) -> list[dict[str, list]]:
    tracks: list[dict[str, list]] = []
    active: list[int] = []
    for frame, comps in enumerate(components):
        t = float(times[frame])
        active = [
            tid for tid in active
            if t - tracks[tid]["times"][-1] <= settings.max_link_gap_seconds + 1e-9
        ]
        edges: list[tuple[float, int, int]] = []
        for ci, (hz, _strength, conf, _flags) in enumerate(comps):
            if conf < settings.link_min_confidence:
                continue
            for tid in active:
                track = tracks[tid]
                dt = t - track["times"][-1]
                # Slope allowance only for short gaps; after a longer gap the
                # pitch must be nearly where the track left off.
                limit = settings.link_tolerance_cents + settings.max_slope_cents_per_second * min(dt, 0.004)
                distance = abs(1200.0 * math.log2(hz / track["hz"][-1]))
                if distance <= limit:
                    edges.append((distance, tid, ci))
        edges.sort()
        used_t: set[int] = set()
        used_c: set[int] = set()
        for _distance, tid, ci in edges:
            if tid in used_t or ci in used_c:
                continue
            used_t.add(tid)
            used_c.add(ci)
            hz, strength, conf, flags = comps[ci]
            for key, value in (("times", t), ("hz", hz), ("strength", strength), ("confidence", conf), ("flags", flags)):
                tracks[tid][key].append(value)
        for ci, (hz, strength, conf, flags) in enumerate(comps):
            if ci in used_c or conf < settings.link_min_confidence:
                continue
            tracks.append({"times": [t], "hz": [hz], "strength": [strength], "confidence": [conf], "flags": [flags]})
            active.append(len(tracks) - 1)
    return [
        track for track in tracks
        if track["times"][-1] - track["times"][0] >= settings.min_track_seconds
    ]


def _assign_roles(candidates: list[PitchCandidate]) -> int | None:
    """Primary = lowest-pitched candidate among the strong ones (the kick
    body); others are marked as its harmonics when their frequency ratio stays
    near an integer, otherwise as independent components."""
    if not candidates:
        return None
    top_score = max(c.score for c in candidates)
    strong = [i for i, c in enumerate(candidates) if c.score >= 0.25 * top_score]
    primary = min(strong, key=lambda i: float(np.median(candidates[i].hz)))
    candidates[primary].role = "primary"
    base = candidates[primary]
    for i, candidate in enumerate(candidates):
        if i == primary:
            continue
        common, a, b = np.intersect1d(np.round(candidate.times, 7), np.round(base.times, 7), return_indices=True)
        if common.size >= 3:
            ratio = candidate.hz[a] / base.hz[b]
            median = float(np.median(ratio))
            k = int(round(median))
            spread = float(np.percentile(np.abs(1200.0 * np.log2(ratio / max(k, 1))), 75))
            if k >= 2 and abs(1200.0 * math.log2(median / k)) <= 30.0 and spread <= 40.0:
                candidate.role = "harmonic"
                candidate.harmonic_of = base.id
                candidate.harmonic_number = k
                continue
        candidate.role = "independent"
    return primary


# --------------------------------------------------------------------------
# Public entry point


def analyze_pitch_region(
    samples: np.ndarray,
    sample_rate: int,
    start: float,
    end: float,
    settings: PitchTrackingSettings | None = None,
) -> PitchTrackingResult:
    """Track kick pitch in ``[start, end]`` seconds of ``samples``."""
    options = settings or PitchTrackingSettings()
    if options.method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    if options.min_hz <= 0 or options.max_hz <= options.min_hz:
        raise ValueError("invalid frequency range")
    if options.hop_seconds <= 0:
        raise ValueError("hop_seconds must be positive")
    started = time.perf_counter()
    sr = int(sample_rate)
    y = _mono(samples)
    start = max(0.0, float(start))
    end = max(start, float(end))
    if end - start > options.max_region_seconds:
        raise ValueError(f"region longer than {options.max_region_seconds:g} s")

    factor, rate = _analysis_rate(sr, options)
    if options.method in ("peak", "phase"):
        window_seconds: tuple[float, ...] = (options.single_window_seconds,)
    else:
        window_seconds = tuple(sorted(options.window_seconds))
    sizes = [max(16, int(round(s * rate / 2.0)) * 2) for s in window_seconds]
    max_size = max(sizes)
    lag = options.phase_lag_samples if options.phase_lag_samples > 0 else max_size // 4
    margin = (max_size / 2 + lag + 64) / rate + 0.02

    excerpt, first_sample = _excerpt(y, sr, start, end, margin)
    x = _decimate(excerpt, factor)
    t0 = first_sample / sr  # time of x[0]
    pad = max_size + lag + 2
    xa = _analytic(x)
    x_pad = np.concatenate((np.zeros(pad, dtype=complex), xa, np.zeros(pad, dtype=complex)))

    hop = max(1, int(round(options.hop_seconds * rate)))
    first_centre = int(math.ceil((start - t0) * rate - 1e-9))
    last_centre = int(math.floor((end - t0) * rate + 1e-9))
    centres = np.arange(first_centre, last_centre + 1, hop, dtype=np.int64)
    if not centres.size:
        centres = np.array([first_centre], dtype=np.int64)
    times = t0 + centres / rate
    frames = centres.size

    harmonic = options.method == "harmonic"
    evidence = [
        _analyse_window(x_pad, centres + pad, size, rate, options, harmonic)
        for size in sizes
    ]
    if len(evidence) > 1:
        chosen, agreement = _select_windows(evidence, options)
    else:
        chosen = np.where(np.isfinite(evidence[0].f0), 0, -1)
        agreement = np.ones(frames)

    # Energy gate from the shortest window (best time resolution).
    short_energy = evidence[0].energy
    peak_energy = float(short_energy.max()) if frames else 0.0
    with np.errstate(divide="ignore"):
        level_db = 10.0 * np.log10(np.maximum(short_energy, 1e-30) / max(peak_energy, 1e-30))
    low_energy = (level_db < options.energy_floor_db) | (short_energy < 1e-12) | (peak_energy < 1e-12)
    energy_conf = np.clip((level_db - options.energy_floor_db) / 15.0, 0.0, 1.0)
    energy_conf[low_energy] = 0.0

    real_pad = x_pad.real
    cumulative_energy = np.concatenate(([0.0], np.cumsum(real_pad * real_pad)))
    onset_ratio = 10.0 ** (-options.onset_dynamic_db / 10.0)

    out_hz = np.full(frames, np.nan)
    out_strength = np.zeros(frames)
    out_conf = np.zeros(frames)
    out_flags = np.zeros(frames, dtype=np.int64)
    out_window = np.zeros(frames)
    frame_components: list[list[tuple[float, float, float, int]]] = [[] for _ in range(frames)]

    for frame in range(frames):
        flags = 0
        if low_energy[frame]:
            flags |= FLAG_LOW_ENERGY
        w = int(chosen[frame])
        if w < 0:
            out_flags[frame] = flags | FLAG_NO_PITCH
            continue
        ev = evidence[w]
        size = ev.size
        centre = int(centres[frame] + pad)
        transient = _transient_in_window(cumulative_energy, centre, size, onset_ratio)
        if transient:
            flags |= FLAG_ONSET
        if ev.lobe[frame] < 0.5:
            flags |= FLAG_PHASE_INCONSISTENT
        if agreement[frame] < 0.5:
            flags |= FLAG_WINDOW_DISAGREE
        harm_conf = _harmonicity_confidence(ev.harmonicity[frame])
        base_conf = energy_conf[frame] * harm_conf * agreement[frame] * (0.25 if transient else 1.0)
        comps = []
        for ci, (hz, strength, lobe_c) in enumerate(ev.components[frame]):
            conf = base_conf * lobe_c
            if ci > 0:
                conf *= min(1.0, strength / max(ev.strength[frame], 1e-12) * 2.0)
            comps.append((hz, strength, float(np.clip(conf, 0.0, 1.0)), flags))
        frame_components[frame] = comps
        out_hz[frame] = ev.f0[frame]
        out_strength[frame] = ev.strength[frame]
        out_conf[frame] = comps[0][2] if comps else 0.0
        out_flags[frame] = flags
        out_window[frame] = ev.seconds

    # Isolated octave / harmonic errors: compare each estimate with the median
    # of its confident neighbours.  Outliers are kept but distrusted, never
    # replaced by an invented value.
    usable = np.isfinite(out_hz) & (out_conf >= options.link_min_confidence)
    log_hz = np.log2(np.where(np.isfinite(out_hz), out_hz, 1.0))
    radius = options.outlier_radius_seconds
    jump_frames = []
    for frame in np.flatnonzero(usable):
        lo = int(np.searchsorted(times, times[frame] - radius, side="left"))
        hi = int(np.searchsorted(times, times[frame] + radius, side="right"))
        neighbours = np.flatnonzero(usable[lo:hi]) + lo
        neighbours = neighbours[neighbours != frame]
        if neighbours.size < 3:
            continue
        deviation = 1200.0 * abs(log_hz[frame] - float(np.median(log_hz[neighbours])))
        if deviation > options.outlier_cents:
            jump_frames.append(frame)
    for frame in jump_frames:
        out_flags[frame] |= FLAG_PITCH_JUMP
        out_conf[frame] *= 0.1
        if frame_components[frame]:
            hz, strength, conf, flags = frame_components[frame][0]
            frame_components[frame][0] = (hz, strength, conf * 0.1, flags | FLAG_PITCH_JUMP)

    max_strength = float(out_strength.max()) if frames else 0.0
    scale = 1.0 / max_strength if max_strength > 0 else 0.0
    out_strength *= scale
    frame_components = [
        [(hz, s * scale, c, f) for hz, s, c, f in comps] for comps in frame_components
    ]

    linked = _link_candidates(times, frame_components, options)
    candidates = [
        PitchCandidate(
            id=i,
            role="independent",
            times=np.asarray(track["times"]),
            hz=np.asarray(track["hz"]),
            strength=np.asarray(track["strength"]),
            confidence=np.asarray(track["confidence"]),
            flags=np.asarray(track["flags"], dtype=np.int64),
        )
        for i, track in enumerate(linked)
    ]
    primary = _assign_roles(candidates)

    elapsed = time.perf_counter() - started
    return PitchTrackingResult(
        start=start,
        end=end,
        method=options.method,
        frames=PitchFrames(times, out_hz, out_strength, out_conf, out_flags, out_window),
        candidates=candidates,
        primary_index=primary,
        stats={
            "analysisSeconds": elapsed,
            "frameCount": int(frames),
            "hopSeconds": hop / rate,
            "analysisRate": rate,
            "windowSeconds": [s / rate for s in sizes],
            "phaseLagSamples": lag,
            "candidateCount": len(candidates),
        },
    )

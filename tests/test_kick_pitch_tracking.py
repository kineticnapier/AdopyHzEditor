"""Kick pitch tracking prototype (Hardstyle Piep / Zaag kicks).

All signals are synthetic with an exactly known instantaneous frequency so the
estimator error can be measured in cents.
"""

from __future__ import annotations

import unittest

import numpy as np

from core.pitch_tracking import (
    FLAG_LOW_ENERGY,
    FLAG_ONSET,
    PitchTrackingSettings,
    analyze_pitch_region,
)


SR = 44_100


def _synth(freq: np.ndarray, harmonics: dict[int, float] | None = None, sr: int = SR) -> np.ndarray:
    phase = 2.0 * np.pi * np.cumsum(freq) / sr
    out = np.zeros_like(freq)
    for h, amp in (harmonics or {1: 1.0}).items():
        out += amp * np.sin(h * phase)
    return out


def _time(seconds: float, sr: int = SR) -> np.ndarray:
    return np.arange(int(round(seconds * sr))) / sr


def _cents(estimate: np.ndarray, truth: np.ndarray) -> np.ndarray:
    return 1200.0 * np.abs(np.log2(estimate / truth))


def _primary_errors(result, truth_fn, *, min_confidence=0.5, skip_edges=0.03):
    frames = result.frames
    t = frames.times
    keep = (
        np.isfinite(frames.hz)
        & (frames.confidence >= min_confidence)
        & (t >= result.start + skip_edges)
        & (t <= result.end - skip_edges)
    )
    errors = _cents(frames.hz[keep], truth_fn(t[keep]))
    return errors, keep


class KickPitchSyntheticTests(unittest.TestCase):
    def test_constant_tone_phase_beats_raw_fft_peak(self):
        f = 112.3  # deliberately between FFT bins
        y = _synth(np.full(int(0.5 * SR), f))
        truth = lambda t: np.full_like(t, f)
        errors = {}
        for method in ("peak", "phase", "multiwindow", "harmonic"):
            result = analyze_pitch_region(y, SR, 0.0, 0.5, PitchTrackingSettings(method=method))
            err, keep = _primary_errors(result, truth)
            self.assertGreater(keep.mean(), 0.8, method)
            errors[method] = float(np.median(err))
        self.assertGreater(errors["peak"], 5.0)
        for method in ("phase", "multiwindow", "harmonic"):
            self.assertLess(errors[method], 1.0, (method, errors))

    def test_linear_hz_drop_150_to_50(self):
        duration = 0.25
        t = _time(duration)
        f_fn = lambda tt: 150.0 - 100.0 * np.clip(tt / duration, 0, 1)
        y = _synth(f_fn(t))
        result = analyze_pitch_region(y, SR, 0.0, duration, PitchTrackingSettings())
        err, keep = _primary_errors(result, f_fn)
        self.assertGreater(keep.mean(), 0.7)
        self.assertLess(float(np.percentile(err, 90)), 15.0)

    def test_exponential_kick_drop_with_attack_is_tracked_and_onset_flagged(self):
        duration = 0.35
        t = _time(duration)
        onset = 0.02
        local = np.clip(t - onset, 0.0, None)
        f_fn = lambda tt: 45.0 + 120.0 * np.exp(-np.clip(tt - onset, 0, None) / 0.05)
        env = (t >= onset) * np.minimum(1.0, local / 0.002) * np.exp(-local / 0.4)
        y = env * _synth(f_fn(t))
        result = analyze_pitch_region(y, SR, 0.0, duration, PitchTrackingSettings())
        err, keep = _primary_errors(result, f_fn, skip_edges=0.03)
        self.assertGreater(keep.sum(), 150)
        self.assertLess(float(np.median(err)), 8.0)
        self.assertLess(float(np.percentile(err, 90)), 25.0)
        # Silence before the hit and the attack itself must not be trusted.
        frames = result.frames
        before = frames.times < onset - 0.01
        self.assertTrue(np.all(frames.confidence[before] < 0.2))
        self.assertTrue(np.all(frames.flags[before] & FLAG_LOW_ENERGY))
        attack = (frames.times >= onset - 0.004) & (frames.times <= onset + 0.004)
        self.assertTrue(np.all(frames.flags[attack] & (FLAG_ONSET | FLAG_LOW_ENERGY)))
        self.assertTrue(np.all(frames.confidence[attack] < 0.5))

    def test_piep_strong_880_partial_is_not_an_independent_fundamental(self):
        f0 = 73.0
        y = _synth(np.full(int(0.4 * SR), f0), {1: 1.0, 2: 0.5, 3: 0.3, 4: 0.2, 12: 1.6})
        result = analyze_pitch_region(y, SR, 0.0, 0.4, PitchTrackingSettings())
        err, keep = _primary_errors(result, lambda t: np.full_like(t, f0))
        self.assertGreater(keep.mean(), 0.8)
        self.assertLess(float(np.median(err)), 2.0)
        primary = result.candidates[result.primary_index]
        self.assertLess(abs(1200 * np.log2(np.nanmedian(primary.hz) / f0)), 5.0)
        for candidate in result.candidates:
            if candidate.role == "independent":
                self.assertLess(float(np.nanmedian(candidate.hz)), 300.0)

    def test_gliding_piep_follows_fundamental_not_harmonic(self):
        duration = 0.3
        t = _time(duration)
        f_fn = lambda tt: 50.0 + 100.0 * np.exp(-tt / 0.08)
        y = _synth(f_fn(t), {1: 1.0, 2: 0.4, 3: 0.25, 12: 1.4})
        result = analyze_pitch_region(y, SR, 0.0, duration, PitchTrackingSettings())
        err, keep = _primary_errors(result, f_fn)
        self.assertGreater(keep.mean(), 0.6)
        self.assertLess(float(np.median(err)), 8.0)
        self.assertLess(float(np.percentile(err, 90)), 30.0)

    def test_two_unrelated_tones_become_two_candidates(self):
        n = int(0.4 * SR)
        y = _synth(np.full(n, 100.0)) + 0.7 * _synth(np.full(n, 317.0))
        result = analyze_pitch_region(y, SR, 0.0, 0.4, PitchTrackingSettings())
        medians = sorted(
            float(np.nanmedian(c.hz))
            for c in result.candidates
            if c.role in {"primary", "independent"} and c.duration >= 0.2
        )
        self.assertEqual(len(medians), 2, medians)
        self.assertLess(abs(1200 * np.log2(medians[0] / 100.0)), 5.0)
        self.assertLess(abs(1200 * np.log2(medians[1] / 317.0)), 5.0)

    def test_tone_in_noise_and_pure_noise(self):
        rng = np.random.default_rng(1234)
        n = int(0.5 * SR)
        tone = _synth(np.full(n, 110.0))
        noise = rng.standard_normal(n)
        noise *= np.sqrt(np.mean(tone**2) / np.mean(noise**2)) / 2.0  # +6 dB SNR
        result = analyze_pitch_region(tone + noise, SR, 0.0, 0.5, PitchTrackingSettings())
        err, keep = _primary_errors(result, lambda t: np.full_like(t, 110.0))
        self.assertGreater(keep.mean(), 0.5)
        self.assertLess(float(np.median(err)), 10.0)

        pure = analyze_pitch_region(rng.standard_normal(n), SR, 0.0, 0.5, PitchTrackingSettings())
        self.assertLess(float(np.mean(pure.frames.confidence >= 0.5)), 0.1)

    def test_heavy_distortion_zaag_tracks_fundamental(self):
        duration = 0.3
        t = _time(duration)
        f_fn = lambda tt: 55.0 + 65.0 * np.exp(-tt / 0.07)
        y = np.tanh(6.0 * _synth(f_fn(t)))
        result = analyze_pitch_region(y, SR, 0.0, duration, PitchTrackingSettings())
        err, keep = _primary_errors(result, f_fn)
        self.assertGreater(keep.mean(), 0.6)
        self.assertLess(float(np.median(err)), 10.0)

    def test_silence_returns_no_candidates(self):
        result = analyze_pitch_region(np.zeros(int(0.2 * SR)), SR, 0.0, 0.2, PitchTrackingSettings())
        self.assertEqual(result.candidates, [])
        self.assertTrue(np.all(result.frames.confidence == 0.0))

    def test_region_inside_longer_audio_uses_absolute_times(self):
        y = _synth(np.full(int(2.0 * SR), 90.0))
        result = analyze_pitch_region(y, SR, 1.2, 1.5, PitchTrackingSettings(hop_seconds=0.002))
        self.assertAlmostEqual(float(result.frames.times[0]), 1.2, delta=0.002)
        self.assertLessEqual(float(result.frames.times[-1]), 1.5 + 1e-9)
        self.assertLess(float(np.mean(np.diff(result.frames.times))), 0.0025)
        err, keep = _primary_errors(result, lambda t: np.full_like(t, 90.0), skip_edges=0.0)
        self.assertGreater(keep.mean(), 0.9)  # context outside the region is used
        payload = result.to_dict()
        self.assertIn("frames", payload)
        self.assertIn("candidates", payload)
        self.assertIsInstance(payload["frames"]["hz"][0], (float, type(None)))


if __name__ == "__main__":
    unittest.main()

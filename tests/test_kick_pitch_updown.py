"""Zaag kicks whose pitch goes up and down (bends, steps, vibrato).

Synthetic signals with a known instantaneous frequency, heavily distorted
like a Zaag kick.
"""

from __future__ import annotations

import unittest

import numpy as np

from core.pitch_tracking import FLAG_NO_PITCH, PitchTrackingSettings, analyze_pitch_region


SR = 44_100


def _zaag(freq_fn, seconds: float) -> np.ndarray:
    t = np.arange(int(round(seconds * SR))) / SR
    phase = 2.0 * np.pi * np.cumsum(freq_fn(t)) / SR
    return np.tanh(6.0 * np.sin(phase))


def _glide(points):
    ts = np.array([p[0] for p in points])
    cents = np.log2(np.array([p[1] for p in points]))
    return lambda t: 2.0 ** np.interp(t, ts, cents)


def _steps(points):
    ts = np.array([p[0] for p in points])
    hz = np.array([p[1] for p in points], dtype=float)
    return lambda t: hz[np.clip(np.searchsorted(ts, t, side="right") - 1, 0, hz.size - 1)]


def _primary(result):
    assert result.primary_index is not None
    return result.candidates[result.primary_index]


def _coverage(candidate, seconds: float, min_confidence: float = 0.5) -> float:
    confident = candidate.confidence >= min_confidence
    return float(np.sum(confident)) * 0.001 / seconds  # 1 ms hop


def _median_error(candidate, freq_fn, min_confidence: float = 0.5) -> float:
    keep = candidate.confidence >= min_confidence
    return float(np.median(1200.0 * np.abs(np.log2(candidate.hz[keep] / freq_fn(candidate.times[keep])))))


class StepsJoinIntoOneBodyTests(unittest.TestCase):
    def test_pitch_steps_become_one_primary_candidate(self):
        freq = _steps([(0.0, 55.0), (0.1, 110.0), (0.2, 55.0)])
        result = analyze_pitch_region(_zaag(freq, 0.3), SR, 0.0, 0.3, PitchTrackingSettings())
        self.assertEqual(len(result.candidates), 1)
        body = _primary(result)
        self.assertEqual(result.primary_index, 0)
        self.assertEqual(body.id, 0)
        self.assertTrue(np.all(np.diff(body.times) > 0))
        # Both the low and the high part are in the body.
        self.assertLess(float(body.hz.min()), 60.0)
        self.assertGreater(float(body.hz.max()), 100.0)
        self.assertGreater(_coverage(body, 0.3), 0.6)
        self.assertLess(_median_error(body, freq), 5.0)

    def test_simultaneous_tone_stays_a_separate_candidate(self):
        t = np.arange(int(0.4 * SR)) / SR
        y = _zaag(lambda tt: np.full_like(tt, 55.0), 0.4) + 0.5 * np.sin(2 * np.pi * 317.0 * t)
        result = analyze_pitch_region(y, SR, 0.0, 0.4, PitchTrackingSettings())
        medians = sorted(float(np.median(c.hz)) for c in result.candidates if c.duration >= 0.2)
        self.assertGreaterEqual(len(medians), 2, medians)
        self.assertLess(abs(1200 * np.log2(_primary(result).hz.mean() / 55.0)), 20.0)


class CycleMethodTests(unittest.TestCase):
    def settings(self, **kw):
        return PitchTrackingSettings(method="cycle", **kw)

    def test_up_and_down_glide(self):
        freq = _glide([(0, 55), (0.08, 80), (0.16, 49), (0.24, 65), (0.32, 55)])
        result = analyze_pitch_region(_zaag(freq, 0.32), SR, 0.0, 0.32, self.settings())
        body = _primary(result)
        self.assertGreater(_coverage(body, 0.32), 0.85)
        self.assertLess(_median_error(body, freq), 3.0)

    def test_fast_vibrato_is_followed_better_than_by_windows(self):
        freq = lambda t: 65.0 * 2.0 ** (3.0 / 12.0 * np.sin(2.0 * np.pi * 12.0 * t))
        y = _zaag(freq, 0.4)
        cycle = _primary(analyze_pitch_region(y, SR, 0.0, 0.4, self.settings()))
        windowed = _primary(analyze_pitch_region(y, SR, 0.0, 0.4, PitchTrackingSettings()))
        self.assertGreater(_coverage(cycle, 0.4), 0.9)
        self.assertGreater(_coverage(cycle, 0.4), _coverage(windowed, 0.4) + 0.3)
        self.assertLess(_median_error(cycle, freq), _median_error(windowed, freq))

    def test_pitch_steps(self):
        freq = _steps([(0.0, 55.0), (0.07, 73.4), (0.14, 49.0), (0.21, 65.4)])
        result = analyze_pitch_region(_zaag(freq, 0.28), SR, 0.0, 0.28, self.settings())
        self.assertEqual(len(result.candidates), 1)
        body = _primary(result)
        self.assertGreater(_coverage(body, 0.28), 0.85)
        self.assertLess(_median_error(body, freq), 5.0)

    def test_noise_and_silence_have_no_confident_pitch(self):
        rng = np.random.default_rng(7)
        noise = analyze_pitch_region(rng.standard_normal(int(0.3 * SR)), SR, 0.0, 0.3, self.settings())
        self.assertLess(float(np.mean(noise.frames.confidence >= 0.5)), 0.2)
        silence = analyze_pitch_region(np.zeros(int(0.2 * SR)), SR, 0.0, 0.2, self.settings())
        self.assertEqual(silence.candidates, [])
        self.assertTrue(np.all(silence.frames.flags & FLAG_NO_PITCH))

    def test_region_inside_longer_audio_and_payload(self):
        y = _zaag(lambda t: np.full_like(t, 90.0), 2.0)
        result = analyze_pitch_region(y, SR, 1.2, 1.5, self.settings())
        self.assertAlmostEqual(float(result.frames.times[0]), 1.2, delta=0.001)
        self.assertLessEqual(float(result.frames.times[-1]), 1.5 + 1e-9)
        body = _primary(result)
        self.assertLess(_median_error(body, lambda t: np.full_like(t, 90.0)), 1.0)
        payload = result.to_dict()
        self.assertEqual(payload["method"], "cycle")
        self.assertGreater(payload["stats"]["cycleCount"], 20)


if __name__ == "__main__":
    unittest.main()

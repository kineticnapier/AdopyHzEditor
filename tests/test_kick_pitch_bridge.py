"""Kick pitch prototype: Bridge API and Curve Note conversion."""

from __future__ import annotations

import unittest

import numpy as np

from core.note_model import hz_to_midi
from web.backend import Bridge
from web.kick_pitch import fit_curve_segments


SR = 44_100


def _kick(duration: float = 0.4, onset: float = 0.05) -> tuple[np.ndarray, callable]:
    t = np.arange(int(duration * SR)) / SR
    local = np.clip(t - onset, 0.0, None)
    f_fn = lambda tt: 45.0 + 110.0 * np.exp(-np.clip(tt - onset, 0, None) / 0.06)
    env = (t >= onset) * np.minimum(1.0, local / 0.002) * np.exp(-local / 0.5)
    phase = 2 * np.pi * np.cumsum(f_fn(t)) / SR
    y = env * (np.sin(phase) + 0.4 * np.sin(2 * phase) + 1.2 * np.sin(12 * phase))
    return y.astype(np.float32), f_fn


def _bridge_with_audio(samples: np.ndarray) -> Bridge:
    bridge = Bridge()
    with bridge.player.lock:
        bridge.player.audio = np.asarray(samples, dtype=np.float32)[:, None]
        bridge.player.sr = SR
    bridge.audio_path = "synthetic-kick.wav"
    bridge.duration = len(samples) / SR
    return bridge


class CurveSegmentFitTests(unittest.TestCase):
    def test_exponential_sweep_is_split_until_within_tolerance(self):
        t = np.linspace(0.0, 0.3, 301)
        midis = np.array([hz_to_midi(45.0 + 110.0 * np.exp(-x / 0.06)) for x in t])
        segments = fit_curve_segments(t, midis, np.ones_like(t), max_error_cents=5.0)
        self.assertGreater(len(segments), 1)
        self.assertLess(len(segments), 12)
        self.assertTrue(all(error <= 5.0 for *_rest, error in segments))
        # Contiguous: every segment starts where the previous one ended.
        for (a0, b0, _c0, _e0), (a1, _b1, _c1, _e1) in zip(segments, segments[1:]):
            self.assertEqual(b0, a1)
        self.assertEqual(segments[0][0], 0)
        self.assertEqual(segments[-1][1], t.size - 1)

    def test_constant_pitch_is_one_segment(self):
        t = np.linspace(0.0, 0.2, 201)
        segments = fit_curve_segments(t, np.full_like(t, 40.0), np.ones_like(t))
        self.assertEqual(len(segments), 1)


class KickPitchBridgeTests(unittest.TestCase):
    def test_analyze_then_convert_primary_to_curve_notes_with_undo(self):
        y, f_fn = _kick()
        bridge = _bridge_with_audio(y)
        payload = bridge.analyze_kick_pitch(0.0, 0.4)
        self.assertTrue(payload["available"])
        primary = payload["candidates"][payload["primaryIndex"]]
        self.assertEqual(primary["role"], "primary")
        self.assertLess(primary["medianHz"], 120.0)  # body, not the 12th harmonic
        self.assertFalse(
            any(c["role"] == "independent" and c["medianHz"] > 300 and c["duration"] > 0.05 for c in payload["candidates"])
        )

        result = bridge.create_notes_from_kick_pitch([primary["id"]], 0.5, 5.0)
        self.assertTrue(result["changed"])
        notes = [bridge.notes[i] for i in result["indices"]]
        self.assertTrue(notes)
        self.assertTrue(all(n.kind == "curve" for n in notes))
        self.assertLessEqual(result["maxErrorCents"], 5.0)
        # Curve Notes reproduce the true sweep where they exist.
        errors = []
        for note in notes:
            for u in np.linspace(0.0, 1.0, 9):
                tt = note.start + u * note.duration
                errors.append(abs(note.midi_at(u) - hz_to_midi(float(f_fn(np.array([tt]))[0]))) * 100.0)
        self.assertLess(float(np.median(errors)), 10.0)
        self.assertLess(float(np.percentile(errors, 90)), 30.0)

        bridge.undo()
        self.assertEqual(bridge.notes, [])

    def test_result_is_cleared_with_analysis_state_and_requires_audio(self):
        bridge = Bridge()
        self.assertFalse(bridge.analyze_kick_pitch(0.0, 0.3)["available"])
        y, _ = _kick()
        bridge = _bridge_with_audio(y)
        bridge.analyze_kick_pitch(0.0, 0.4)
        self.assertIsNotNone(bridge.kick_pitch_result)
        bridge._clear_analysis_state()
        self.assertIsNone(bridge.kick_pitch_result)
        result = bridge.create_notes_from_kick_pitch([0])
        self.assertFalse(result["changed"])

    def test_rejects_too_long_region(self):
        y, _ = _kick()
        bridge = _bridge_with_audio(np.tile(y, 30))
        self.assertFalse(bridge.analyze_kick_pitch(0.0, 11.0)["available"])


if __name__ == "__main__":
    unittest.main()

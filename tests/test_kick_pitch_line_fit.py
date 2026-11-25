"""Kick pitch "one line" fit: bridge holes, drop stray points, cap the notes."""

from __future__ import annotations

import unittest

import numpy as np

from core.note_model import Note, hz_to_midi
from web.kick_pitch import FIT_MODES, _bezier_midis, fit_one_line
from tests.test_kick_pitch_bridge import _bridge_with_audio, _kick


def _sweep(t: np.ndarray) -> np.ndarray:
    return np.array([hz_to_midi(45.0 + 110.0 * np.exp(-x / 0.06)) for x in t])


def _broken_sweep():
    """A falling sweep measured in short pieces, with an octave slip."""
    t = np.arange(0.0, 0.3, 0.001)
    keep = (np.floor(t / 0.012) % 2 == 0) | (t > 0.2)  # 12 ms on, 12 ms off
    m = _sweep(t)
    m[(t > 0.15) & (t < 0.153)] += 12.0  # stray octave frames
    return t[keep], m[keep]


def _drawn(stretches, times: np.ndarray) -> np.ndarray:
    """Pitch of the fitted line at ``times`` (NaN outside it)."""
    out = np.full(times.shape, np.nan)
    for grid, _strength, segments in stretches:
        for lo, hi, controls, _error in segments:
            inside = (times >= grid[lo]) & (times <= grid[hi])
            if np.any(inside):
                span = np.concatenate(([grid[lo]], times[inside], [grid[hi]]))
                out[inside] = _bezier_midis(span, controls)[1:-1]
    return out


class FitOneLineTests(unittest.TestCase):
    def test_broken_sweep_becomes_one_joined_line_without_swinging_through_holes(self):
        t, m = _broken_sweep()
        stretches = fit_one_line(t, m, np.ones_like(t), max_error_cents=30.0)
        self.assertEqual(len(stretches), 1)
        grid, _strength, segments = stretches[0]
        self.assertAlmostEqual(grid[0], t[0])
        self.assertAlmostEqual(grid[-1], t[-1])
        for (_a0, b0, *_), (a1, *_rest) in zip(segments, segments[1:]):
            self.assertEqual(b0, a1)  # joined, no pitch step
        # The line follows the true sweep inside the holes too; the octave slip is ignored.
        dense = np.arange(0.002, 0.298, 0.001)
        error = np.abs(_drawn(stretches, dense) - _sweep(dense)) * 100.0
        self.assertLess(float(np.max(error)), 60.0)
        self.assertLess(float(np.median(error)), 20.0)

    def test_cap_of_one_gives_a_single_curve(self):
        t, m = _broken_sweep()
        (grid, _strength, segments), = fit_one_line(t, m, np.ones_like(t), max_segments=1)
        self.assertEqual(len(segments), 1)
        self.assertEqual((segments[0][0], segments[0][1]), (0, grid.size - 1))

    def test_long_silence_still_splits(self):
        t = np.concatenate((np.arange(0.0, 0.1, 0.001), np.arange(0.4, 0.5, 0.001)))
        stretches = fit_one_line(t, np.full_like(t, 30.0), np.ones_like(t))
        self.assertEqual(len(stretches), 2)


class LineModeBridgeTests(unittest.TestCase):
    def test_line_mode_gives_fewer_joined_notes_than_exact(self):
        y, _ = _kick()
        bridge = _bridge_with_audio(y)
        payload = bridge.analyze_kick_pitch(0.0, 0.4)
        primary = payload["candidates"][payload["primaryIndex"]]["id"]
        exact = bridge.create_notes_from_kick_pitch([primary], 0.5, 5.0, "exact")
        bridge.undo()
        line = bridge.create_notes_from_kick_pitch([primary], 0.5, 30.0, "line")
        self.assertTrue(line["changed"])
        notes: list[Note] = [bridge.notes[i] for i in line["indices"]]
        self.assertLessEqual(len(notes), len(exact["indices"]))
        for a, b in zip(notes, notes[1:]):
            self.assertAlmostEqual(a.end, b.start, places=6)
            self.assertAlmostEqual(a.end_midi, b.midi, places=6)
        bridge.undo()
        single = bridge.create_notes_from_kick_pitch([primary], 0.5, 30.0, "line", 1)
        self.assertEqual(len(single["indices"]), 1)

    def test_unknown_fit_mode_is_rejected(self):
        self.assertEqual(FIT_MODES, ("line", "exact"))
        y, _ = _kick()
        bridge = _bridge_with_audio(y)
        bridge.analyze_kick_pitch(0.0, 0.4)
        with self.assertRaises(ValueError):
            bridge.create_notes_from_kick_pitch([0], 0.5, 5.0, "smooth")


if __name__ == "__main__":
    unittest.main()

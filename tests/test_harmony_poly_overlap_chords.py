from __future__ import annotations

import unittest

from core.note_model import Note
from exporters.adofai import (
    _harmony_poly_overlap_units,
    build_adofai_level,
    build_harmony_ratio_polyrhythm_events,
    just_ratio_for_semitones,
)
from web_ui import Bridge

BPM = 1600.0
CYCLE = 720.0 * 60.0 / (180.0 * BPM)  # one ratio-polyrhythm cycle at the default cycle angle


def _chord(start: float, end: float, *midis: float) -> list[Note]:
    return [Note(start, end, m) for m in midis]


def _events(notes: list[Note], *, source: str = "overlap", cycle_mode: str = "fixed"):
    return build_harmony_ratio_polyrhythm_events(
        notes,
        harmony_mode="fifth +7",
        play_bpm=BPM,
        harmony_poly_cycle_mode=cycle_mode,
        harmony_poly_chord_source=source,
    )


class JustRatioTests(unittest.TestCase):
    def test_equal_tempered_steps_snap_to_just_ratios(self):
        self.assertAlmostEqual(just_ratio_for_semitones(4), 5 / 4)
        self.assertAlmostEqual(just_ratio_for_semitones(7.1), 3 / 2)
        self.assertAlmostEqual(just_ratio_for_semitones(16), 5 / 2)  # major tenth = octave + third

    def test_far_off_intervals_keep_their_exact_ratio(self):
        self.assertAlmostEqual(just_ratio_for_semitones(4.5), 2 ** (4.5 / 12))


class OverlapUnitTests(unittest.TestCase):
    def test_groups_and_active_sets(self):
        notes = _chord(0.0, 1.0, 60, 64) + [Note(1.0, 2.0, 65), Note(3.0, 4.0, 60)]
        units = _harmony_poly_overlap_units(notes)
        self.assertEqual(len(units), 2)  # the 1 s gap splits the groups
        first = units[0]
        self.assertAlmostEqual(first["note"].start, 0.0)
        self.assertAlmostEqual(first["note"].end, 2.0)
        self.assertEqual([len(seg[2]) for seg in first["segments"]], [2, 1])


class OverlapChordPolyrhythmTests(unittest.TestCase):
    def test_chord_ratios_come_from_overlapping_notes(self):
        notes = (
            _chord(0.0, 2 * CYCLE, 60, 64, 67)  # C E G -> 4:5:6
            + _chord(2 * CYCLE, 4 * CYCLE, 62, 65, 69)  # D F A -> 10:12:15
            + [Note(4 * CYCLE, 5 * CYCLE, 60)]  # single note -> preset fifth 2:3
        )
        events, _dup, _specs, stats = _events(notes)
        self.assertEqual(stats["chord_source"], "overlap")
        self.assertEqual(stats["chord_sequence"], "4:5:6 > 10:12:15 > 2:3")
        self.assertEqual(stats["chord_changes"], 2)
        by_cycle = {}
        for e in events:
            by_cycle.setdefault(e["poly_cycle_index"], e["poly_ratio_text"])
        self.assertEqual([by_cycle[i] for i in range(5)], ["4:5:6", "4:5:6", "10:12:15", "10:12:15", "2:3"])

    def test_preset_source_keeps_the_old_per_note_behaviour(self):
        notes = _chord(0.0, 2 * CYCLE, 60, 64, 67)
        _events_list, _dup, _specs, stats = _events(notes, source="preset")
        self.assertEqual(stats["chord_source"], "preset")
        self.assertEqual(stats["chord_sequence"], "2:3")

    def test_chord_change_waits_for_the_cycle_boundary(self):
        notes = _chord(0.0, 1.5 * CYCLE, 60, 64, 67) + [Note(1.5 * CYCLE, 3 * CYCLE, 60)]
        events, *_ = _events(notes)
        # Cycle 1 starts while C E G still sounds, so it stays 4:5:6 to its end.
        cycle1 = [e for e in events if e["poly_cycle_index"] == 1]
        self.assertTrue(cycle1)
        self.assertTrue(all(e["poly_ratio_text"] == "4:5:6" for e in cycle1))
        self.assertTrue(any(e["time"] > 1.5 * CYCLE for e in cycle1))
        self.assertTrue(all(e["poly_ratio_text"] == "2:3" for e in events if e["poly_cycle_index"] == 2))

    def test_auto_cycle_keeps_timing_per_shape(self):
        notes = _chord(0.0, 2 * CYCLE, 60, 64, 67) + [Note(2 * CYCLE, 4 * CYCLE, 60)]
        events, _dup, _specs, stats = _events(notes, cycle_mode="auto")
        bpms = {round(e["poly_play_bpm"], 6) for e in events}
        self.assertEqual(len(bpms), 2)  # each chord shape runs at its own speed
        self.assertAlmostEqual(stats["effective_play_bpm"], events[0]["poly_play_bpm"])
        for cur, nxt in zip(events, events[1:]):
            if cur["note_id"] != nxt["note_id"]:
                continue
            seconds = cur["poly_timing_rel_to_next"] * 60.0 / (180.0 * cur["poly_play_bpm"])
            self.assertAlmostEqual(seconds, nxt["time"] - cur["time"], places=9)

    def test_level_switches_speed_between_shapes(self):
        notes = _chord(0.0, 2 * CYCLE, 60, 64, 67) + [Note(2 * CYCLE, 4 * CYCLE, 60)]
        options = dict(
            method="harmony",
            harmony_timing_mode="ratio-polyrhythm",
            harmony_mode="fifth +7",
            angle_only_bpm=BPM,
            harmony_poly_chord_source="overlap",
        )
        _level, fixed = build_adofai_level(notes, harmony_poly_cycle_mode="fixed", **options)
        self.assertEqual(fixed["harmony_setspeed_events"], 0)
        self.assertEqual(fixed["harmony_poly_chord_sequence"], "4:5:6 > 2:3")
        level, auto = build_adofai_level(notes, harmony_poly_cycle_mode="auto", **options)
        events, *_ = _events(notes, cycle_mode="auto")
        first_bpm = events[0]["poly_play_bpm"]
        second_bpm = next(e["poly_play_bpm"] for e in events if e["poly_ratio_text"] == "2:3")
        self.assertAlmostEqual(level["settings"]["bpm"], round(first_bpm, 6))
        speeds = [a["beatsPerMinute"] for a in level["actions"] if a["eventType"] == "SetSpeed"]
        self.assertTrue(any(abs(s - second_bpm) < 1e-6 for s in speeds))


class OverlapChordBridgeOptionTests(unittest.TestCase):
    def test_web_defaults_to_overlap_chords(self):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 0.5, 60.0).normalized()]
        self.assertEqual(bridge.get_adofai_export_defaults()["harmonyPolyChordSource"], "overlap")
        _, options, _ = bridge._prepare_adofai_export({"method": "harmony"}, None)
        self.assertEqual(options["harmony_poly_chord_source"], "overlap")
        _, options, _ = bridge._prepare_adofai_export({"method": "harmony", "harmonyPolyChordSource": "preset"}, None)
        self.assertEqual(options["harmony_poly_chord_source"], "preset")


if __name__ == "__main__":
    unittest.main()

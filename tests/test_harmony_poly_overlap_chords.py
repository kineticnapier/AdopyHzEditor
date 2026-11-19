from __future__ import annotations

import time
import unittest

from core.note_model import Note
from exporters import adofai
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


def _brute_force_auto_angle(gaps: tuple[float, ...], twirl: bool) -> float:
    """The original exhaustive search, kept as a reference."""
    tiles = len(gaps)
    cap = 360.0 / max(gaps)
    preferred = min(180.0 * tiles, cap)

    def score(angle: float) -> int:
        return adofai._ratio_path_near_overlaps(
            gaps, angle, cycles=adofai._AUTO_CYCLE_PREVIEW_CYCLES, twirl_each_cycle=twirl,
        )

    if score(preferred) == 0:
        return preferred
    narrowest = min(gaps)
    best_key = None
    best = preferred
    angle = 180.0
    while angle <= cap + 1e-9:
        key = (float(score(angle)), -narrowest * angle, abs(angle - preferred))
        if best_key is None or key < best_key:
            best_key, best = key, angle
        angle += adofai._AUTO_CYCLE_SEARCH_STEP
    return best


class AutoCycleSearchPerformanceTests(unittest.TestCase):
    def _gaps(self, specs) -> tuple[float, ...]:
        pattern = adofai.build_harmony_ratio_polyrhythm_pattern(specs)
        return tuple(float(g) for g in pattern["position_gaps"] if float(g) > 0)

    def test_early_exit_search_matches_the_exhaustive_search(self):
        presets = ("fifth +7", "major triad", "minor triad", "sus4", "dominant 7")
        shapes = [adofai.build_harmony_voice_specs(p, harmony_tuning="just intonation") for p in presets]
        shapes += [adofai._overlap_voice_specs(m) for m in ([60, 64], [60, 65], [60, 63], [60, 69])]
        for specs in shapes:
            gaps = self._gaps(specs)
            self.assertLessEqual(len(gaps), adofai._AUTO_CYCLE_SEARCH_MAX_TILES)
            for twirl in (False, True):
                with self.subTest(tiles=len(gaps), twirl=twirl):
                    adofai._harmony_poly_auto_cycle_angle.cache_clear()
                    self.assertEqual(
                        adofai._harmony_poly_auto_cycle_angle(gaps, twirl),
                        _brute_force_auto_angle(gaps, twirl),
                    )

    def test_dense_grid_skips_the_search(self):
        # A 9-note cluster gives hundreds of hits per cycle; the exhaustive
        # search over it took minutes.
        gaps = self._gaps(adofai._overlap_voice_specs([60, 61, 62, 63, 64, 65, 66, 67, 68]))
        self.assertGreater(len(gaps), adofai._AUTO_CYCLE_SEARCH_MAX_TILES)
        adofai._harmony_poly_auto_cycle_angle.cache_clear()
        started = time.perf_counter()
        angle = adofai._harmony_poly_auto_cycle_angle(gaps, True)
        self.assertLess(time.perf_counter() - started, 0.5)
        self.assertAlmostEqual(angle, min(180.0 * len(gaps), 360.0 / max(gaps)))

    def test_dense_overlapping_chords_export_quickly(self):
        notes = []
        for k in range(8):
            start = k * 4 * CYCLE
            notes += _chord(start, start + 4 * CYCLE, *[60 + k + i for i in range(7)])
        adofai._harmony_poly_auto_cycle_angle.cache_clear()
        started = time.perf_counter()
        _events_list, _dup, _specs, stats = _events(notes, cycle_mode="auto")
        self.assertLess(time.perf_counter() - started, 10.0)
        self.assertEqual(stats["chord_source"], "overlap")


class BeatGridTests(unittest.TestCase):
    """harmony_poly_grid_origin puts cycles on one global grid with rests."""

    def test_cycles_sit_on_the_global_grid_and_silence_is_a_rest(self):
        # Notes start half a cycle in and leave a one-cycle silent gap.
        notes = [Note(0.5 * CYCLE, 2.0 * CYCLE, 60.0), Note(3.0 * CYCLE, 4.25 * CYCLE, 60.0)]
        events, *_ = build_harmony_ratio_polyrhythm_events(
            notes, harmony_mode="fifth +7", play_bpm=BPM, harmony_poly_grid_origin=0.0,
        )
        positions = {0.0, 1 / 3, 0.5, 2 / 3}  # fifth 2:3 grid
        for e in events:
            cycle_pos = e["time"] / CYCLE - e["poly_cycle_index"]
            self.assertTrue(any(abs(cycle_pos - p) < 1e-9 for p in positions), e["time"])
            # Only inside a sounding note.
            self.assertTrue(any(n.start - 1e-9 <= e["time"] < n.end - 1e-9 for n in notes), e["time"])
        times = [round(e["time"] / CYCLE, 6) for e in events]
        self.assertEqual(times[0], 0.5)  # first grid hit inside the first note
        self.assertFalse([t for t in times if 2.0 <= t < 3.0])  # the gap is a rest
        self.assertIn(3.0, times)

    def test_per_note_grid_is_unchanged_without_origin(self):
        notes = [Note(0.5 * CYCLE, 2.0 * CYCLE, 60.0)]
        events, *_ = build_harmony_ratio_polyrhythm_events(notes, harmony_mode="fifth +7", play_bpm=BPM)
        self.assertAlmostEqual(events[0]["time"], 0.5 * CYCLE)
        self.assertEqual(events[0]["poly_cycle_index"], 0)

    def test_level_shifts_the_song_time_origin_with_the_first_note(self):
        notes = [Note(10.0 + 0.5 * CYCLE, 10.0 + 2.0 * CYCLE, 60.0)]
        level, stats = build_adofai_level(
            notes,
            method="harmony",
            harmony_timing_mode="ratio-polyrhythm",
            harmony_mode="fifth +7",
            angle_only_bpm=BPM,
            harmony_poly_cycle_mode="fixed",
            harmony_poly_grid_origin_seconds=10.0,
        )
        self.assertEqual(stats["harmony_poly_grid"], "global")
        # Grid hits at cycle positions 0.5, 2/3, 1, 4/3, 1.5, 5/3 -> 6 tiles.
        self.assertEqual(stats["tiles_total"], 6)


class PitchTimingTests(unittest.TestCase):
    """harmony_poly_pitch_timing makes every voice hit at its own frequency."""

    def _events(self, notes, harmony_mode="off", **kwargs):
        return build_harmony_ratio_polyrhythm_events(
            notes,
            harmony_mode=harmony_mode,
            play_bpm=BPM,
            harmony_poly_chord_source="overlap",
            harmony_poly_pitch_timing=True,
            **kwargs,
        )

    @staticmethod
    def _voice_rates(events) -> dict[int, float]:
        """Hits per second of each voice in the first cycle."""
        first = [e for e in events if e["poly_cycle_index"] == 0]
        seconds = first[0]["poly_cycle_seconds"]
        counts: dict[int, int] = {}
        for e in first:
            for voice in str(e["poly_merged_voices"]).split(","):
                counts[int(voice)] = counts.get(int(voice), 0) + 1
        return {v: c / seconds for v, c in counts.items()}

    def test_single_note_hits_at_its_frequency(self):
        events, *_ = self._events([Note(0.0, 0.1, 69.0)])  # A4 = 440 Hz
        gaps = {round(b["time"] - a["time"], 9) for a, b in zip(events, events[1:])}
        self.assertEqual(gaps, {round(1 / 440.0, 9)})

    def test_chord_voices_hit_at_their_own_pitch_with_octaves_kept(self):
        # G#3 + A#5 (26 semitones): just ratio 9/2, not folded to 9/8.
        events, _dup, _specs, stats = self._events([Note(0.0, 0.2, 56.0), Note(0.0, 0.2, 82.0)])
        self.assertEqual(stats["ratio_text"], "2:9")
        rates = self._voice_rates(events)
        g3 = 440.0 * 2 ** ((56 - 69) / 12)
        self.assertAlmostEqual(rates[0], g3, places=6)
        self.assertAlmostEqual(rates[1], g3 * 4.5, places=6)  # A#5 within 4 cents of 932.3 Hz

    def test_cycle_bpm_matches_its_length(self):
        events, *_ = self._events([Note(0.0, 0.2, 60.0), Note(0.0, 0.2, 64.0), Note(0.0, 0.2, 67.0)])
        for cur, nxt in zip(events, events[1:]):
            seconds = cur["poly_timing_rel_to_next"] * 60.0 / (180.0 * cur["poly_play_bpm"])
            self.assertAlmostEqual(seconds, nxt["time"] - cur["time"], places=9)

    def test_silence_after_a_note_is_a_rest(self):
        events, *_ = self._events([Note(0.0, 0.05, 69.0), Note(0.2, 0.25, 69.0)])
        self.assertFalse([e for e in events if 0.05 <= e["time"] < 0.2])

    def test_full_turn_gaps_never_wrap_to_a_near_zero_tile(self):
        # 360 + float noise used to wrap to a 2e-9 degree tile with a ~0 BPM.
        self.assertEqual(adofai.clean_relative_angle(360.0000000016371), 360.0)
        self.assertEqual(adofai.clean_relative_angle(720.0 + 5e-7), 360.0)
        notes = _chord(0.0, 0.5, 45, 57, 64, 69, 76) + _chord(0.5, 1.0, 43, 55, 62, 67, 74)
        level, _stats = build_adofai_level(
            notes,
            method="harmony",
            harmony_timing_mode="ratio-polyrhythm",
            harmony_mode="off",
            harmony_poly_chord_source="overlap",
            harmony_poly_pitch_timing=True,
        )
        speeds = [a["beatsPerMinute"] for a in level["actions"] if a.get("eventType") == "SetSpeed"]
        self.assertTrue(speeds)
        self.assertGreater(min(speeds), 1.0)

    def test_level_starts_at_the_first_cycle_speed(self):
        level, stats = build_adofai_level(
            [Note(0.0, 0.1, 69.0)],
            method="harmony",
            harmony_timing_mode="ratio-polyrhythm",
            harmony_mode="off",
            harmony_poly_chord_source="overlap",
            harmony_poly_cycle_mode="fixed",
            harmony_poly_pitch_timing=True,
        )
        self.assertEqual(stats["harmony_poly_timing"], "pitch")
        # 720 degrees per 1/440 s cycle.
        self.assertAlmostEqual(level["settings"]["bpm"], 720.0 * 60.0 * 440.0 / 180.0, places=3)


class ChordCleanupTests(unittest.TestCase):
    """Legato tails and octave doublings should not create extra harmony."""

    def test_short_legato_tail_is_trimmed_but_real_overlap_kept(self):
        notes = [
            Note(0.0, 0.53, 69.0),   # rings 30 ms into the next note
            Note(0.5, 1.0, 71.0),
            Note(1.0, 2.0, 72.0),    # held 300 ms under the next note: real overlap
            Note(1.7, 2.2, 67.0),
        ]
        trimmed = adofai._trim_legato_overlaps(notes, 0.05)
        self.assertAlmostEqual(trimmed[0].end, 0.5)
        self.assertAlmostEqual(trimmed[2].end, 2.0)
        self.assertEqual(len(adofai._trim_legato_overlaps(notes, 0.0)), 4)
        self.assertAlmostEqual(adofai._trim_legato_overlaps(notes, 0.0)[0].end, 0.53)

    def test_glides_are_not_trimmed(self):
        glide = Note(0.0, 0.53, 69.0, kind="curve", midi_end=72.0)
        trimmed = adofai._trim_legato_overlaps([glide, Note(0.5, 1.0, 71.0)], 0.05)
        self.assertAlmostEqual(trimmed[0].end, 0.53)

    def test_octave_doublings_fold_into_the_lower_voice(self):
        doubled = adofai._overlap_voice_specs([57.0, 69.0, 81.0, 76.0], merge_octaves=True)
        self.assertEqual([round(s["ratio"], 9) for s in doubled], [1.0, 3.0])  # A3 + E5 (3/1)
        kept = adofai._overlap_voice_specs([57.0, 69.0, 81.0, 76.0], merge_octaves=False)
        self.assertEqual(len(kept), 4)

    def test_lead_with_octave_double_is_one_voice(self):
        notes = [Note(0.0, 0.1, 69.0), Note(0.0, 0.1, 57.0)]
        _events_list, _dup, _specs, merged = build_harmony_ratio_polyrhythm_events(
            notes, harmony_mode="off", play_bpm=BPM, harmony_poly_chord_source="overlap",
            harmony_poly_pitch_timing=True, harmony_poly_merge_octaves=True,
        )
        _events_list, _dup, _specs, plain = build_harmony_ratio_polyrhythm_events(
            notes, harmony_mode="off", play_bpm=BPM, harmony_poly_chord_source="overlap",
            harmony_poly_pitch_timing=True,
        )
        self.assertEqual(merged["ratio_text"], "1")
        self.assertEqual(plain["ratio_text"], "1:2")


class ChordLimitTests(unittest.TestCase):
    def test_max_voices_keeps_top_root_and_simplest(self):
        # C3 E3 G3 B3 D4 + melody A5: keep C3 (root), A5 (top) and G3 (3:2, simplest).
        kept = adofai._limit_chord_voices([48, 52, 55, 59, 62, 81], 3, 0)
        self.assertEqual(kept, [48, 55, 81])
        self.assertEqual(adofai._limit_chord_voices([48, 52, 55, 81], 1, 0), [81])
        self.assertEqual(adofai._limit_chord_voices([48, 52, 55], 0, 0), [48, 52, 55])

    def test_root_cycle_limit_keeps_the_top_note(self):
        self.assertEqual(adofai._chord_root_cycles([60, 64, 67]), 4)   # 4:5:6
        self.assertEqual(adofai._chord_root_cycles([60, 63, 67]), 10)  # 10:12:15
        self.assertEqual(adofai._limit_chord_voices([60, 64, 67], 0, 12), [60, 64, 67])
        # Semitone 16:15 needs 15 root periods: drop the root, keep the melody.
        self.assertEqual(adofai._limit_chord_voices([60, 61], 0, 12), [61])

    def test_limits_apply_in_the_export(self):
        notes = _chord(0.0, 0.2, 48, 52, 55, 59, 62, 81)
        _events_list, _dup, _specs, stats = build_harmony_ratio_polyrhythm_events(
            notes, harmony_mode="off", play_bpm=BPM, harmony_poly_chord_source="overlap",
            harmony_poly_pitch_timing=True, harmony_poly_max_voices=3, harmony_poly_max_root_cycles=12,
        )
        self.assertEqual(stats["ratio_text"].count(":") + 1, 3)
        self.assertLessEqual(stats["common_root_cycles"], 12)


class OverlapChordBridgeOptionTests(unittest.TestCase):
    def test_web_defaults_to_overlap_chords(self):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 0.5, 60.0).normalized()]
        self.assertEqual(bridge.get_adofai_export_defaults()["harmonyPolyChordSource"], "overlap")
        _, options, _ = bridge._prepare_adofai_export({"method": "harmony"}, None)
        self.assertEqual(options["harmony_poly_chord_source"], "overlap")
        _, options, _ = bridge._prepare_adofai_export({"method": "harmony", "harmonyPolyChordSource": "preset"}, None)
        self.assertEqual(options["harmony_poly_chord_source"], "preset")

    def test_web_defaults_clean_up_chords(self):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 0.5, 60.0).normalized()]
        defaults = bridge.get_adofai_export_defaults()
        self.assertEqual(defaults["harmonyPolyLegatoMs"], 50.0)
        self.assertTrue(defaults["harmonyPolyMergeOctaves"])
        _, options, _ = bridge._prepare_adofai_export({"method": "harmony"}, None)
        self.assertEqual(options["harmony_poly_legato_ms"], 50.0)
        self.assertTrue(options["harmony_poly_merge_octaves"])
        self.assertEqual(options["harmony_poly_max_voices"], 3)
        self.assertEqual(options["harmony_poly_max_root_cycles"], 12)
        _, options, _ = bridge._prepare_adofai_export(
            {"method": "harmony", "harmonyPolyLegatoMs": 0, "harmonyPolyMergeOctaves": False}, None,
        )
        self.assertEqual(options["harmony_poly_legato_ms"], 0.0)
        self.assertFalse(options["harmony_poly_merge_octaves"])

    def test_beat_sync_derives_output_bpm_and_grid_from_project(self):
        bridge = Bridge()
        bridge.notes = [Note(0.0, 0.5, 60.0).normalized()]
        bridge.settings["bpm"] = 190.0
        bridge.settings["offsetMs"] = 250.0
        base = {"method": "harmony", "harmonyTimingMode": "ratio-polyrhythm", "harmonyPolyCycleAngle": 720.0}
        self.assertEqual(bridge.get_adofai_export_defaults()["harmonyPolyCycleTiming"], "pitch")
        _, options, _ = bridge._prepare_adofai_export(base, None)
        self.assertTrue(options["harmony_poly_pitch_timing"])
        self.assertIsNone(options["harmony_poly_grid_origin_seconds"])
        base = {**base, "harmonyPolyCycleTiming": "beat"}
        _, options, _ = bridge._prepare_adofai_export(base, None)
        self.assertFalse(options["harmony_poly_pitch_timing"])
        self.assertAlmostEqual(options["angle_only_bpm"], 760.0)  # one cycle = one beat
        self.assertAlmostEqual(options["harmony_poly_grid_origin_seconds"], 0.25)
        _, options, _ = bridge._prepare_adofai_export({**base, "harmonyPolyBeatsPerCycle": 0.5}, None)
        self.assertAlmostEqual(options["angle_only_bpm"], 1520.0)
        _, options, _ = bridge._prepare_adofai_export(
            {**base, "harmonyPolyCycleTiming": "manual", "angleOnlyBpm": 1234.0}, None,
        )
        self.assertAlmostEqual(options["angle_only_bpm"], 1234.0)
        self.assertIsNone(options["harmony_poly_grid_origin_seconds"])


if __name__ == "__main__":
    unittest.main()

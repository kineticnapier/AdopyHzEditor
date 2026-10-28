from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from mido import Message, MidiFile, MidiTrack

from core.audio_player import AudioPlayer
from core.audio_analysis import Spectrogram
from core.note_model import Note
from exporters.midi import export_midi
from importers.midi import import_midi
from web.backend import Bridge
import web.tools as web_tools
from web_ui import Bridge as WebUIBridge


class _FakeStream:
    def __init__(self, **_kwargs):
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        pass


class _FakeSoundDevice:
    class CallbackStop(Exception):
        pass

    OutputStream = _FakeStream


class IssueCorrectnessBoundaryTests(unittest.TestCase):
    def bridge(self, *, duration: float = 10.0) -> Bridge:
        bridge = Bridge()
        bridge.duration = duration
        bridge.player.set_virtual_duration(duration)
        bridge._undo_stack.clear()
        bridge._redo_stack.clear()
        return bridge

    def test_paste_near_end_shifts_group_without_collapsing_spacing(self):
        bridge = self.bridge()
        bridge.notes = [Note(1, 2, 60), Note(3, 4, 64)]
        bridge.copy_notes([0, 1])

        result = bridge.paste_notes(9.0)

        pasted = [Note.from_dict(result["notes"][i]) for i in result["indices"]]
        self.assertEqual([(n.start, n.end) for n in pasted], [(7.0, 8.0), (9.0, 10.0)])

    def test_note_created_at_chart_end_has_positive_duration(self):
        bridge = self.bridge()
        result = bridge.add_note(10.0, 10.0, 60.0)
        note = Note.from_dict(result["notes"][result["index"]])
        self.assertGreaterEqual(note.duration, 0.001)
        self.assertEqual(note.end, 10.0)

    def test_window_resize_reclamps_existing_start(self):
        bridge = self.bridge()
        bridge.view.update(start=8.0, windowSeconds=2.0)
        view = bridge.set_view({"windowSeconds": 6.0})
        self.assertEqual(view["start"], 4.0)

    def test_fractional_property_pitch_is_not_rounded_to_analysis_bins(self):
        bridge = self.bridge()
        bridge.pitch_step = 1.0
        bridge.notes = [Note(0, 1, 60)]
        result = bridge.set_note_properties(0, {"midi": 60.25})
        self.assertEqual(result["notes"][0]["midi"], 60.25)

    def test_horizontal_move_does_not_clamp_pitch_to_analysis_range(self):
        bridge = self.bridge()
        bridge.midi_min = 60
        bridge.midi_max = 72
        bridge.notes = [Note(1, 2, 20.5)]
        result = bridge.move_notes([0], 1.0, 0.0)
        self.assertEqual(result["notes"][0]["midi"], 20.5)

    def test_curve_move_clamps_every_pitch_value_to_midi_bounds(self):
        bridge = self.bridge()
        bridge.notes = [Note(0, 1, 120, kind="curve", midi_end=125, ctrl1_midi=126, ctrl2_midi=124)]
        result = bridge.move_notes([0], 0.0, 50.0)
        note = Note.from_dict(result["notes"][0])
        self.assertEqual(note.ctrl1_midi, 127.0)
        self.assertTrue(all(0 <= value <= 127 for value in (note.midi, note.midi_end, note.ctrl1_midi, note.ctrl2_midi)))

    def test_snap_group_move_is_reclamped_after_snapping(self):
        bridge = self.bridge()
        bridge.settings.update(snapEnabled=True, bpm=120.0, snapDiv=1)
        bridge.notes = [Note(9.7, 9.9, 60)]
        result = bridge.move_notes([0], 0.2, 0.0)
        note = Note.from_dict(result["notes"][0])
        self.assertLessEqual(note.end, bridge.duration)
        self.assertAlmostEqual(note.end, 10.0)

    def test_bulk_snap_group_move_is_reclamped_at_chart_end(self):
        bridge = self.bridge(duration=1.0)
        bridge.settings.update(snapEnabled=True, bpm=60.0, snapDiv=1, offsetMs=0.0)
        bridge.notes = [Note(0.25, 0.50, 60)]
        result = bridge.bulk_edit_notes([0], {"timeDelta": 0.50})
        note = Note.from_dict(result["notes"][0])
        self.assertAlmostEqual(note.start, 0.75)
        self.assertAlmostEqual(note.end, 1.0)

    def test_vertical_move_does_not_snap_off_grid_note_in_time(self):
        bridge = self.bridge(duration=2.0)
        bridge.settings.update(snapEnabled=True, bpm=120.0, snapDiv=1, offsetMs=0.0)
        bridge.notes = [Note(0.30, 0.50, 60)]
        result = bridge.move_notes([0], 0.0, 1.0)
        note = Note.from_dict(result["notes"][0])
        self.assertAlmostEqual(note.start, 0.30)
        self.assertAlmostEqual(note.end, 0.50)
        self.assertEqual(note.midi, 61.0)

    def test_vertical_duplicate_does_not_snap_off_grid_note_in_time(self):
        bridge = self.bridge(duration=2.0)
        bridge.settings.update(snapEnabled=True, bpm=120.0, snapDiv=1, offsetMs=0.0)
        bridge.notes = [Note(0.30, 0.50, 60)]
        result = bridge.duplicate_notes_shifted([0], 0.0, 1.0)
        note = Note.from_dict(result["notes"][result["indices"][0]])
        self.assertAlmostEqual(note.start, 0.30)
        self.assertAlmostEqual(note.end, 0.50)
        self.assertEqual(note.midi, 61.0)

    def test_noop_move_preserves_history_redo_dirty_and_player_sync(self):
        bridge = self.bridge(duration=1.0)
        bridge.settings["snapEnabled"] = False
        bridge.notes = [Note(0.0, 0.25, 60)]
        marker = bridge._snapshot()
        bridge._redo_stack.append(marker)
        bridge._dirty = False
        with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
            result = bridge.move_notes([0], -1.0, 0.0)
        self.assertFalse(result["changed"])
        self.assertFalse(bridge._dirty)
        self.assertEqual(bridge._undo_stack, [])
        self.assertEqual(bridge._redo_stack, [marker])
        sync.assert_not_called()

    def test_noop_quantize_preserves_history_redo_dirty_and_player_sync(self):
        bridge = self.bridge(duration=1.0)
        bridge.settings.update(bpm=120.0, snapDiv=1, offsetMs=0.0)
        bridge.notes = [Note(0.0, 0.5, 60)]
        marker = bridge._snapshot()
        bridge._redo_stack.append(marker)
        bridge._dirty = False
        with mock.patch.object(bridge, "_sync_notes_to_player") as sync:
            result = bridge.quantize_notes([0])
        self.assertFalse(result["changed"])
        self.assertFalse(bridge._dirty)
        self.assertEqual(bridge._undo_stack, [])
        self.assertEqual(bridge._redo_stack, [marker])
        sync.assert_not_called()

    def test_note_only_fit_opens_around_late_notes(self):
        bridge = WebUIBridge()
        bridge.duration = 1.0
        bridge.notes = [Note(100.0, 101.0, 70)]
        bridge._fit_blank_bounds_to_notes()
        self.assertLessEqual(bridge.view["start"], 100.0)
        self.assertGreaterEqual(bridge.view["start"] + bridge.view["windowSeconds"], 101.0)

    def test_merge_extends_chart_duration_even_with_existing_audio(self):
        bridge = WebUIBridge()
        bridge.duration = 5.0
        bridge.audio_path = "audio.wav"
        bridge.spectrogram = Spectrogram(
            audio_path="audio.wav",
            db=np.zeros((2, 2), dtype=np.float32),
            duration=5.0,
            midi_min=60,
            midi_max=61,
            frame_times=np.array([0.0, 5.0]),
            sr=44100,
            bins_per_semitone=1,
            folded_to_semitone=False,
        )
        with (
            mock.patch.object(bridge, "_dialog", return_value="notes.adopyhz"),
            mock.patch.object(web_tools, "load_project", return_value=(None, [Note(8, 12, 60)], {})),
        ):
            state = bridge.merge_project_notes_dialog()
        self.assertEqual(state["playback"]["duration"], 12.0)

    def test_player_replay_at_eof_restarts_from_zero(self):
        player = AudioPlayer()
        player.available = True
        player.sd = _FakeSoundDevice()
        player.audio = np.zeros((10, 1), dtype=np.float32)
        player.sr = 10
        player.virtual_duration_samples = 10
        player.pos = 10
        player._pos_float = 10.0
        player.play()
        self.assertEqual(player.pos, 0)
        self.assertTrue(player.playing)

    def test_player_can_seek_and_preview_beyond_audio_end(self):
        player = AudioPlayer()
        player.audio = np.zeros((10, 1), dtype=np.float32)
        player.sr = 10
        player.set_virtual_duration(2.0)
        player.seek(1.5)
        self.assertEqual(player.duration, 2.0)
        self.assertEqual(player.time, 1.5)

    def test_curve_preview_has_continuous_phase_and_only_outer_fades(self):
        player = AudioPlayer()
        player.sr = 1000
        player.set_preview_notes([Note(0, 1, 60, kind="curve", midi_end=72, ctrl1_midi=60, ctrl2_midi=72)])
        segments = player.preview_notes
        self.assertGreater(len(segments), 2)
        self.assertTrue(segments[0].fade_in)
        self.assertFalse(segments[0].fade_out)
        self.assertFalse(segments[1].fade_in)
        self.assertGreater(segments[1].phase, segments[0].phase)
        self.assertTrue(segments[-1].fade_out)

    def test_unavailable_audio_device_is_reported_as_unavailable(self):
        bridge = self.bridge()
        bridge.player.available = False
        bridge.player.error = "no output device"
        state = bridge.get_playback_state()
        self.assertFalse(state["available"])
        self.assertEqual(state["error"], "no output device")

    def test_cross_track_note_off_pairs_by_channel_and_pitch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cross-track.mid"
            midi = MidiFile(type=1, ticks_per_beat=480)
            on_track = MidiTrack([Message("note_on", channel=2, note=64, velocity=90, time=0)])
            off_track = MidiTrack([Message("note_off", channel=2, note=64, velocity=0, time=480)])
            midi.tracks.extend([on_track, off_track])
            midi.save(path)
            result = import_midi(path)
        self.assertEqual(len(result.notes), 1)
        self.assertEqual(result.notes[0].midi, 64.0)
        self.assertAlmostEqual(result.notes[0].duration, 0.5)

    def test_overlapping_same_pitch_exports_as_one_union_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "overlap.mid"
            export_midi([Note(0, 1, 60), Note(0.5, 1.5, 60)], path, bpm=120)
            midi = MidiFile(path)
        messages = [message for message in midi.tracks[0] if message.type in {"note_on", "note_off"}]
        self.assertEqual([message.type for message in messages], ["note_on", "note_off"])
        self.assertEqual(sum(message.time for message in messages), 1440)

    def test_quick_hz_append_validates_requested_start_floor(self):
        bridge = WebUIBridge()
        with (
            mock.patch.object(web_tools, "AppendGeneratedDataToChart", side_effect=ValueError("start mismatch")) as append,
            self.assertRaisesRegex(ValueError, "start mismatch"),
        ):
            bridge.append_quick_hz_chart("level.adofai", {"bpm": 120, "hz": 4, "startFloor": 7, "count": 1})
        self.assertEqual(append.call_args.kwargs["start_floor"], 7)


if __name__ == "__main__":
    unittest.main()

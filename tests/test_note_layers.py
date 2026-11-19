from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.note_model import Note
from core.project_io import load_project, save_project
from web_ui import Bridge
from tests.test_midi_track_selection import _midi_file, _track


class NoteLayerModelTests(unittest.TestCase):
    def test_layer_survives_copies_and_serialization(self):
        note = Note(0.0, 1.0, 60.0, layer="Lead")
        for copy in (
            note.normalized(),
            note.shifted(0.5, 2.0),
            note.with_target_angle(90.0),
            note.with_interpolation("linear_pitch"),
        ):
            self.assertEqual(copy.layer, "Lead")
        self.assertEqual(Note.from_dict(note.to_dict()).layer, "Lead")
        self.assertNotIn("layer", Note(0.0, 1.0, 60.0).to_dict())

    def test_project_round_trip_keeps_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.adopyhz"
            save_project(path, audio_path=None, notes=[Note(0, 1, 60, layer="Bass"), Note(1, 2, 62)], settings={})
            _audio, notes, _settings = load_project(path)
        self.assertEqual([n.layer for n in notes], ["Bass", None])


class LayerBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "song.mid"
        self.path.write_bytes(_midi_file([
            _track("Lead", [(0, 480, 72, 100), (480, 960, 74, 100)], channel=0),
            _track("Layer", [(0, 480, 72, 90)], channel=1),
            _track("Lead", [(0, 960, 48, 90)], channel=2),  # duplicate track name
        ]))
        self.bridge = Bridge()
        with mock.patch.object(self.bridge, "_dialog", return_value=str(self.path)):
            picked = self.bridge.pick_midi_tracks_dialog()
        self.names = [t["name"] for t in picked["tracks"]]
        with mock.patch.object(self.bridge, "_sync_notes_to_player"):
            self.bridge.import_midi_tracks([t["index"] for t in picked["tracks"]])

    def tearDown(self):
        self.tmp.cleanup()

    def test_import_tags_notes_with_unique_track_names(self):
        self.assertEqual(self.names, ["Lead", "Layer", "Lead (2)"])
        layers = sorted((n.layer, n.midi) for n in self.bridge.notes)
        self.assertEqual(layers, [("Layer", 72.0), ("Lead", 72.0), ("Lead", 74.0), ("Lead (2)", 48.0)])

    def test_muted_layers_leave_playback_and_export(self):
        with mock.patch.object(self.bridge.player, "set_preview_notes") as preview:
            state = self.bridge.update_settings({"mutedLayers": ["Lead (2)", "Layer"]})
        self.assertEqual(state["mutedLayers"], ["Lead (2)", "Layer"])
        played = preview.call_args[0][0]
        self.assertEqual(sorted(n.layer for n in played), ["Lead", "Lead"])
        notes, _opts, _ = self.bridge._prepare_adofai_export({"method": "rabbit_zip"}, None)
        self.assertEqual(sorted(n.midi for n in notes), [72.0, 74.0])
        self.assertEqual(len(self.bridge.notes), 4)  # muting never deletes notes

    def test_export_merges_same_pitch_across_active_layers(self):
        notes, _opts, _ = self.bridge._prepare_adofai_export({"method": "rabbit_zip"}, None)
        self.assertEqual(sorted(n.midi for n in notes), [48.0, 72.0, 74.0])  # Lead/Layer 72 merged
        notes, _opts, _ = self.bridge._prepare_adofai_export({"method": "rabbit_zip", "mergeDuplicateNotes": False}, None)
        self.assertEqual(sorted(n.midi for n in notes), [48.0, 72.0, 72.0, 74.0])

    def test_all_muted_export_has_nothing_to_export(self):
        self.bridge.update_settings({"mutedLayers": ["Lead", "Layer", "Lead (2)"]})
        with self.assertRaisesRegex(ValueError, "No notes"):
            self.bridge._prepare_adofai_export({"method": "rabbit_zip"}, None)

    def test_split_keeps_layer(self):
        index = next(i for i, n in enumerate(self.bridge.notes) if n.layer == "Lead (2)")
        with mock.patch.object(self.bridge, "_sync_notes_to_player"):
            self.bridge.split_notes([index], 0.25)
        self.assertEqual(sorted(n.layer for n in self.bridge.notes if n.midi == 48.0), ["Lead (2)", "Lead (2)"])

    def test_bad_muted_layers_value_is_rejected(self):
        with self.assertRaises(ValueError):
            self.bridge.update_settings({"mutedLayers": "Lead"})


if __name__ == "__main__":
    unittest.main()

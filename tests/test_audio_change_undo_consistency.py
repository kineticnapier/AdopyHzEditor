"""Undo/Redo must not resurrect source-derived state from a replaced audio file.

Audio replacement is not itself an undoable step. History entries created
against the previous audio therefore restore notes only; the timeline length
and analysed pitch range must keep following the currently loaded audio.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

import web.backend as web_backend
from core.note_model import Note
from core.audio_analysis import Spectrogram
from web_ui import Bridge


def _spec(duration: float, midi_min: int, midi_max: int) -> Spectrogram:
    return Spectrogram(
        audio_path="mock.wav",
        db=np.zeros((2, 2), dtype=np.float32),
        duration=duration,
        midi_min=midi_min,
        midi_max=midi_max,
        frame_times=np.array([0.0, duration]),
        sr=44100,
    )


class AudioChangeUndoConsistencyTests(unittest.TestCase):
    def _bridge(self) -> Bridge:
        bridge = Bridge()
        bridge.settings["snapEnabled"] = False
        # No real audio device/buffer is needed for history consistency.
        bridge.player.set_audio = mock.Mock()
        return bridge

    def _open(self, bridge: Bridge, name: str, duration: float, midi=(24, 96)) -> dict:
        decoded = SimpleNamespace(samples=np.zeros(1, dtype=np.float32), sample_rate=44100, duration=duration)
        with (
            mock.patch.object(bridge, "_file_dialog", return_value=[name]),
            mock.patch.object(bridge, "_prepare_audio_path", return_value=(decoded, _spec(duration, *midi))),
        ):
            return bridge.open_audio()

    def _assert_source_state(self, bridge: Bridge, duration: float, midi=(24, 96)) -> None:
        self.assertAlmostEqual(bridge.duration, duration)
        self.assertEqual((bridge.midi_min, bridge.midi_max), midi)
        self.assertAlmostEqual(bridge.get_playback_state()["duration"], duration)
        # The seekable range is the observable symptom of a stale duration.
        self.assertAlmostEqual(bridge.seek_to(duration - 0.5)["time"], duration - 0.5, places=3)

    def test_undo_after_switching_to_longer_audio_keeps_new_duration(self):
        bridge = self._bridge()
        self._open(bridge, "short.wav", 10.0, (40, 80))
        bridge.add_note(1.0, 2.0, 60.0)
        self._open(bridge, "long.wav", 30.0, (24, 96))

        undone = bridge.undo()
        self.assertTrue(undone["changed"])
        self.assertEqual(undone["notes"], [])
        self._assert_source_state(bridge, 30.0)

        redone = bridge.redo()
        self.assertTrue(redone["changed"])
        self.assertEqual(len(redone["notes"]), 1)
        self._assert_source_state(bridge, 30.0)

    def test_undo_after_switching_to_shorter_audio_does_not_restore_old_length(self):
        bridge = self._bridge()
        self._open(bridge, "long.wav", 30.0, (24, 96))
        bridge.add_note(1.0, 2.0, 60.0)
        self._open(bridge, "short.wav", 10.0, (40, 80))

        bridge.undo()
        self._assert_source_state(bridge, 10.0, (40, 80))
        bridge.redo()
        self.assertEqual(len(bridge.notes), 1)
        self._assert_source_state(bridge, 10.0, (40, 80))

    def test_redo_entry_created_before_audio_change_uses_new_duration(self):
        bridge = self._bridge()
        self._open(bridge, "short.wav", 10.0, (40, 80))
        bridge.add_note(1.0, 2.0, 60.0)
        bridge.undo()
        self._open(bridge, "long.wav", 30.0)

        redone = bridge.redo()
        self.assertEqual(len(redone["notes"]), 1)
        self._assert_source_state(bridge, 30.0)
        bridge.undo()
        self.assertEqual(bridge.notes, [])
        self._assert_source_state(bridge, 30.0)

    def test_restored_tail_note_beyond_new_audio_extends_duration(self):
        bridge = self._bridge()
        self._open(bridge, "long.wav", 30.0)
        bridge.add_note(25.0, 26.0, 60.0)
        bridge.delete_notes([0])
        self._open(bridge, "short.wav", 10.0)
        self.assertAlmostEqual(bridge.duration, 10.0)

        bridge.undo()
        self.assertEqual(len(bridge.notes), 1)
        self.assertAlmostEqual(bridge.duration, 26.0)
        self.assertAlmostEqual(bridge.seek_to(25.5)["time"], 25.5, places=3)

        bridge.undo()
        self.assertEqual(bridge.notes, [])
        self.assertAlmostEqual(bridge.duration, 10.0)

    def test_same_audio_undo_still_restores_note_driven_duration(self):
        bridge = self._bridge()
        self._open(bridge, "song.wav", 10.0)
        bridge._push_undo()
        bridge.notes.append(Note(18.0, 20.0, 60.0).normalized())
        bridge.duration = 20.0

        bridge.undo()
        self.assertEqual(bridge.notes, [])
        self.assertAlmostEqual(bridge.duration, 10.0)
        bridge.redo()
        self.assertAlmostEqual(bridge.duration, 20.0)

    def test_undo_after_direct_reanalysis_keeps_direct_pitch_range(self):
        bridge = self._bridge()
        self._open(bridge, "song.ogg", 10.0, (40, 80))
        bridge.add_note(1.0, 2.0, 60.0)
        bridge.settings["analysisSource"] = "vorbis_direct"
        store = SimpleNamespace(
            duration=12.0,
            stats=SimpleNamespace(to_dict=lambda: {
                "storedBins": 1, "blocksProcessed": 1, "analysisSeconds": 0.0,
            }),
        )
        tracks = SimpleNamespace(stats=SimpleNamespace(to_dict=lambda: {"totalTrackCount": 0}))
        with (
            mock.patch.object(web_backend, "select_analysis_backend",
                              return_value=SimpleNamespace(selected="vorbis_direct")),
            mock.patch.object(web_backend, "analyze_vorbis_spectrum_store", return_value=store),
            mock.patch.object(web_backend, "build_frequency_track_store", return_value=tracks),
        ):
            self.assertEqual(bridge._analyze_current_audio(explicit=True), "vorbis_direct")

        bridge.undo()
        self.assertEqual(bridge.notes, [])
        self._assert_source_state(bridge, 12.0, (0, 127))

    def test_blank_workspace_history_keeps_document_bounds(self):
        """Without audio, duration and pitch range are document data and stay undoable."""
        bridge = self._bridge()
        self.assertIsNone(bridge.audio_path)
        bridge.duration = 12.0
        bridge._push_undo()
        bridge.notes.append(Note(30.0, 31.0, 60.0).normalized())
        bridge.duration = 33.0

        bridge.undo()
        self.assertAlmostEqual(bridge.duration, 12.0)


if __name__ == "__main__":
    unittest.main()

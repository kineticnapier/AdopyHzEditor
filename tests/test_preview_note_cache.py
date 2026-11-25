"""Preview data is cached per note so an edit only recomputes what changed."""

from __future__ import annotations

import threading
import unittest
from unittest import mock

import numpy as np

from core import audio_player
from core.note_model import Note


def _player():
    player = audio_player.AudioPlayer.__new__(audio_player.AudioPlayer)
    player.sr = 44_100
    player.lock = threading.RLock()
    player._preview_note_cache = {}
    return player


def _snapshot(player):
    return list(player.preview_notes), player._preview_hit_samples.copy(), list(player._preview_ends)


class PreviewNoteCacheTests(unittest.TestCase):
    def notes(self):
        return [
            Note(0.0, 0.2, 60.0).normalized(),
            Note(0.1, 0.4, 48.0, kind="curve", midi_end=55.0).normalized(),
            Note(0.5, 0.6, 72.0).normalized(),
        ]

    def test_an_edit_recomputes_only_the_changed_note(self):
        player = _player()
        notes = self.notes()
        player.set_preview_notes(notes)
        notes[2] = Note(0.5, 0.6, 73.0).normalized()
        with mock.patch.object(
            audio_player, "_prepare_preview_note", wraps=audio_player._prepare_preview_note
        ) as prepare:
            player.set_preview_notes(notes)
        self.assertEqual(prepare.call_count, 1)
        self.assertEqual(prepare.call_args.args[0], notes[2])

    def test_cached_result_matches_a_fresh_computation(self):
        notes = self.notes()
        warm = _player()
        warm.set_preview_notes(notes[:2])
        warm.set_preview_notes(notes)
        cold = _player()
        cold.set_preview_notes(notes)
        a, b = _snapshot(warm), _snapshot(cold)
        self.assertEqual(a[0], b[0])
        self.assertTrue(np.array_equal(a[1], b[1]))
        self.assertEqual(a[2], b[2])

    def test_cache_only_keeps_current_notes(self):
        player = _player()
        notes = self.notes()
        player.set_preview_notes(notes)
        player.set_preview_notes(notes[:1])
        self.assertEqual(len(player._preview_note_cache), 1)

    def test_velocity_and_layer_do_not_invalidate_the_cache(self):
        player = _player()
        player.set_preview_notes([Note(0.0, 0.2, 60.0, velocity=100)])
        with mock.patch.object(audio_player, "_prepare_preview_note") as prepare:
            player.set_preview_notes([Note(0.0, 0.2, 60.0, velocity=40, layer="B")])
        prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()

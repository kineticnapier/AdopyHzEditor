from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from importers.midi import import_midi
from web_ui import Bridge

PPQ = 480


def _varlen(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(out))


def _track(name: str | None, notes: list[tuple[int, int, int, int]], channel: int = 0) -> bytes:
    """notes: (start_tick, end_tick, pitch, velocity) on one channel."""
    events: list[tuple[int, bytes]] = []
    if name is not None:
        encoded = name.encode("utf-8")
        events.append((0, b"\xff\x03" + _varlen(len(encoded)) + encoded))
    for start, end, pitch, velocity in notes:
        events.append((start, bytes([0x90 | channel, pitch, velocity])))
        events.append((end, bytes([0x80 | channel, pitch, 0])))
    events.sort(key=lambda e: (e[0], e[1][0] & 0xF0 == 0x90))
    body = b""
    now = 0
    for tick, payload in events:
        body += _varlen(tick - now) + payload
        now = tick
    body += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def _midi_file(tracks: list[bytes]) -> bytes:
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), PPQ) + b"".join(tracks)


class MidiTrackImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "song.mid"
        self.path.write_bytes(_midi_file([
            _track(None, []),  # conductor track
            _track("Lead", [(0, 480, 72, 100), (480, 960, 74, 100)], channel=0),
            _track("Bass", [(0, 960, 36, 100)], channel=1),
            _track("Drum Kit", [(0, 120, 36, 100), (480, 600, 38, 100)], channel=2),
            _track("GM perc", [(0, 120, 42, 100)], channel=9),
        ]))

    def tearDown(self):
        self.tmp.cleanup()

    def test_track_summaries(self):
        result = import_midi(self.path)
        by_name = {t.name: t for t in result.tracks}
        self.assertEqual(by_name["Lead"].note_count, 2)
        self.assertEqual((by_name["Lead"].lowest, by_name["Lead"].highest), (72.0, 74.0))
        self.assertEqual(by_name["Bass"].channels, (1,))
        self.assertFalse(by_name["Lead"].looks_like_drums)
        self.assertTrue(by_name["Drum Kit"].looks_like_drums)  # by name
        self.assertTrue(by_name["GM perc"].looks_like_drums)  # by GM channel 10
        self.assertEqual(len(result.notes), 6)
        self.assertEqual(len(result.note_tracks), len(result.notes))

    def test_track_filter_keeps_only_chosen_tracks(self):
        result = import_midi(self.path, track_indices=[1, 2])
        self.assertEqual(sorted(n.midi for n in result.notes), [36.0, 72.0, 74.0])
        self.assertEqual(set(result.note_tracks), {1, 2})
        # Summaries still describe every track.
        self.assertEqual(len([t for t in result.tracks if t.note_count]), 4)


class MidiTrackBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "song.mid"
        self.path.write_bytes(_midi_file([
            _track("Lead", [(0, 480, 72, 100)], channel=0),
            _track("Drums", [(0, 120, 36, 100)], channel=9),
        ]))
        self.bridge = Bridge()

    def tearDown(self):
        self.tmp.cleanup()

    def _pick(self):
        with mock.patch.object(self.bridge, "_dialog", return_value=str(self.path)):
            return self.bridge.pick_midi_tracks_dialog()

    def test_pick_lists_tracks_without_importing(self):
        picked = self._pick()
        self.assertFalse(picked["cancelled"])
        self.assertEqual(picked["fileName"], "song.mid")
        self.assertEqual([(t["name"], t["drums"], t["channels"]) for t in picked["tracks"]],
                         [("Lead", False, [1]), ("Drums", True, [10])])
        self.assertEqual(self.bridge.notes, [])

    def test_cancelled_pick(self):
        with mock.patch.object(self.bridge, "_dialog", return_value=None):
            self.assertEqual(self.bridge.pick_midi_tracks_dialog(), {"cancelled": True})

    def test_import_only_chosen_tracks_with_one_undo_step(self):
        picked = self._pick()
        lead = next(t["index"] for t in picked["tracks"] if t["name"] == "Lead")
        with mock.patch.object(self.bridge, "_sync_notes_to_player"):
            state = self.bridge.import_midi_tracks([lead])
        self.assertTrue(state["dirty"])
        self.assertEqual([n.midi for n in self.bridge.notes], [72.0])
        self.assertEqual(len(self.bridge._undo_stack), 1)

    def test_import_requires_a_pick_and_valid_indices(self):
        with self.assertRaises(ValueError):
            self.bridge.import_midi_tracks([0])
        self._pick()
        for bad in (["0"], [0.5], [True]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.bridge.import_midi_tracks(bad)
        self.assertEqual(self.bridge.notes, [])

    def test_empty_selection_changes_nothing(self):
        self._pick()
        state = self.bridge.import_midi_tracks([])
        self.assertFalse(state["dirty"])
        self.assertEqual(self.bridge.notes, [])
        self.assertEqual(len(self.bridge._undo_stack), 0)


if __name__ == "__main__":
    unittest.main()

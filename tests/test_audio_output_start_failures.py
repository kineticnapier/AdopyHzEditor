from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from web.audio import WebAudioPlayer


class AudioOutputStartFailureTests(unittest.TestCase):
    def _player(self, factory) -> WebAudioPlayer:
        # Never open a real device: simulate PortAudio's output stream.
        player = WebAudioPlayer()
        player.sd = SimpleNamespace(OutputStream=factory)
        player.available = True
        player.error = None
        player.set_virtual_duration(1.0)
        return player

    def test_output_stream_constructor_failure_is_reported_in_snapshot(self):
        factory = mock.Mock(side_effect=OSError("no default output device"))
        player = self._player(factory)

        player.play()

        self.assertFalse(player.available)
        self.assertFalse(player.snapshot().playing)
        self.assertIsNone(player.stream)
        self.assertIn("no default output device", player.snapshot().error or "")
        factory.assert_called_once()
        # Once unavailable, another click cannot repeatedly raise the error.
        player.play()
        factory.assert_called_once()

    def test_start_failure_closes_stream_and_reports_error(self):
        stream = mock.Mock()
        stream.start.side_effect = RuntimeError("device disconnected")
        player = self._player(mock.Mock(return_value=stream))

        player.play()

        self.assertFalse(player.available)
        self.assertFalse(player.playing)
        self.assertIsNone(player.stream)
        self.assertIn("device disconnected", player.snapshot().error or "")
        stream.close.assert_called_once()

    def test_cleanup_failure_does_not_hide_original_start_error(self):
        stream = mock.Mock()
        stream.start.side_effect = RuntimeError("start failed")
        stream.close.side_effect = OSError("close failed")
        player = self._player(mock.Mock(return_value=stream))

        player.play()

        self.assertFalse(player.available)
        self.assertIsNone(player.stream)
        self.assertIn("start failed", player.error or "")

    def test_successful_start_still_plays_and_stops_normally(self):
        stream = mock.Mock()
        player = self._player(mock.Mock(return_value=stream))

        player.play()

        self.assertTrue(player.available)
        self.assertTrue(player.snapshot().playing)
        self.assertIsNone(player.error)
        self.assertIs(player.stream, stream)
        stream.start.assert_called_once()

        player.stop()
        self.assertFalse(player.playing)
        self.assertIsNone(player.stream)
        stream.stop.assert_called_once()
        stream.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

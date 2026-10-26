from __future__ import annotations

import threading
import unittest

import numpy as np

from core.audio_player import AudioPlayer
from web.audio import WebAudioPlayer


class _LockCheckingStream:
    def __init__(self, player: AudioPlayer) -> None:
        self.player = player
        self.stop_timed_out = False

    def stop(self) -> None:
        acquired = threading.Event()

        def enter_callback_lock() -> None:
            with self.player.lock:
                acquired.set()

        worker = threading.Thread(target=enter_callback_lock)
        worker.start()
        if not acquired.wait(0.5):
            self.stop_timed_out = True
        worker.join(timeout=1.0)

    def close(self) -> None:
        pass


class AudioStopLockingRegressionTests(unittest.TestCase):
    def test_stream_stop_waits_without_holding_callback_lock(self):
        operations = ("pause", "stop", "set_audio", "clear_audio")
        for operation in operations:
            with self.subTest(operation=operation):
                player = AudioPlayer()
                stream = _LockCheckingStream(player)
                player.stream = stream
                player.playing = True
                player.audio = np.zeros((10, 1), dtype=np.float32)
                if operation == "set_audio":
                    player.set_audio(np.ones((20, 1), dtype=np.float32), 20)
                else:
                    getattr(player, operation)()
                self.assertFalse(stream.stop_timed_out)

    def test_web_stop_without_reset_releases_callback_lock_and_keeps_position(self):
        player = WebAudioPlayer()
        stream = _LockCheckingStream(player)
        player.stream = stream
        player.playing = True
        player.audio = np.zeros((20, 1), dtype=np.float32)
        player.pos = 7
        player._pos_float = 7.25

        player.stop(reset=False)

        self.assertFalse(stream.stop_timed_out)
        self.assertEqual(player.pos, 7)
        self.assertEqual(player._pos_float, 7.25)


if __name__ == "__main__":
    unittest.main()

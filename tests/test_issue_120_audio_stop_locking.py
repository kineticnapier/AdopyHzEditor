from __future__ import annotations

import threading
import unittest

import numpy as np

from core.audio_player import AudioPlayer


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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import threading
import unittest
from unittest import mock

import numpy as np

import web.backend as web_backend
from core.audio_analysis import Spectrogram
from web_ui import Bridge


def _spectrogram(tag: str) -> Spectrogram:
    return Spectrogram(
        audio_path=tag,
        db=np.linspace(-80.0, 0.0, 400, dtype=np.float32).reshape(4, 100),
        duration=10.0,
        midi_min=60,
        midi_max=63,
        frame_times=np.linspace(0.0, 10.0, 100, dtype=np.float32),
        sr=22_050,
        pitch_step=1.0,
    )


class CqtRenderLockTests(unittest.TestCase):
    def test_slow_render_does_not_block_view_updates(self):
        bridge = Bridge()
        bridge.spectrogram = _spectrogram("first.wav")
        bridge.duration = 10.0
        entered = threading.Event()
        release = threading.Event()
        view_done = threading.Event()
        render_result: list[dict] = []

        def slow_enhance(data, **_kwargs):
            entered.set()
            if not release.wait(2.0):
                raise RuntimeError("test render was not released")
            return np.asarray(data, dtype=np.float32)

        with mock.patch.object(
            web_backend,
            "enhance_spectrogram",
            side_effect=slow_enhance,
        ):
            render = threading.Thread(
                target=lambda: render_result.append(
                    bridge.get_spectrogram(128, 1.0, 3.0)
                )
            )
            render.start()
            self.assertTrue(entered.wait(1.0))

            def update_view():
                bridge.set_view({"start": 2.0, "windowSeconds": 4.0})
                view_done.set()

            view_thread = threading.Thread(target=update_view)
            view_thread.start()
            responsive = view_done.wait(0.5)
            release.set()
            render.join(2.0)
            view_thread.join(2.0)

        self.assertTrue(responsive, "set_view waited for CQT image generation")
        self.assertFalse(render.is_alive())
        self.assertFalse(view_thread.is_alive())
        self.assertTrue(render_result[0]["available"])

    def test_replaced_spectrogram_marks_inflight_render_stale(self):
        bridge = Bridge()
        first = _spectrogram("first.wav")
        bridge.spectrogram = first
        bridge.duration = 10.0
        entered = threading.Event()
        release = threading.Event()
        result: list[dict] = []

        def slow_enhance(data, **_kwargs):
            entered.set()
            if not release.wait(2.0):
                raise RuntimeError("test render was not released")
            return np.asarray(data, dtype=np.float32)

        with mock.patch.object(
            web_backend,
            "enhance_spectrogram",
            side_effect=slow_enhance,
        ):
            worker = threading.Thread(
                target=lambda: result.append(
                    bridge.get_spectrogram(128, 0.0, 2.0)
                )
            )
            worker.start()
            self.assertTrue(entered.wait(1.0))
            with bridge._lock:
                bridge.spectrogram = _spectrogram("second.wav")
            release.set()
            worker.join(2.0)

        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [{"available": False, "stale": True}])


if __name__ == "__main__":
    unittest.main()

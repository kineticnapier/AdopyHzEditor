from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest import mock

from core.note_model import Note
import exporters.adofai as adofai


class AdoFAIConcurrencyRegressionTests(unittest.TestCase):
    def test_parallel_builds_match_isolated_results(self):
        inputs = [
            [Note(0.0, 0.45, 57.0), Note(0.6, 1.2, 81.0)],
            [Note(0.0, 0.8, 69.0, kind="curve", midi_end=48.0, ctrl1_midi=76.0, ctrl2_midi=52.0)],
        ]
        options = {
            "method": "angle_only",
            "angle_only_bpm": 1600.0,
            "visual_path_mode": "auto route twirl",
            "final_angle_mode": "scaled",
        }
        expected = [adofai.build_adofai_level(notes, **options) for notes in inputs]
        barrier = threading.Barrier(2)
        per_thread = threading.local()
        original_add_relative = adofai.add_relative

        def interleaved_add_relative(*args, **kwargs):
            if not getattr(per_thread, "waited", False):
                per_thread.waited = True
                barrier.wait(timeout=2.0)
            return original_add_relative(*args, **kwargs)

        with mock.patch.object(adofai, "add_relative", side_effect=interleaved_add_relative):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(adofai.build_adofai_level, notes, **options) for notes in inputs]
                actual = [future.result(timeout=5.0) for future in futures]

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()

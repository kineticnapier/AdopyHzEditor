from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import core.audio_analysis as audio_analysis
from core.audio_analysis import Spectrogram
from core.note_model import Note
import tools.quick_hz as quick_hz
import web.adofai as web_adofai
from web.backend import Bridge as CoreBridge
from web_ui import Bridge


class IssuePerformanceRegressionTests(unittest.TestCase):
    def test_quick_hz_text_materializes_only_visible_preview_rows(self):
        info = quick_hz.CalculateHzInfo(120.0, 4.0)
        with mock.patch.object(quick_hz, "GenerateHzPreview", wraps=quick_hz.GenerateHzPreview) as generate:
            output = quick_hz.GenerateOutputText(info, 0, 1_000_000)
        self.assertEqual(generate.call_args.args[2], 200)
        self.assertIn("999800 more rows omitted", output)

    def test_undo_snapshots_share_unchanged_note_objects(self):
        bridge = CoreBridge()
        bridge.notes = [Note(i, i + 0.5, 60 + i % 12) for i in range(1000)]
        bridge._push_undo()
        snapshot = bridge._undo_stack[-1]
        self.assertIsInstance(snapshot, tuple)
        self.assertIs(snapshot[500], bridge.notes[500])

    def test_spectrogram_request_slices_to_view_before_downsampling(self):
        bridge = CoreBridge()
        frames = np.linspace(0, 100, 10_001)
        bridge.spectrogram = Spectrogram(
            audio_path="long.wav", db=np.zeros((2, len(frames)), dtype=np.float32), duration=100,
            midi_min=60, midi_max=61, frame_times=frames, sr=44100,
        )
        result = bridge.get_spectrogram(300, 40, 42)
        self.assertEqual(result["start"], 40.0)
        self.assertEqual(result["end"], 42.0)
        self.assertLessEqual(result["cols"], 300)

    def test_cache_hit_refreshes_lru_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "audio.wav"
            audio.write_bytes(b"cache-key-source")
            with mock.patch.object(audio_analysis.Path, "home", return_value=root):
                cache = audio_analysis.analysis_cache_path(audio)
                cache.parent.mkdir(exist_ok=True)
                audio_analysis._save_analysis_cache(
                    cache,
                    db=np.zeros((2, 2), dtype=np.float32), duration=np.array(1.0),
                    midi_min=np.array(12), midi_max=np.array(108), frame_times=np.array([0.0, 1.0]),
                    sr=np.array(22050), bins_per_semitone=np.array(1), folded_to_semitone=np.array(True),
                    bins_per_octave=np.array(12), pitch_step=np.array(1.0),
                )
                old = time.time() - 3600
                os.utime(cache, (old, old))
                audio_analysis.analyze_cqt(audio)
                self.assertGreater(cache.stat().st_mtime, old + 100)

    def test_tile_preview_caps_chart_materialization_but_reports_estimate(self):
        bridge = Bridge()
        bridge.notes = [Note(0, 1, 60)]
        captured = {}

        def fake_build(_notes, **options):
            captured.update(options)
            return {"angleData": [0, 180]}, {"floors_total": 1}

        with (
            mock.patch.object(web_adofai, "build_adofai_debug_rows", return_value=[{"tiles_est": 50_000}]),
            mock.patch.object(web_adofai, "build_adofai_level", side_effect=fake_build),
        ):
            result = bridge.preview_adofai_tiles({"maxTiles": 200_000})
        self.assertEqual(captured["max_tiles"], 5000)
        self.assertEqual(result["totalTiles"], 50_000)
        self.assertTrue(result["limited"])


if __name__ == "__main__":
    unittest.main()

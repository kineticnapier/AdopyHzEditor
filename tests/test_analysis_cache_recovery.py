from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import core.audio_analysis as audio_analysis


class _FakeLibrosa:
    def __init__(self) -> None:
        self.analysis_calls = 0

    def load(self, _path, *, sr, mono):
        self.analysis_calls += 1
        return np.ones(4096, dtype=np.float32), sr

    def get_duration(self, *, y, sr):
        return len(y) / sr

    def hybrid_cqt(self, _y, **kwargs):
        return np.ones((kwargs["n_bins"], 4), dtype=np.complex64)

    cqt = hybrid_cqt

    def amplitude_to_db(self, mag, *, ref):
        del ref
        return np.asarray(mag, dtype=np.float32)

    def frames_to_time(self, frames, *, sr, hop_length):
        return np.asarray(frames, dtype=np.float64) * hop_length / sr


class AnalysisCacheRecoveryTests(unittest.TestCase):
    def _analyze(self, audio: Path, home: Path, fake: _FakeLibrosa):
        with (
            mock.patch.dict(sys.modules, {"librosa": fake}),
            mock.patch.object(audio_analysis.Path, "home", return_value=home),
        ):
            return audio_analysis.analyze_cqt(
                audio,
                sr=8000,
                midi_min=24,
                midi_max=48,
                hop_length=512,
                engine="hybrid",
            )

    def test_normal_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "song.wav"
            audio.write_bytes(b"audio")
            fake = _FakeLibrosa()

            first = self._analyze(audio, root, fake)
            second = self._analyze(audio, root, fake)

            self.assertEqual(fake.analysis_calls, 1)
            np.testing.assert_array_equal(first.db, second.db)

    def test_corrupt_cache_is_reanalyzed_and_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "song.wav"
            audio.write_bytes(b"audio")
            fake = _FakeLibrosa()
            with mock.patch.object(audio_analysis.Path, "home", return_value=root):
                cache_path = audio_analysis.analysis_cache_path(
                    audio,
                    sr=8000,
                    midi_min=24,
                    midi_max=48,
                    hop_length=512,
                    engine="hybrid",
                )
            cache_path.parent.mkdir()
            cache_path.write_bytes(b"truncated npz")

            result = self._analyze(audio, root, fake)

            self.assertEqual(fake.analysis_calls, 1)
            self.assertGreater(result.db.size, 0)
            loaded = audio_analysis._load_analysis_cache(cache_path, audio)
            np.testing.assert_array_equal(loaded.db, result.db)

    def test_cache_replace_failure_preserves_existing_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            cache_path = directory / "known.npz"
            cache_path.write_bytes(b"known-good")

            with mock.patch.object(audio_analysis.os, "replace", side_effect=OSError("locked")):
                with self.assertRaises(OSError):
                    audio_analysis._save_analysis_cache(
                        cache_path,
                        db=np.ones((2, 2), dtype=np.float32),
                    )

            self.assertEqual(cache_path.read_bytes(), b"known-good")
            self.assertEqual(list(directory.glob(".known.npz.*.tmp")), [])

    def test_stale_cache_cleanup_removes_oldest_and_keeps_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            oldest = directory / "oldest.npz"
            middle = directory / "middle.npz"
            current = directory / "current.npz"
            for path in (oldest, middle, current):
                path.write_bytes(b"x" * 10)
            os.utime(oldest, (1, 1))
            os.utime(middle, (2, 2))
            os.utime(current, (3, 3))

            audio_analysis.cleanup_analysis_cache(
                directory,
                max_bytes=15,
                exclude={current},
            )

            self.assertFalse(oldest.exists())
            self.assertFalse(middle.exists())
            self.assertTrue(current.exists())


if __name__ == "__main__":
    unittest.main()

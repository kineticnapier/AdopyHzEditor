from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import core.adofai_assets as adofai_assets
from core.audio_player import AudioPlayer
from core.note_model import Note, hz_to_midi


class AdoFaiKickPreviewTests(unittest.TestCase):
    def _player(self) -> AudioPlayer:
        player = AudioPlayer()
        player.sr = 1000
        player.note_sound_enabled = True
        player.note_volume = 1.0
        player.note_instrument = "adofai_kick"
        return player

    def test_adofai_kick_is_a_supported_preview_instrument(self):
        player = self._player()
        self.assertEqual(player._normalize_note_instrument("ADOFAI Kick"), "adofai_kick")
        self.assertEqual(player._normalize_note_instrument("kick"), "adofai_kick")

    def test_kick_repeats_at_every_fixed_note_phase_cycle(self):
        player = self._player()
        player.sr = 4400
        player.set_note_sample(np.array([1.0, 0.0], dtype=np.float32))
        player.set_preview_notes([Note(0.100, 0.150, 69.0)])

        positions = np.arange(430.0, 670.0, dtype=np.float64)
        output = np.zeros((len(positions), 1), dtype=np.float32)
        player._mix_preview_notes(output, positions)

        nonzero = np.flatnonzero(np.abs(output[:, 0]) > 1e-6)
        expected = [10 + 10 * i for i in range(22)]
        self.assertEqual(nonzero.tolist(), expected)

    def test_kick_tail_is_not_clipped_to_note_end(self):
        player = self._player()
        player.sr = 4400
        player.set_note_sample(np.ones(80, dtype=np.float32))
        player.set_preview_notes([Note(0.100, 0.105, 69.0)])

        positions = np.arange(430.0, 550.0, dtype=np.float64)
        output = np.zeros((len(positions), 1), dtype=np.float32)
        player._mix_preview_notes(output, positions)

        self.assertTrue(np.allclose(output[:10], 0.0))
        self.assertGreater(float(output[10, 0]), 0.9)
        self.assertGreater(float(output[80, 0]), 0.9)

    def test_curve_segmentation_keeps_one_continuous_hit_train(self):
        player = self._player()
        player.sr = 4400
        player.set_note_sample(np.array([1.0, 0.0], dtype=np.float32))
        player.set_preview_notes([
            Note(
                0.100,
                0.150,
                69.0,
                kind="curve",
                midi_end=69.0,
                ctrl1_midi=69.0,
                ctrl2_midi=69.0,
            )
        ])
        self.assertGreater(len(player.preview_notes), 2)

        positions = np.arange(430.0, 670.0, dtype=np.float64)
        output = np.zeros((len(positions), 1), dtype=np.float32)
        player._mix_preview_notes(output, positions)

        nonzero = np.flatnonzero(np.abs(output[:, 0]) > 1e-6)
        expected = [10 + 10 * i for i in range(22)]
        self.assertEqual(nonzero.tolist(), expected)

    def test_missing_kick_sample_falls_back_to_synth_preview(self):
        player = self._player()
        player.set_preview_notes([Note(0.100, 0.200, 69.0)])
        positions = np.arange(100.0, 130.0, dtype=np.float64)
        output = np.zeros((len(positions), 1), dtype=np.float32)

        player._mix_preview_notes(output, positions)

        self.assertGreater(float(np.max(np.abs(output))), 0.1)

    def test_10khz_preview_builds_dense_hit_train_and_fft_mixes_it(self):
        player = self._player()
        player.sr = 44100
        player.set_note_sample(np.linspace(1.0, 0.0, 512, dtype=np.float32))
        player.set_preview_notes([Note(0.0, 0.1, hz_to_midi(10000.0))])

        self.assertEqual(len(player._preview_hit_samples), 1000)

        positions = np.arange(0.0, 1024.0, dtype=np.float64)
        output = np.zeros((len(positions), 1), dtype=np.float32)
        player._mix_preview_notes(output, positions)

        self.assertTrue(np.all(np.isfinite(output)))
        self.assertGreater(float(np.max(np.abs(output))), 0.0)
        self.assertTrue(player._note_sample_fft_cache)


class AdoFaiAssetLocatorTests(unittest.TestCase):
    def _make_game(self, root: Path) -> Path:
        game = root / "steamapps" / "common" / "A Dance of Fire and Ice"
        data = game / "A Dance of Fire and Ice_Data"
        data.mkdir(parents=True)
        (data / "resources.assets").write_bytes(b"assets")
        (data / "resources.assets.resS").write_bytes(b"resource")
        return game

    def test_finds_adofai_in_secondary_steam_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            steam = base / "Steam"
            library = base / "Library"
            (steam / "steamapps").mkdir(parents=True)
            game = self._make_game(library)

            (steam / "steamapps" / "libraryfolders.vdf").write_text(
                '"libraryfolders"\n{\n  "1" { "path" "' + str(library) + '" }\n}\n',
                encoding="utf-8",
            )
            (library / "steamapps" / f"appmanifest_{adofai_assets.STEAM_APP_ID}.acf").write_text(
                '"AppState"\n{\n  "installdir" "A Dance of Fire and Ice"\n}\n',
                encoding="utf-8",
            )

            env = {
                "STEAM_PATH": str(steam),
                "PROGRAMFILES": "",
                "PROGRAMFILES(X86)": "",
                "ADOPYHZ_ADOFAI_PATH": "",
            }
            with mock.patch.dict(os.environ, env, clear=False):
                self.assertEqual(adofai_assets.find_adofai_installation(), game.resolve())

    def test_cached_kick_is_reused_when_source_signature_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            game = self._make_game(base / "game-root")
            local = base / "local"
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False):
                kick = adofai_assets.adofai_kick_cache_path()
                kick.parent.mkdir(parents=True)
                kick.write_bytes(b"RIFF" + b"\0" * 100)
                adofai_assets._cache_manifest_path().write_text(
                    json.dumps(adofai_assets._source_signature(game)),
                    encoding="utf-8",
                )
                with (
                    mock.patch.object(adofai_assets, "find_adofai_installation", return_value=game),
                    mock.patch.object(adofai_assets, "_run_extractor") as extractor,
                ):
                    self.assertEqual(adofai_assets.ensure_adofai_kick(), kick)
                extractor.assert_not_called()


if __name__ == "__main__":
    unittest.main()

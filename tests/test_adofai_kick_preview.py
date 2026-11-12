from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import wave
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

        self.assertLess(float(np.max(np.abs(output[:10]))), 1e-5)
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
    @staticmethod
    def _wav_bytes(samples: bytes) -> bytes:
        with io.BytesIO() as output:
            with wave.open(output, "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(44100)
                writer.writeframes(samples)
            return output.getvalue()

    def test_large_valid_kick_wav_is_checked_in_bounded_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.wav"
            path.write_bytes(self._wav_bytes(b"AB" * 40_000))
            requested: list[int] = []
            original_open = wave.open

            def tracked_open(*args, **kwargs):
                reader = original_open(*args, **kwargs)
                original_readframes = reader.readframes

                def tracked_readframes(count: int):
                    requested.append(count)
                    return original_readframes(count)

                reader.readframes = tracked_readframes
                return reader

            with mock.patch.object(adofai_assets.wave, "open", side_effect=tracked_open):
                self.assertTrue(adofai_assets._valid_kick_wav(path))
            self.assertGreater(len(requested), 1)
            self.assertLessEqual(max(requested), 16_384)
            self.assertEqual(sum(requested), 40_000)

    def test_large_kick_wav_truncated_after_first_chunk_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "truncated.wav"
            path.write_bytes(self._wav_bytes(b"AB" * 40_000)[:-2])
            self.assertFalse(adofai_assets._valid_kick_wav(path))

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
                kick.write_bytes(self._wav_bytes(b"\x01\x02" * 50))
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


    def test_failed_forced_refresh_preserves_cached_kick_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            game = self._make_game(base / "game-root")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(base / "local")}, clear=False):
                kick = adofai_assets.adofai_kick_cache_path()
                kick.parent.mkdir(parents=True)
                original = self._wav_bytes(b"\x03\x04" * 50)
                kick.write_bytes(original)
                manifest = adofai_assets._cache_manifest_path()
                manifest.write_text(json.dumps(adofai_assets._source_signature(game)), encoding="utf-8")
                original_manifest = manifest.read_bytes()

                def fail_after_partial_write(_game: Path, output: Path) -> None:
                    self.assertNotEqual(output, kick)
                    self.assertEqual(output.suffix, ".wav")
                    output.write_bytes(b"partial")
                    raise RuntimeError("simulated extractor failure")

                with (
                    mock.patch.object(adofai_assets, "find_adofai_installation", return_value=game),
                    mock.patch.object(adofai_assets, "_run_extractor", side_effect=fail_after_partial_write),
                ):
                    with self.assertRaisesRegex(RuntimeError, "simulated extractor failure"):
                        adofai_assets.ensure_adofai_kick(force=True)

                self.assertEqual(kick.read_bytes(), original)
                self.assertEqual(manifest.read_bytes(), original_manifest)
                self.assertEqual(list(kick.parent.glob("sndKick-*.wav")), [])

    def test_rollback_attempts_manifest_restore_after_wav_restore_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            game = self._make_game(base / "game-root")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(base / "local")}, clear=False):
                kick = adofai_assets.adofai_kick_cache_path()
                kick.parent.mkdir(parents=True)
                old = self._wav_bytes(bytes([1, 2]) * 50)
                new = self._wav_bytes(bytes([3, 4]) * 50)
                kick.write_bytes(old)
                manifest = adofai_assets._cache_manifest_path()
                manifest.write_text(json.dumps(adofai_assets._source_signature(game)), encoding="utf-8")
                old_manifest = manifest.read_bytes()
                original_replace = Path.replace
                attempted: list[str] = []

                def fail_publish_and_wav_restore(source: Path, target: Path):
                    if source.name == "sndKick.source.json" and target == manifest:
                        raise OSError("manifest publish failed")
                    if source.name == "old-sndKick.wav" and target == kick:
                        attempted.append("wav")
                        raise OSError("wav restore failed")
                    if source.name == "old-sndKick.source.json" and target == manifest:
                        attempted.append("manifest")
                    return original_replace(source, target)

                with (
                    mock.patch.object(adofai_assets, "find_adofai_installation", return_value=game),
                    mock.patch.object(adofai_assets, "_run_extractor",
                                      side_effect=lambda _game, output: output.write_bytes(new)),
                    mock.patch.object(Path, "replace", autospec=True,
                                      side_effect=fail_publish_and_wav_restore),
                ):
                    with self.assertRaisesRegex(ExceptionGroup, "rollback failed") as caught:
                        adofai_assets.ensure_adofai_kick(force=True)

                # Preserve both the original publication failure and the
                # rollback failure for diagnostics.
                self.assertEqual(len(caught.exception.exceptions), 2)
                self.assertIn("manifest", str(caught.exception.exceptions[0]).lower())
                self.assertIn("restore", str(caught.exception.exceptions[1]).lower())
                self.assertEqual(attempted, ["wav", "manifest"])
                self.assertEqual(manifest.read_bytes(), old_manifest)

    def test_manifest_publish_failure_restores_both_cache_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            game = self._make_game(base / "game-root")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(base / "local")}, clear=False):
                kick = adofai_assets.adofai_kick_cache_path()
                kick.parent.mkdir(parents=True)
                old = self._wav_bytes(b"\\x01\\x02" * 50)
                new = self._wav_bytes(b"\\x03\\x04" * 50)
                kick.write_bytes(old)
                manifest = adofai_assets._cache_manifest_path()
                manifest.write_text(json.dumps(adofai_assets._source_signature(game)), encoding="utf-8")
                old_manifest = manifest.read_bytes()
                original_replace = Path.replace

                def fail_manifest_publish(source: Path, target: Path):
                    if source.name == "sndKick.source.json" and target == manifest:
                        raise OSError("simulated manifest publication failure")
                    return original_replace(source, target)

                with (
                    mock.patch.object(adofai_assets, "find_adofai_installation", return_value=game),
                    mock.patch.object(adofai_assets, "_run_extractor",
                                      side_effect=lambda _game, output: output.write_bytes(new)),
                    mock.patch.object(Path, "replace", autospec=True, side_effect=fail_manifest_publish),
                ):
                    with self.assertRaisesRegex(OSError, "simulated manifest publication failure"):
                        adofai_assets.ensure_adofai_kick(force=True)

                self.assertEqual(kick.read_bytes(), old)
                self.assertEqual(manifest.read_bytes(), old_manifest)
                self.assertEqual(list(kick.parent.glob("sndKick-refresh-*")), [])

    def test_successful_forced_refresh_replaces_cache_after_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            game = self._make_game(base / "game-root")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(base / "local")}, clear=False):
                kick = adofai_assets.adofai_kick_cache_path()
                kick.parent.mkdir(parents=True)
                old = self._wav_bytes(b"\x05\x06" * 50)
                new = self._wav_bytes(b"\x07\x08" * 50)
                kick.write_bytes(old)

                def write_new_kick(_game: Path, output: Path) -> None:
                    self.assertNotEqual(output, kick)
                    self.assertEqual(kick.read_bytes(), old)
                    output.write_bytes(new)

                with (
                    mock.patch.object(adofai_assets, "find_adofai_installation", return_value=game),
                    mock.patch.object(adofai_assets, "_run_extractor", side_effect=write_new_kick),
                ):
                    self.assertEqual(adofai_assets.ensure_adofai_kick(force=True), kick)

                self.assertEqual(kick.read_bytes(), new)
                manifest = adofai_assets._cache_manifest_path()
                self.assertEqual(json.loads(manifest.read_text(encoding="utf-8")),
                                 adofai_assets._source_signature(game))
                self.assertEqual(list(kick.parent.glob("sndKick-*.wav")), [])

    def test_short_extractor_output_does_not_replace_existing_kick(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            game = self._make_game(base / "game-root")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(base / "local")}, clear=False):
                kick = adofai_assets.adofai_kick_cache_path()
                kick.parent.mkdir(parents=True)
                old = self._wav_bytes(b"\x05\x06" * 50)
                kick.write_bytes(old)

                def write_short_kick(_game: Path, output: Path) -> None:
                    output.write_bytes(b"RIFF")

                with (
                    mock.patch.object(adofai_assets, "find_adofai_installation", return_value=game),
                    mock.patch.object(adofai_assets, "_run_extractor", side_effect=write_short_kick),
                ):
                    with self.assertRaisesRegex(RuntimeError, "without a valid sndKick.wav"):
                        adofai_assets.ensure_adofai_kick(force=True)

                self.assertEqual(kick.read_bytes(), old)
                self.assertEqual(list(kick.parent.glob("sndKick-*.wav")), [])

    def test_invalid_cached_wav_is_not_reused_even_with_matching_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            game = self._make_game(base / "game-root")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(base / "local")}, clear=False):
                kick = adofai_assets.adofai_kick_cache_path()
                kick.parent.mkdir(parents=True)
                kick.write_bytes(b"RIFF" + b"x" * 100)
                adofai_assets._cache_manifest_path().write_text(
                    json.dumps(adofai_assets._source_signature(game)), encoding="utf-8"
                )
                replacement = self._wav_bytes(b"\x09\x0a" * 50)

                def extract(_game: Path, output: Path) -> None:
                    output.write_bytes(replacement)

                with (
                    mock.patch.object(adofai_assets, "find_adofai_installation", return_value=game),
                    mock.patch.object(adofai_assets, "_run_extractor", side_effect=extract) as extractor,
                ):
                    self.assertEqual(adofai_assets.ensure_adofai_kick(), kick)

                extractor.assert_called_once()
                self.assertEqual(kick.read_bytes(), replacement)

    def test_truncated_wav_header_does_not_replace_cached_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            game = self._make_game(base / "game-root")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(base / "local")}, clear=False):
                kick = adofai_assets.adofai_kick_cache_path()
                kick.parent.mkdir(parents=True)
                old = self._wav_bytes(b"\x01\x02" * 50)
                kick.write_bytes(old)
                manifest = adofai_assets._cache_manifest_path()
                manifest.write_text(json.dumps(adofai_assets._source_signature(game)), encoding="utf-8")
                original_manifest = manifest.read_bytes()
                truncated = self._wav_bytes(b"\x03\x04" * 50)[:-20]

                with (
                    mock.patch.object(adofai_assets, "find_adofai_installation", return_value=game),
                    mock.patch.object(adofai_assets, "_run_extractor",
                                      side_effect=lambda _game, output: output.write_bytes(truncated)),
                ):
                    with self.assertRaisesRegex(RuntimeError, "without a valid sndKick.wav"):
                        adofai_assets.ensure_adofai_kick(force=True)

                self.assertEqual(kick.read_bytes(), old)
                self.assertEqual(manifest.read_bytes(), original_manifest)
                self.assertEqual(list(kick.parent.glob("sndKick-*.wav")), [])

    def test_invalid_wav_header_over_44_bytes_does_not_replace_cached_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            game = self._make_game(base / "game-root")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(base / "local")}, clear=False):
                kick = adofai_assets.adofai_kick_cache_path()
                kick.parent.mkdir(parents=True)
                old = self._wav_bytes(b"\x01\x02" * 50)
                kick.write_bytes(old)
                with (
                    mock.patch.object(adofai_assets, "find_adofai_installation", return_value=game),
                    mock.patch.object(adofai_assets, "_run_extractor",
                                      side_effect=lambda _game, output: output.write_bytes(b"not-wav" * 30)),
                ):
                    with self.assertRaisesRegex(RuntimeError, "without a valid sndKick.wav"):
                        adofai_assets.ensure_adofai_kick(force=True)

                self.assertEqual(kick.read_bytes(), old)
                self.assertEqual(list(kick.parent.glob("sndKick-*.wav")), [])

    def test_riff_header_claiming_bytes_beyond_eof_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sndKick.wav"
            valid = self._wav_bytes(bytes([1, 2]) * 50)
            # wave.open() can still read every PCM frame despite this
            # impossible outer RIFF size.
            malformed = valid[:4] + (len(valid) + 100).to_bytes(4, "little") + valid[8:]
            path.write_bytes(malformed)
            self.assertFalse(adofai_assets._valid_kick_wav(path))

    def test_oversized_riff_header_does_not_replace_existing_kick(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            game = self._make_game(base / "game-root")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(base / "local")}, clear=False):
                kick = adofai_assets.adofai_kick_cache_path()
                kick.parent.mkdir(parents=True)
                old = self._wav_bytes(bytes([1, 2]) * 50)
                kick.write_bytes(old)
                manifest = adofai_assets._cache_manifest_path()
                manifest.write_text(json.dumps(adofai_assets._source_signature(game)), encoding="utf-8")
                old_manifest = manifest.read_bytes()
                bad = old[:4] + (len(old) + 100).to_bytes(4, "little") + old[8:]
                with (
                    mock.patch.object(adofai_assets, "find_adofai_installation", return_value=game),
                    mock.patch.object(adofai_assets, "_run_extractor",
                                      side_effect=lambda _game, output: output.write_bytes(bad)),
                ):
                    with self.assertRaisesRegex(RuntimeError, "without a valid sndKick.wav"):
                        adofai_assets.ensure_adofai_kick(force=True)
                self.assertEqual(kick.read_bytes(), old)
                self.assertEqual(manifest.read_bytes(), old_manifest)
                self.assertEqual(list(kick.parent.glob("sndKick-*.wav")), [])

    def test_malformed_riff_chunk_length_is_rejected_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sndKick.wav"
            # The RIFF chunk claims only 16 bytes, but its JUNK child claims
            # far more. Python's wave reader can raise RuntimeError here.
            path.write_bytes(
                b"RIFF" + (16).to_bytes(4, "little") + b"WAVE" +
                b"JUNK" + (0xffffffff).to_bytes(4, "little") + b"x" * 80
            )
            self.assertFalse(adofai_assets._valid_kick_wav(path))

    def test_frozen_build_prefers_bundled_extractor(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "AdopyHzEditor.exe"
            expected = exe.parent / "AssetExtractor" / adofai_assets._EXTRACTOR_NAME
            with (
                mock.patch.object(adofai_assets.sys, "frozen", True, create=True),
                mock.patch.object(adofai_assets.sys, "executable", str(exe)),
            ):
                self.assertEqual(adofai_assets._extractor_candidates()[0], expected)

    def test_frozen_build_runs_bundled_extractor_without_dotnet(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "AdopyHzEditor.exe"
            bundled = exe.parent / "AssetExtractor" / adofai_assets._EXTRACTOR_NAME
            bundled.parent.mkdir(parents=True)
            bundled.write_bytes(b"test executable placeholder")
            game_root = Path(tmp) / "game"
            output = Path(tmp) / "sndKick.wav"

            with (
                mock.patch.object(adofai_assets.sys, "frozen", True, create=True),
                mock.patch.object(adofai_assets.sys, "executable", str(exe)),
                mock.patch.object(adofai_assets.shutil, "which", return_value=None) as which,
                mock.patch.object(
                    adofai_assets.subprocess,
                    "run",
                    return_value=mock.Mock(returncode=0, stdout="", stderr=""),
                ) as run,
            ):
                adofai_assets._run_extractor(game_root, output)

            which.assert_not_called()
            run.assert_called_once()
            self.assertEqual(
                run.call_args.args[0],
                [str(bundled), "--adofai", str(game_root), "--output", str(output)],
            )
            self.assertEqual(run.call_args.kwargs["timeout"], 600)
            self.assertFalse(run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()

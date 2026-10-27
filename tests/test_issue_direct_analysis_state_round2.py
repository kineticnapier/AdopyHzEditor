from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

import web.backend as web_backend
import web.io as web_io
import web.tools as web_tools
from core.audio_analysis import Spectrogram
from web.audio import DecodedAudio
from web_ui import Bridge


def _decoded() -> DecodedAudio:
    return DecodedAudio(np.zeros((4410, 1), dtype=np.float32), 44_100)


def _cqt(path: str) -> Spectrogram:
    return Spectrogram(
        audio_path=path,
        db=np.zeros((4, 8), dtype=np.float32),
        duration=0.1,
        midi_min=60,
        midi_max=63,
        frame_times=np.linspace(0.0, 0.1, 8, dtype=np.float64),
        sr=22_050,
    )


class DirectAnalysisStateRound2Tests(unittest.TestCase):
    def _seed_direct_state(self, bridge: Bridge) -> None:
        bridge.audio_path = str(Path("old.ogg").resolve())
        bridge.project_audio_reference = bridge.audio_path
        bridge.spectrogram = None
        bridge.vorbis_spectrum_store = SimpleNamespace(duration=12.0)
        bridge.frequency_track_store = SimpleNamespace(track_count=1)
        bridge.analysis_stats = {
            "requestedSource": "vorbis_direct",
            "selectedSource": "vorbis_direct",
            "storedBins": 123,
        }

    def test_blank_workspace_clears_all_direct_analysis_products(self):
        bridge = Bridge()
        self._seed_direct_state(bridge)
        generation = bridge._source_generation

        state = bridge.apply_blank_workspace(
            {"duration": 20.0, "midiMin": 24, "midiMax": 96}
        )

        self.assertIsNone(bridge.audio_path)
        self.assertIsNone(bridge.spectrogram)
        self.assertIsNone(bridge.vorbis_spectrum_store)
        self.assertIsNone(bridge.frequency_track_store)
        self.assertEqual(bridge.analysis_stats, {})
        self.assertGreater(bridge._source_generation, generation)
        self.assertFalse(state["analysis"]["available"])
        self.assertFalse(
            bridge.get_spectrum_region(0, 1, 0, 127, 100, 100)["available"]
        )
        self.assertFalse(
            bridge.get_frequency_track_region(0, 1, 0, 127, 100, 100)["available"]
        )

    def test_notes_only_load_clears_previous_direct_products(self):
        bridge = Bridge()
        self._seed_direct_state(bridge)

        with (
            mock.patch.object(bridge, "_dialog", return_value="notes.adopyhz"),
            mock.patch.object(
                web_tools,
                "load_project",
                return_value=(None, [], {}),
            ),
        ):
            state = bridge.load_project_notes_only_dialog()

        self.assertIsNone(bridge.audio_path)
        self.assertIsNone(bridge.vorbis_spectrum_store)
        self.assertIsNone(bridge.frequency_track_store)
        self.assertFalse(state["analysis"]["available"])

    def test_audio_less_project_load_clears_previous_direct_products(self):
        bridge = Bridge()
        self._seed_direct_state(bridge)

        with (
            mock.patch.object(bridge, "_dialog", return_value="empty.adopyhz"),
            mock.patch.object(
                web_io,
                "load_project",
                return_value=(None, [], {}),
            ),
        ):
            state = bridge.load_project_dialog()

        self.assertIsNone(bridge.audio_path)
        self.assertIsNone(bridge.vorbis_spectrum_store)
        self.assertIsNone(bridge.frequency_track_store)
        self.assertFalse(state["analysis"]["available"])

    def test_saved_direct_project_reloads_as_direct_pending_without_cqt(self):
        bridge = Bridge()
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.ogg"
            audio.write_bytes(b"not-real-audio-because-decoder-is-mocked")
            with (
                mock.patch.object(bridge, "_dialog", return_value=str(Path(tmp) / "project.adopyhz")),
                mock.patch.object(
                    web_io,
                    "load_project",
                    return_value=(
                        str(audio),
                        [],
                        {"analysis_source": "vorbis_direct"},
                    ),
                ),
                mock.patch.object(
                    web_backend,
                    "decode_audio_file",
                    return_value=_decoded(),
                ),
                mock.patch.object(
                    web_backend,
                    "select_analysis_backend",
                    return_value=SimpleNamespace(
                        selected="vorbis_direct",
                        fallback_reason=None,
                    ),
                ),
                mock.patch.object(web_backend, "analyze_cqt") as cqt,
            ):
                    state = bridge.load_project_dialog()

        cqt.assert_not_called()
        self.assertEqual(bridge.settings["analysisSource"], "vorbis_direct")
        self.assertIsNotNone(bridge.audio_path)
        self.assertIsNone(bridge.spectrogram)
        self.assertIsNone(bridge.vorbis_spectrum_store)
        self.assertTrue(bridge.analysis_stats["pending"])
        self.assertEqual(
            bridge.analysis_stats["selectedSource"],
            "vorbis_direct",
        )
        self.assertFalse(state["analysis"]["available"])
        self.assertEqual(state["analysis"]["source"], "vorbis_direct")

    def test_unsupported_direct_project_falls_back_to_cqt_explicitly(self):
        bridge = Bridge()
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.wav"
            audio.write_bytes(b"mock")
            spec = _cqt(str(audio))
            with (
                mock.patch.object(bridge, "_dialog", return_value=str(Path(tmp) / "project.adopyhz")),
                mock.patch.object(
                    web_io,
                    "load_project",
                    return_value=(
                        str(audio),
                        [],
                        {"analysis_source": "vorbis_direct"},
                    ),
                ),
                mock.patch.object(
                    web_backend,
                    "decode_audio_file",
                    return_value=_decoded(),
                ),
                mock.patch.object(
                    web_backend,
                    "select_analysis_backend",
                    return_value=SimpleNamespace(
                        selected="pcm",
                        fallback_reason="unsupported test source",
                    ),
                ),
                mock.patch.object(
                    web_backend,
                    "analyze_cqt",
                    return_value=spec,
                ) as cqt,
            ):
                    state = bridge.load_project_dialog()

        cqt.assert_called_once()
        self.assertTrue(state["analysis"]["available"])
        self.assertEqual(state["analysis"]["source"], "cqt")
        self.assertEqual(
            state["analysis"]["stats"]["requestedSource"],
            "vorbis_direct",
        )
        self.assertEqual(
            state["analysis"]["stats"]["fallbackReason"],
            "unsupported test source",
        )

    def test_relink_respects_direct_request_and_stays_pending(self):
        bridge = Bridge()
        bridge.project_path = str(Path("project.adopyhz").resolve())
        bridge.settings["analysisSource"] = "vorbis_direct"
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.ogg"
            audio.write_bytes(b"mock")
            with (
                mock.patch.object(bridge, "_dialog", return_value=str(audio)),
                mock.patch.object(
                    web_backend,
                    "decode_audio_file",
                    return_value=_decoded(),
                ),
                mock.patch.object(
                    web_backend,
                    "select_analysis_backend",
                    return_value=SimpleNamespace(
                        selected="vorbis_direct",
                        fallback_reason=None,
                    ),
                ),
                mock.patch.object(web_backend, "analyze_cqt") as cqt,
            ):
                    state = bridge.relink_project_audio_dialog()

        cqt.assert_not_called()
        self.assertEqual(bridge.audio_path, str(audio.resolve()))
        self.assertTrue(bridge.analysis_stats["pending"])
        self.assertFalse(state["analysis"]["available"])
        self.assertIn("Vorbis Direct解析待ち", state["status"])


if __name__ == "__main__":
    unittest.main()

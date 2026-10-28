from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import web.backend as web_backend
from core.frequency_tracks import FrequencyTrackRegion
from web_ui import Bridge


class ExplicitWebTrackPolicyTests(unittest.TestCase):
    def test_importing_web_does_not_replace_core_track_query(self):
        script = r"""
from core.frequency_tracks import FrequencyTrackStore
before = FrequencyTrackStore.query_region
import web
from web.editing import EditingMixin
assert FrequencyTrackStore.query_region is before
assert "find_frequency_tracks" not in EditingMixin.__dict__
assert "create_notes_from_tracks" not in EditingMixin.__dict__
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=completed.stdout + completed.stderr,
        )

    def test_bridge_exposes_track_transcription_without_editing_mixin_patch(self):
        bridge = Bridge()
        self.assertTrue(callable(bridge.find_frequency_tracks))
        self.assertTrue(callable(bridge.create_notes_from_tracks))
        self.assertEqual(
            bridge.find_frequency_tracks(0.0, 1.0, 0.0, 127.0)["trackIds"],
            [],
        )

    def test_bridge_calls_web_readability_policy_explicitly(self):
        bridge = Bridge()
        bridge.audio_path = "test.ogg"
        bridge.frequency_track_store = SimpleNamespace()
        expected = FrequencyTrackRegion(
            packed_points=b"",
            returned_tracks=0,
            returned_points=0,
            decimation_level=1.0,
            query_seconds=0.001,
        )
        with mock.patch.object(
            web_backend,
            "readable_frequency_track_region",
            return_value=expected,
        ) as query:
            result = bridge.get_frequency_track_region(
                0.0, 1.0, 0.0, 127.0, 800, 400
            )

        query.assert_called_once()
        self.assertTrue(result["available"])
        self.assertEqual(result["trackCount"], 0)
        self.assertEqual(result["pointCount"], 0)


if __name__ == "__main__":
    unittest.main()

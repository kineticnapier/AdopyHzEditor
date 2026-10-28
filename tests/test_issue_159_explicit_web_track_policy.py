from __future__ import annotations

import subprocess
import sys
import unittest

from core.frequency_tracks import FrequencyTrackStore
from web.backend import Bridge as CoreBridge
from web.track_display import readable_frequency_track_region


class ExplicitWebTrackPolicyTests(unittest.TestCase):
    def test_import_web_does_not_patch_core_frequency_track_store(self):
        code = (
            "from core.frequency_tracks import FrequencyTrackStore\n"
            "before = FrequencyTrackStore.query_region\n"
            "import web\n"
            "assert FrequencyTrackStore.query_region is before\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_core_bridge_exposes_track_transcription_without_dynamic_install(self):
        bridge = CoreBridge()
        self.assertTrue(callable(bridge.find_frequency_tracks))
        self.assertTrue(callable(bridge.create_notes_from_tracks))

    def test_core_store_query_method_remains_distinct_from_web_display_policy(self):
        self.assertIsNot(
            FrequencyTrackStore.query_region,
            readable_frequency_track_region,
        )


if __name__ == "__main__":
    unittest.main()

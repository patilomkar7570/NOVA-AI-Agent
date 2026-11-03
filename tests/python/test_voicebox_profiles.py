"""Regression tests for NOVA's Voicebox profile-list endpoint helper."""
import unittest
from unittest.mock import patch

import api


class VoiceboxProfileListTests(unittest.TestCase):
    def test_profiles_are_normalised_and_default_is_resolved(self):
        responses = [
            {"profiles": [
                {"id": 12, "name": "NOVA Voice", "language": "en", "voice_type": "cloned"},
                {"profile_id": "preset-1", "name": "Hindi voice", "language": "hi", "voice_type": "preset", "preset_engine": "kokoro"},
                {"name": "Invalid row without ID"},
            ]},
            {"default_playback_voice_id": 12},
        ]
        with patch.object(api, "_voicebox_request_json", side_effect=responses):
            status, payload = api.list_voicebox_profiles()

        self.assertEqual(status, 200)
        self.assertEqual(len(payload["profiles"]), 2)
        self.assertEqual(payload["profiles"][0]["id"], "12")
        self.assertTrue(payload["profiles"][0]["is_default"])
        self.assertEqual(payload["profiles"][1]["preset_engine"], "kokoro")

    def test_connection_failure_is_reported_as_service_unavailable(self):
        from urllib.error import URLError
        with patch.object(api, "_voicebox_request_json", side_effect=URLError("connection refused")):
            status, payload = api.list_voicebox_profiles()
        self.assertEqual(status, 503)
        self.assertFalse(payload["ok"])
        self.assertIn("not reachable", payload["error"])


if __name__ == "__main__":
    unittest.main()

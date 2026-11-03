"""Regression tests for Voicebox /transcribe multipart field compatibility."""
import unittest
from unittest.mock import patch

import api


class VoiceboxTranscribeContractTests(unittest.TestCase):
    def test_published_file_field_is_recognised(self):
        schema = {
            "paths": {
                "/transcribe": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "multipart/form-data": {
                                    "schema": {"$ref": "#/components/schemas/TranscribeBody"}
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "TranscribeBody": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string", "format": "binary"},
                            "language": {"type": "string"},
                        },
                        "required": ["file"],
                    }
                }
            },
        }
        properties, required = api._voicebox_request_properties(schema, "/transcribe")
        self.assertIn("file", required)
        self.assertEqual(api._voicebox_transcription_upload_candidates(properties, required)[:2], ["file", "audio"])

    def test_audio_field_without_binary_format_is_recognised(self):
        properties = {"audio": {"type": "string"}, "language": {"type": "string"}}
        candidates = api._voicebox_transcription_upload_candidates(properties, {"audio"})
        self.assertEqual(candidates[0], "audio")
        self.assertIn("file", candidates)

    def test_composed_schema_is_resolved(self):
        schema = {
            "paths": {
                "/transcribe": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "multipart/form-data": {
                                    "schema": {
                                        "allOf": [
                                            {"$ref": "#/components/schemas/BaseBody"},
                                            {"properties": {"language": {"type": "string"}}},
                                        ]
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "BaseBody": {
                        "properties": {"file": {"type": "string", "format": "binary"}},
                        "required": ["file"],
                    }
                }
            },
        }
        properties, required = api._voicebox_request_properties(schema, "/transcribe")
        self.assertIn("file", properties)
        self.assertIn("language", properties)
        self.assertIn("file", required)

    def test_validation_detail_detects_alternate_missing_upload_key(self):
        payload = {"detail": [{"loc": ["body", "audio"], "msg": "Field required"}]}
        self.assertTrue(api._voicebox_validation_mentions_upload(payload, ["file", "audio"]))
        self.assertFalse(api._voicebox_validation_mentions_upload(
            {"detail": [{"loc": ["body", "language"], "msg": "Field required"}]},
            ["file", "audio"],
        ))

    def test_runtime_retries_audio_when_server_rejects_file_key(self):
        schema = {
            "paths": {
                "/transcribe": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "multipart/form-data": {
                                    "schema": {
                                        "properties": {
                                            "file": {"type": "string", "format": "binary"},
                                            "language": {"type": "string"},
                                        },
                                        "required": ["file"],
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        calls = []

        def fake_post(_audio, file_field, _fields, endpoint="/transcribe"):
            calls.append((file_field, endpoint))
            if file_field == "file":
                return 422, {"detail": [{"loc": ["body", "audio"], "msg": "Field required"}]}
            return 200, {"text": "Hello from Voicebox."}

        valid_wav_header = b"RIFF" + (36).to_bytes(4, "little") + b"WAVE" + b"fmt " + b"\x00" * 32
        with patch.object(api, "_voicebox_openapi_schema", return_value=schema), patch.object(
            api, "_post_voicebox_transcription", side_effect=fake_post
        ):
            status, payload = api.transcribe_with_voicebox(valid_wav_header, "auto")

        self.assertEqual(status, 200)
        self.assertEqual(payload["text"], "Hello from Voicebox.")
        self.assertEqual(calls[:2], [("file", "/transcribe"), ("audio", "/transcribe")])


if __name__ == "__main__":
    unittest.main()

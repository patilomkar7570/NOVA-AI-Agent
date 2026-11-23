"""Unit tests for NOVA Multi-Model & Google Gemini Integration."""
import unittest
from unittest.mock import patch, MagicMock
import nova_models


class TestNovaModels(unittest.TestCase):
    def test_default_settings(self):
        settings = nova_models.get_model_settings()
        self.assertIn("provider", settings)
        self.assertIn("chat_model", settings)
        self.assertIn("work_model", settings)
        self.assertIn("unified_model", settings)
        self.assertTrue(settings["chat_model"]["enabled"])
        self.assertTrue(settings["work_model"]["enabled"])

    def test_mask_api_key(self):
        self.assertEqual(nova_models.mask_api_key(""), "")
        self.assertEqual(nova_models.mask_api_key("short"), "••••••••")
        masked = nova_models.mask_api_key("AIzaSyABCD1234EFGH5678")
        self.assertTrue(masked.startswith("AIzaSy"))
        self.assertTrue(masked.endswith("5678"))
        self.assertIn("••••••••", masked)

    def test_test_gemini_api_key_empty(self):
        result = nova_models.test_gemini_api_key("")
        self.assertFalse(result["ok"])
        self.assertIn("empty", result["error"])

    def test_save_and_load_settings(self):
        current = nova_models.get_model_settings()
        updated = nova_models.save_model_settings({
            "unified_model": False,
            "chat_model": {"local_model": "qwen3:1.7b"},
        })
        self.assertFalse(updated["unified_model"])
        loaded = nova_models.get_model_settings()
        self.assertFalse(loaded["unified_model"])

    def test_role_disabled_message(self):
        with patch.object(nova_models, "get_model_settings", return_value={
            "chat_model": {"enabled": False},
            "work_model": {"enabled": True},
        }):
            reply = nova_models.ask_ai([{"role": "user", "content": "hi"}], role="chat")
            self.assertIn("Disabled", reply)


if __name__ == "__main__":
    unittest.main()

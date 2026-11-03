import unittest

from nova_agents.language import (
    detect_language_from_text, language_instruction, normalize_language,
    preferred_voicebox_engine, voicebox_engine_supports_language,
)


class LanguagePreferenceTests(unittest.TestCase):
    def test_normalises_selected_language_and_locale_tags(self):
        self.assertEqual(normalize_language("hi-IN"), "hi")
        self.assertEqual(normalize_language("de-DE"), "de")
        self.assertEqual(normalize_language("Automatic"), "auto")
        self.assertEqual(normalize_language("unsupported"), "en")

    def test_explicit_language_instructions_keep_machine_syntax(self):
        instruction = language_instruction("hi")
        self.assertIn("Hindi", instruction)
        self.assertIn("Devanagari", instruction)
        self.assertIn("JSON keys", instruction)

    def test_automatic_instruction_follows_latest_user_language(self):
        instruction = language_instruction("auto")
        self.assertIn("same language as the user's latest message", instruction)

    def test_detects_hindi_and_japanese_scripts(self):
        self.assertEqual(detect_language_from_text("नमस्ते, आप कैसे हैं?"), "hi")
        self.assertEqual(detect_language_from_text("こんにちは、元気ですか？"), "ja")

    def test_detects_common_latin_language_examples(self):
        self.assertEqual(detect_language_from_text("Guten Morgen, wie geht es dir heute?"), "de")
        self.assertEqual(detect_language_from_text("Bonjour, je voudrais parler avec vous."), "fr")
        self.assertEqual(detect_language_from_text("Hola, quiero hablar contigo ahora."), "es")

    def test_voicebox_engine_routing_covers_all_six_languages(self):
        qwen_languages = {"en", "de", "fr", "es", "ja"}
        for code in qwen_languages:
            with self.subTest(engine="qwen", language=code):
                self.assertTrue(voicebox_engine_supports_language("qwen", code))
        self.assertFalse(voicebox_engine_supports_language("qwen", "hi"))
        self.assertEqual(preferred_voicebox_engine("hi"), "chatterbox")
        self.assertEqual(preferred_voicebox_engine("de"), "qwen")
        for code in {"en", "de", "fr", "es", "ja", "hi"}:
            with self.subTest(engine="chatterbox", language=code):
                self.assertTrue(voicebox_engine_supports_language("chatterbox", code))
        self.assertTrue(voicebox_engine_supports_language("kokoro", "hi"))
        self.assertFalse(voicebox_engine_supports_language("luxtts", "ja"))


if __name__ == "__main__":
    unittest.main()

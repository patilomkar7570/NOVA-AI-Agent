import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

"""Tests for 2FA SMS Interception, TOTP Generator & CAPTCHA Hand-off."""
import os
import unittest
from unittest.mock import MagicMock, patch
import agent
from nova_2fa import TwoFactorEngine, two_factor_engine


class TwoFactorAndCaptchaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["NOVA_TEST_MODE"] = "1"

    @classmethod
    def tearDownClass(cls):
        pass

    def test_extract_2fa_sms_codes(self):
        cases = [
            ("Your Discord verification code is 482910.", "482910"),
            ("Use 829-102 to verify your Microsoft account.", "829102"),
            ("G-954123 is your Google verification code.", "954123"),
            ("Security PIN: 3918. Do not share this with anyone.", "3918"),
        ]
        for msg, expected in cases:
            res = two_factor_engine.extract_code(msg)
            self.assertTrue(res["found"], f"Failed to extract from: {msg}")
            self.assertEqual(res["code"], expected)

    def test_negative_cases_no_code(self):
        negatives = [
            "Hey, are you free to meet tomorrow at 5pm?",
            "Your order #998811 has shipped via FedEx.",
            "Meeting room 104 is booked.",
        ]
        for msg in negatives:
            res = two_factor_engine.extract_code(msg)
            self.assertFalse(res["found"])

    def test_rfc6238_totp_generation(self):
        # Known test secret in base32
        secret = "JBSWY3DPEHPK3PXP"  # standard test secret "Hello!\xde\xad\xbe\xef"
        res = two_factor_engine.generate_totp(secret)
        self.assertTrue(res["ok"])
        self.assertEqual(len(res["token"]), 6)
        self.assertTrue(res["token"].isdigit())
        self.assertGreaterEqual(res["remaining_seconds"], 0)
        self.assertLessEqual(res["remaining_seconds"], 30)

    def test_captcha_turnstile_detection(self):
        mock_page = MagicMock()
        mock_page.content.return_value = '<html><body><div class="cf-turnstile" data-sitekey="abc"></div><iframe src="https://challenges.cloudflare.com/cdn-cgi/challenge-platform"></iframe></body></html>'
        with patch.object(agent, "_page", mock_page):
            status = agent.detect_captcha_challenge()
            self.assertTrue(status["detected"])
            self.assertEqual(status["type"], "cloudflare_turnstile")

    def test_captcha_clear_when_no_challenge(self):
        mock_page = MagicMock()
        mock_page.content.return_value = '<html><body><h1>Welcome to Dashboard</h1></body></html>'
        with patch.object(agent, "_page", mock_page):
            status = agent.detect_captcha_challenge()
            self.assertFalse(status["detected"])


if __name__ == "__main__":
    unittest.main()

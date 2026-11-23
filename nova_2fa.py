"""Two-Factor Authentication (2FA) SMS Interception & TOTP Generator for NOVA AI Agent.

Enables automated reading of SMS 2FA codes from Windows Phone Link notifications
and native RFC 6238 TOTP generation without external dependencies.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import struct
import time
from typing import Any


class TwoFactorEngine:
    """Handles 2FA code extraction and local TOTP generation."""

    # Common OTP regexes
    CODE_PATTERNS = [
        # Explicit keyword: "Your verification code is 123456"
        re.compile(
            r"(?:code|otp|pin|passcode|token|verification|secret)\s*(?:is|:)?\s*([0-9]{4,8})\b",
            re.IGNORECASE,
        ),
        # Hyphenated code: "123-456"
        re.compile(r"\b([0-9]{3})-([0-9]{3})\b"),
        # Google style: "G-123456"
        re.compile(r"\b[A-Z]-([0-9]{6})\b", re.IGNORECASE),
        # Fallback standalone 6-digit number if word "code" or "verify" is in the sentence
        re.compile(r"(?=.*(?:code|verify|security|login|access))\b([0-9]{6})\b", re.IGNORECASE),
    ]

    @classmethod
    def extract_code(cls, text: str) -> dict[str, Any]:
        """Extracts 2FA code from SMS text or notification payload."""
        if not text:
            return {"found": False, "code": None}

        for pattern in cls.CODE_PATTERNS:
            match = pattern.search(text)
            if match:
                if len(match.groups()) == 2:
                    code = f"{match.group(1)}{match.group(2)}"
                else:
                    code = match.group(1)

                return {
                    "found": True,
                    "code": code.strip(),
                    "confidence": 0.95,
                    "matched_pattern": pattern.pattern[:35] + "...",
                }

        return {"found": False, "code": None}

    @staticmethod
    def generate_totp(secret: str, interval: int = 30, digits: int = 6) -> dict[str, Any]:
        """Generates RFC 6238 TOTP token using standard library HMAC-SHA1."""
        clean_secret = secret.strip().replace(" ", "").upper()
        # Add required base32 padding if missing
        missing_padding = len(clean_secret) % 8
        if missing_padding:
            clean_secret += "=" * (8 - missing_padding)

        try:
            key = base64.b32decode(clean_secret, casefold=True)
        except Exception as exc:
            return {"ok": False, "error": f"Invalid Base32 secret key: {exc}"}

        now = int(time.time())
        time_step = now // interval
        remaining_seconds = interval - (now % interval)

        # Pack time step into big-endian 8-byte integer
        time_bytes = struct.pack(">Q", time_step)
        hmac_digest = hmac.new(key, time_bytes, hashlib.sha1).digest()

        # Dynamic truncation (RFC 4226)
        offset = hmac_digest[-1] & 0x0F
        code_int = struct.unpack(">I", hmac_digest[offset : offset + 4])[0] & 0x7FFFFFFF
        token = str(code_int % (10**digits)).zfill(digits)

        return {
            "ok": True,
            "token": token,
            "remaining_seconds": remaining_seconds,
            "interval": interval,
            "digits": digits,
        }


# Global instance
two_factor_engine = TwoFactorEngine()

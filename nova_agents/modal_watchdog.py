"""Closed-loop interstitial and modal dismissal watchdog.

Provides real-time pre-action interception to detect and clear surprise popups,
update banners, cookie dialogs, and child modal barriers before actions execute.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import time
import re
from typing import Any

user32 = getattr(ctypes.windll, "user32", None)


class ModalWatchdog:
    """Detects and resolves unexpected interstitial popups and blocking modals."""

    DISMISSAL_PATTERNS = re.compile(
        r"\b(?:close|dismiss|skip|later|not now|cancel|x|continue|accept all|got it|agree|remind me later)\b",
        re.I
    )

    BLOCKING_TITLE_PATTERNS = re.compile(
        r"\b(?:update|whats new|welcome|tip|announcement|promotion|cookie|privacy agreement|survey)\b",
        re.I
    )

    @classmethod
    def get_foreground_info(cls) -> dict[str, Any]:
        """Returns details about the currently focused top-level window."""
        if not user32:
            return {"hwnd": 0, "title": "", "is_valid": False}
        hwnd = user32.GetForegroundWindow()
        if not hwnd or not user32.IsWindow(hwnd):
            return {"hwnd": 0, "title": "", "is_valid": False}
        title_buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buf, 512)
        return {
            "hwnd": hwnd,
            "title": title_buf.value.strip(),
            "is_valid": True,
        }

    @classmethod
    def is_blocking_modal(cls, fg_hwnd: int, target_hwnd: int) -> bool:
        """Determines if fg_hwnd is a non-target child modal or popup blocking target_hwnd."""
        if not user32 or not fg_hwnd or fg_hwnd == target_hwnd:
            return False

        # Check if fg_hwnd is owned by target_hwnd
        owner = user32.GetWindow(fg_hwnd, 4)  # GW_OWNER = 4
        root_owner = user32.GetAncestor(fg_hwnd, 3)  # GA_ROOTOWNER = 3
        if owner == target_hwnd or root_owner == target_hwnd:
            return True

        # Check if title indicates an interstitial dialog
        title_info = cls.get_foreground_info()
        if cls.BLOCKING_TITLE_PATTERNS.search(title_info.get("title", "")):
            return True

        return False

    @classmethod
    def check_and_clear_blocking_modals(
        cls,
        target_hwnd: int,
        auto_dismiss: bool = True,
        timeout: float = 0.5
    ) -> dict[str, Any]:
        """Inspects whether an unexpected modal is blocking target_hwnd, and clears it if safe.
        
        Returns:
            {"cleared": bool, "barrier_title": str | None, "focus_restored": bool}
        """
        if not user32 or os.environ.get("NOVA_TEST_MODE") == "1" or os.environ.get("NOVA_SANDBOX_MODE") == "1":
            return {"cleared": True, "barrier_title": None, "focus_restored": True}

        fg_info = cls.get_foreground_info()
        fg_hwnd = fg_info.get("hwnd", 0)

        if not fg_hwnd or fg_hwnd == target_hwnd:
            return {"cleared": True, "barrier_title": None, "focus_restored": True}

        if cls.is_blocking_modal(fg_hwnd, target_hwnd):
            barrier_title = fg_info.get("title", "Unknown Modal")
            if auto_dismiss:
                # 1. Non-destructive attempt: dispatch Escape key to dismiss non-essential modal/flyout
                user32.PostMessageW(fg_hwnd, 0x0100, 0x1B, 0)  # WM_KEYDOWN, VK_ESCAPE
                time.sleep(0.04)
                user32.PostMessageW(fg_hwnd, 0x0101, 0x1B, 0)  # WM_KEYUP, VK_ESCAPE
                time.sleep(0.12)

                # Re-check if focus returned to target
                new_fg = user32.GetForegroundWindow()
                if new_fg == target_hwnd:
                    return {"cleared": True, "barrier_title": barrier_title, "focus_restored": True}

                # 2. Try bringing target_hwnd back to foreground
                user32.SetForegroundWindow(target_hwnd)
                time.sleep(0.08)
                new_fg = user32.GetForegroundWindow()
                return {
                    "cleared": new_fg == target_hwnd,
                    "barrier_title": barrier_title,
                    "focus_restored": new_fg == target_hwnd,
                }

            return {"cleared": False, "barrier_title": barrier_title, "focus_restored": False}

        return {"cleared": True, "barrier_title": None, "focus_restored": user32.GetForegroundWindow() == target_hwnd}

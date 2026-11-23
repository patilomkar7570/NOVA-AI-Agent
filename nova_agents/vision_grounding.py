"""Sub-image ROI visual grounding and high-DPI normalized coordinate engine.

Provides resolution-independent, multi-monitor normalized coordinates (0.0 to 1.0)
and localized Region of Interest (ROI) patch cropping for zero-latency, full-fidelity
visual UI element detection.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import io
import os
from typing import Any
try:
    from PIL import Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False
    Image = None

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

user32 = getattr(ctypes.windll, "user32", None)


class NormalizedCoordinateEngine:
    """Provides high-DPI aware, normalized (0.0 to 1.0) desktop coordinate transforms."""

    @staticmethod
    def get_screen_metrics() -> dict[str, int]:
        """Returns virtual desktop boundaries across all attached monitors."""
        if os.environ.get("NOVA_TEST_MODE") == "1" or not user32:
            return {"virtual_x": 0, "virtual_y": 0, "virtual_width": 1920, "virtual_height": 1080}
        try:
            return {
                "virtual_x": user32.GetSystemMetrics(76),      # SM_XVIRTUALSCREEN
                "virtual_y": user32.GetSystemMetrics(77),      # SM_YVIRTUALSCREEN
                "virtual_width": user32.GetSystemMetrics(78),  # SM_CXVIRTUALSCREEN
                "virtual_height": user32.GetSystemMetrics(79), # SM_CYVIRTUALSCREEN
            }
        except Exception:
            return {"virtual_x": 0, "virtual_y": 0, "virtual_width": 1920, "virtual_height": 1080}

    @classmethod
    def to_normalized(cls, abs_x: int, abs_y: int, hwnd: int | None = None) -> tuple[float, float]:
        """Convert physical screen pixels to normalized [0.0, 1.0] coordinates."""
        if hwnd and user32 and user32.IsWindow(hwnd):
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = max(1, rect.right - rect.left)
            h = max(1, rect.bottom - rect.top)
            norm_x = max(0.0, min(1.0, (abs_x - rect.left) / float(w)))
            norm_y = max(0.0, min(1.0, (abs_y - rect.top) / float(h)))
            return norm_x, norm_y

        metrics = cls.get_screen_metrics()
        w = max(1, metrics["virtual_width"])
        h = max(1, metrics["virtual_height"])
        norm_x = max(0.0, min(1.0, (abs_x - metrics["virtual_x"]) / float(w)))
        norm_y = max(0.0, min(1.0, (abs_y - metrics["virtual_y"]) / float(h)))
        return norm_x, norm_y

    @classmethod
    def to_absolute_pixels(cls, norm_x: float, norm_y: float, hwnd: int | None = None) -> tuple[int, int]:
        """Convert normalized [0.0, 1.0] coordinates to physical screen pixels."""
        norm_x = max(0.0, min(1.0, float(norm_x)))
        norm_y = max(0.0, min(1.0, float(norm_y)))

        if hwnd and user32 and user32.IsWindow(hwnd):
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = max(1, rect.right - rect.left)
            h = max(1, rect.bottom - rect.top)
            return int(rect.left + (norm_x * w)), int(rect.top + (norm_y * h))

        metrics = cls.get_screen_metrics()
        x = metrics["virtual_x"] + int(norm_x * metrics["virtual_width"])
        y = metrics["virtual_y"] + int(norm_y * metrics["virtual_height"])
        return x, y

    @staticmethod
    def crop_window_roi(
        hwnd: int | None = None,
        quadrant: str = "full",
        target_box: tuple[int, int, int, int] | None = None
    ) -> tuple[Any, tuple[int, int]]:
        """Extract a high-resolution sub-image patch around a target quadrant.
        
        Avoids full-screen 4K downsampling, keeping 1:1 pixel fidelity for small UI icons.
        Returns:
            (PIL_Image_or_None, (offset_x, offset_y))
        """
        if os.environ.get("NOVA_TEST_MODE") == "1" or not _PYAUTOGUI or not user32:
            img = Image.new("RGB", (400, 200), color=(30, 30, 30)) if _PIL_OK and Image else {"mock": True}
            return img, (0, 0)

        if target_box:
            x, y, w, h = target_box
            patch_rect = (max(0, x), max(0, y), max(10, w), max(10, h))
            shot = pyautogui.screenshot(region=patch_rect)
            return shot, (patch_rect[0], patch_rect[1])

        if hwnd and user32.IsWindow(hwnd):
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            x1, y1 = max(0, rect.left), max(0, rect.top)
            w, h = max(10, rect.right - rect.left), max(10, rect.bottom - rect.top)

            if quadrant == "top_header":
                patch_rect = (x1, y1, w, min(h, 220))
            elif quadrant == "bottom_bar":
                patch_rect = (x1, y1 + max(0, h - 180), w, min(h, 180))
            elif quadrant == "left_sidebar":
                patch_rect = (x1, y1, min(w, 320), h)
            elif quadrant == "center_canvas":
                margin_x = int(w * 0.15)
                margin_y = int(h * 0.15)
                patch_rect = (x1 + margin_x, y1 + margin_y, max(10, w - 2 * margin_x), max(10, h - 2 * margin_y))
            else:
                patch_rect = (x1, y1, w, h)

            shot = pyautogui.screenshot(region=patch_rect)
            return shot, (patch_rect[0], patch_rect[1])

        # Desktop fallback
        metrics = NormalizedCoordinateEngine.get_screen_metrics()
        patch_rect = (metrics["virtual_x"], metrics["virtual_y"], metrics["virtual_width"], metrics["virtual_height"])
        shot = pyautogui.screenshot(region=patch_rect)
        return shot, (patch_rect[0], patch_rect[1])

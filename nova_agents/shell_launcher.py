"""Direct Windows Shell and AUMID (Application User Model ID) package launcher.

Launches modern Windows UWP, Store, Desktop, and packaged applications directly
via explorer shell:AppsFolder protocols, eliminating reliance on Windows Search Indexing.
"""
from __future__ import annotations

import os
import re
import subprocess
import winreg
from typing import Any


class WindowsShellLauncher:
    """Deterministic application launcher using Windows Shell and AUMID protocols."""

    # Common Windows Modern / Store App Package mappings
    KNOWN_AUMID_MAP: dict[str, str] = {
        "calculator": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
        "calc": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
        "settings": "windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel",
        "notepad": "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App",
        "paint": "Microsoft.Paint_8wekyb3d8bbwe!App",
        "photos": "Microsoft.Windows.Photos_8wekyb3d8bbwe!App",
        "terminal": "Microsoft.WindowsTerminal_8wekyb3d8bbwe!App",
        "camera": "Microsoft.WindowsCamera_8wekyb3d8bbwe!App",
        "clock": "Microsoft.WindowsAlarms_8wekyb3d8bbwe!App",
        "spotify": "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify",
        "whatsapp": "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!WhatsApp",
        "discord": "com.squirrel.Discord.Discord",
    }

    @classmethod
    def find_aumid_in_registry(cls, app_alias: str) -> str | None:
        """Scan Windows Store repository registry hives to resolve active package AUMID."""
        clean = re.sub(r"[^\w]", "", app_alias.lower())
        if not clean:
            return None

        # Check known map first
        if clean in cls.KNOWN_AUMID_MAP:
            return cls.KNOWN_AUMID_MAP[clean]

        hives = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
        reg_path = r"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages"

        for hive in hives:
            try:
                with winreg.OpenKey(hive, reg_path) as base_key:
                    subkeys_count = winreg.QueryInfoKey(base_key)[0]
                    for i in range(min(subkeys_count, 300)):
                        pkg_name = winreg.EnumKey(base_key, i)
                        if clean in pkg_name.lower():
                            with winreg.OpenKey(base_key, pkg_name) as pkg_key:
                                try:
                                    app_id = winreg.QueryValueEx(pkg_key, "PackageID")[0]
                                    return f"{app_id}!App"
                                except Exception:
                                    return f"{pkg_name}!App"
            except Exception:
                continue

        return None

    @classmethod
    def launch(cls, app_alias: str) -> dict[str, Any]:
        """Launch an application deterministically via AUMID shell protocol.
        
        Returns:
            {"success": bool, "protocol": str, "aumid": str | None}
        """
        if os.environ.get("NOVA_TEST_MODE") == "1":
            return {"success": True, "protocol": "shell:AppsFolder", "aumid": f"Mock.{app_alias}!App"}

        clean = app_alias.strip()
        aumid = cls.find_aumid_in_registry(clean)

        if aumid:
            try:
                proc = subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{aumid}"], shell=False)
                return {"success": True, "protocol": "shell:AppsFolder", "aumid": aumid}
            except Exception as exc:
                return {"success": False, "protocol": "shell:AppsFolder", "error": str(exc)}

        return {"success": False, "protocol": None, "aumid": None}

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


API_PATH = Path(__file__).resolve().parent / "api.py"


def main() -> int:
    if not API_PATH.is_file():
        print("ERROR: api.py was not found beside this script.")
        print("Extract this ZIP into the NOVA project root, beside api.py, then run it again.")
        return 2

    source = API_PATH.read_text(encoding="utf-8")

    # Do not fabricate the TTS service if this project has not received the
    # backend Voicebox integration yet. That integration includes the actual
    # Voicebox request / returned-audio logic, not just a frontend URL.
    has_speak_route = "/api/voice/speak" in source and "generate_voicebox_audio" in source
    if not has_speak_route:
        print("ERROR: This api.py does not contain NOVA's /api/voice/speak backend route.")
        print("The frontend is calling that route, but this backend file is an older build.")
        print("Do not overwrite api.py with this hotfix. Install the Voicebox backend integration first.")
        return 3

    updated = source
    changes: list[str] = []

    if not re.search(r"(?m)^import\s+re\s*$", updated):
        import_anchor = re.search(r"(?m)^import\s+queue\s*$", updated)
        if not import_anchor:
            print("ERROR: Could not find the standard import section in api.py; no file was changed.")
            return 4
        insert_at = import_anchor.end()
        updated = updated[:insert_at] + "\nimport re" + updated[insert_at:]
        changes.append("Added the missing standard-library import: re")

    error_guard_marker = "NOVA Voicebox speech route failed"
    if error_guard_marker not in updated:
        route_pattern = re.compile(
            r"(?m)^(?P<indent>[ \t]*)"
            r"(?P<call>status,\s*audio,\s*content_type,\s*payload\s*=\s*"
            r"generate_voicebox_audio\([^\n]*\))\n"
            r"(?P=indent)if audio is None:\n"
            r"(?P=indent)[ \t]+self\._send_json\(status, payload\)\n"
            r"(?P=indent)else:\n"
            r"(?P=indent)[ \t]+self\._send_audio\(status, audio, content_type\)\n"
            r"(?P=indent)return\n"
        )
        match = route_pattern.search(updated)
        if not match:
            print("ERROR: Found the speech route, but its handler layout did not match the known NOVA builds.")
            print("No file was changed. Please share your current api.py so I can make a precise patch.")
            return 5

        indent = match.group("indent")
        call = match.group("call")
        replacement = (
            f"{indent}try:\n"
            f"{indent}    {call}\n"
            f"{indent}except Exception as exc:\n"
            f"{indent}    self.log_error('NOVA Voicebox speech route failed: %s', exc)\n"
            f"{indent}    self._send_json(500, {{\"ok\": False, \"error\": \"NOVA's Voicebox speech handler failed before audio could be returned.\", \"detail\": str(exc)[:1000]}})\n"
            f"{indent}    return\n"
            f"{indent}if audio is None:\n"
            f"{indent}    self._send_json(status, payload)\n"
            f"{indent}else:\n"
            f"{indent}    self._send_audio(status, audio, content_type)\n"
            f"{indent}return\n"
        )
        updated = updated[:match.start()] + replacement + updated[match.end():]
        changes.append("Wrapped /api/voice/speak in an exception guard so backend errors return JSON instead of dropping the connection")

    if updated == source:
        print("NOVA Voicebox API hotfix is already applied. No changes were needed.")
        return 0

    try:
        compile(updated, str(API_PATH), "exec")
    except SyntaxError as exc:
        print(f"ERROR: The patched api.py did not pass Python syntax validation: {exc}")
        return 6

    backup_path = API_PATH.with_name(
        f"api.py.before_voicebox_hotfix.{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
    )
    shutil.copy2(API_PATH, backup_path)
    API_PATH.write_text(updated, encoding="utf-8", newline="\n")

    print("SUCCESS: NOVA Voicebox API hotfix applied.")
    for change in changes:
        print(f"  - {change}")
    print(f"Backup: {backup_path.name}")
    print("Next: stop and restart NOVA's Python backend, then test Voice Mode again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import subprocess
import time
import os
import sys
from pathlib import Path


# ============================================================
# NOVA LAUNCHER
# ============================================================

# When running normally:
#   PROJECT_DIR = C:\Users\dudha\Desktop\AI-Agent
#
# When running as:
#   C:\Users\dudha\Desktop\AI-Agent\dist\NOVA.exe
#
# PROJECT_DIR becomes:
#   C:\Users\dudha\Desktop\AI-Agent
#
# This prevents PyInstaller's temporary _MEI folder from
# being treated as the project directory.

if getattr(sys, "frozen", False):
    PROJECT_DIR = Path(sys.executable).resolve().parent.parent
else:
    PROJECT_DIR = Path(__file__).resolve().parent


FRONTEND_DIR = PROJECT_DIR / "frontend"

PYTHON = sys.executable if not getattr(sys, "frozen", False) else "python"
NPM = "npm.cmd"

FRONTEND_URL = "http://localhost:5173"


# ============================================================
# MICROSOFT EDGE
# ============================================================

def find_edge():
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",

        Path(os.environ.get("PROGRAMFILES", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",

        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
    ]

    for path in candidates:
        if path.exists():
            return path

    return None


# ============================================================
# START BACKEND
# ============================================================

def start_backend():
    print("[1/2] Starting NOVA backend...")

    return subprocess.Popen(
        [PYTHON, "api.py"],
        cwd=str(PROJECT_DIR),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )


# ============================================================
# START FRONTEND
# ============================================================

def start_frontend():
    print("[2/2] Starting NOVA frontend...")

    return subprocess.Popen(
        [NPM, "run", "dev"],
        cwd=str(FRONTEND_DIR),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )


# ============================================================
# OPEN EDGE
# ============================================================

def open_edge():
    print()
    print("Opening NOVA in Microsoft Edge...")

    edge = find_edge()

    if edge:
        subprocess.Popen(
            [
                str(edge),
                FRONTEND_URL,
            ]
        )
    else:
        print("Microsoft Edge was not found.")
        print("Opening the default browser instead...")

        import webbrowser
        webbrowser.open(FRONTEND_URL)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("                 NOVA")
    print("          Local AI Agent Launcher")
    print("=" * 60)
    print()

    print(f"Project folder: {PROJECT_DIR}")
    print(f"Frontend folder: {FRONTEND_DIR}")
    print()

    # Safety checks
    if not PROJECT_DIR.exists():
        print("ERROR: NOVA project folder was not found.")
        print(PROJECT_DIR)
        input("Press ENTER to exit...")
        return

    if not (PROJECT_DIR / "api.py").exists():
        print("ERROR: api.py was not found.")
        print(PROJECT_DIR / "api.py")
        input("Press ENTER to exit...")
        return

    if not FRONTEND_DIR.exists():
        print("ERROR: frontend folder was not found.")
        print(FRONTEND_DIR)
        input("Press ENTER to exit...")
        return

    backend = None
    frontend = None

    try:

        # ----------------------------------------------------
        # BACKEND
        # ----------------------------------------------------

        backend = start_backend()

        time.sleep(2)

        if backend.poll() is not None:
            print()
            print("ERROR: NOVA backend stopped immediately.")
            input("Press ENTER to exit...")
            return

        # ----------------------------------------------------
        # FRONTEND
        # ----------------------------------------------------

        frontend = start_frontend()

        time.sleep(4)

        if frontend.poll() is not None:
            print()
            print("ERROR: NOVA frontend stopped immediately.")
            input("Press ENTER to exit...")
            return

        # ----------------------------------------------------
        # OPEN EDGE
        # ----------------------------------------------------

        open_edge()

        print()
        print("=" * 60)
        print("NOVA is running.")
        print()
        print(f"Frontend: {FRONTEND_URL}")
        print("Backend:  http://127.0.0.1:8000")
        print()
        print("Keep this window open while using NOVA.")
        print("Press CTRL+C here to stop NOVA.")
        print("=" * 60)

        # ----------------------------------------------------
        # KEEP LAUNCHER ALIVE
        # ----------------------------------------------------

        while True:

            if backend.poll() is not None:
                print()
                print("ERROR: NOVA backend stopped.")
                break

            if frontend.poll() is not None:
                print()
                print("ERROR: NOVA frontend stopped.")
                break

            time.sleep(1)

    except KeyboardInterrupt:

        print()
        print("Stopping NOVA...")

    except Exception as error:

        print()
        print("NOVA launcher error:")
        print(error)

    finally:

        print()
        print("Cleaning up NOVA processes...")

        if frontend is not None and frontend.poll() is None:
            frontend.terminate()

        if backend is not None and backend.poll() is None:
            backend.terminate()

        print("NOVA stopped.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
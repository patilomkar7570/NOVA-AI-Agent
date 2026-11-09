# NOVA Alpha 0.5 — Voice and UI Update

**Release tag:** `v0.5.0-alpha`

NOVA Alpha 0.5 is a major update centred around a complete voice interaction experience, including dedicated Voice Mode, local and online speech recognition, and local text-to-speech through Voicebox.

This release also introduces a refreshed interface with the Mercury Orb, improved multilingual support, expanded browser compatibility, a more structured multi-agent architecture, and significant reliability improvements.

The goal is to make NOVA a more natural, capable, and locally powered AI assistant.

**NOVA is the core AI assistant project in the NOVA ecosystem.**


---

# ⬇️ Installation & Setup

> **Read before installing:** NOVA Alpha 0.5 is a Windows local-first development/alpha build. The interface runs in a browser; a standalone desktop application and a self-contained EXE are not included. This repository provides manual setup instructions and a portable development launcher. Install the prerequisites and download the required models separately before starting NOVA.

## 1. Check the system requirements

- **Operating system:** Windows 10 22H2 (64-bit) or Windows 11 (64-bit).
- **Memory:** 16 GB RAM is the minimum target for the two-model setup; 32 GB is recommended for smoother multitasking.
- **Storage:** Keep at least 20 GB free for the application, AI models, voice models, and temporary downloads.
- **Internet:** Required for the initial application/dependency/model downloads. Browser-based speech recognition may also use an online recognition service.
- **Audio:** A working microphone and speakers/headphones are recommended for Voice Mode.

The AI models can be demanding. Performance depends on the CPU, GPU, RAM, available VRAM, and background applications.

## 2. Download NOVA Alpha 0.5

1. Open the [NOVA GitHub Releases page](https://github.com/patilomkar7570/NOVA-AI-Agent/releases).
2. Download the source archive for **Alpha 0.5 / `v0.5.0-alpha`** from the [published release](https://github.com/patilomkar7570/NOVA-AI-Agent/releases/tag/v0.5.0-alpha).
3. Extract the archive to a normal writable folder.
4. Keep the project structure intact. The main folder should contain files such as `api.py`, `agent.py`, `requirements.txt`, and a `frontend` folder.
5. Place `Startup-Portable.bat` in that main project folder, beside `api.py` and `agent.py`.

Do not mix Alpha 0.5 files with the older Alpha 0.4 source.

## 3. Install Python

NOVA uses Python for its backend. Install **Python 3.11 or newer** and make sure the Windows Python launcher (`py`) is available in PowerShell.

1. Install the [Python Install Manager](https://www.python.org/downloads/) for Windows. The [official Windows instructions](https://docs.python.org/3/using/windows.html) explain the manager and its commands.
2. Open a new PowerShell window.
3. Confirm that Python 3.11 or newer is available:

   ```powershell
   py -3 --version
   ```

4. In the NOVA project folder, create a virtual environment and install the Python requirements:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

Use the same Python installation to create the virtual environment and install the backend dependencies. If the `py` launcher is unavailable, install Python from the official download page and use `python` in place of `py -3`.

## 4. Install Node.js and npm

NOVA's frontend uses Node.js and npm.

1. Open the [official Node.js download page](https://nodejs.org/en/download/).
2. Select the **LTS** release for Windows x64. Do not choose an Alpha, nightly, or Current build for this setup.
3. Run the installer and keep the npm option enabled.
4. Open a new terminal and verify:

   ```powershell
   node --version
   npm --version
   ```

NOVA does not pin a specific Node.js release. Use a current **LTS** version from the official download page; npm is installed alongside Node.js.

## 5. Install the frontend packages

1. Open PowerShell in the NOVA project folder.
2. Move into the frontend folder:

   ```powershell
   cd frontend
   ```

3. If `package-lock.json` is present, install the locked dependencies:

   ```powershell
   npm ci
   ```

   If the release archive does not contain a lock file, use:

   ```powershell
   npm install
   ```

4. Build the frontend:

   ```powershell
   npm run build
   ```

5. Return to the project root:

   ```powershell
   cd ..
   ```

Do not delete `package.json` or the lock file. They define the frontend dependencies and scripts.

## 6. Install Ollama and download NOVA's language models

Ollama runs NOVA's local language models.

1. Download and install [Ollama for Windows](https://ollama.com/download/windows).
2. Open a new PowerShell window.
3. Download the two model variants used by NOVA's current default configuration:

   ```powershell
   ollama pull qwen3:8b
   ollama pull qwen3:1.7b
   ```

4. Confirm that both models appear:

   ```powershell
   ollama list
   ```

5. Make sure Ollama is running. The Windows app normally runs its local service in the background. If you need to start it manually, use:

   ```powershell
   ollama serve
   ```

NOVA connects to Ollama at `http://127.0.0.1:11434` by default. The local Ollama REST API does not require a cloud API key for this local setup.

## 7. Install and prepare Voicebox

Voicebox provides NOVA's local speech recognition and speech generation.

1. The Alpha 0.5 setup instructions use [Voicebox 0.5.0 for Windows x64](https://github.com/jamiepine/voicebox/releases/download/v0.5.0/Voicebox_0.5.0_x64_en-US.msi). Follow the [official Voicebox installation guide](https://docs.voicebox.sh/overview/installation) to install it.
2. Double-click the MSI and complete the installation.
3. Launch Voicebox from the Windows Start menu.
4. Wait for the Voicebox local server to become ready. The application should show that its backend/server is running.
5. Check the model manager in Voicebox:
   - Download **Whisper Base** for local speech-to-text.
   - Download **Kokoro** for the default lightweight text-to-speech path.
6. Open Voicebox's voice/profile area and select or create a preset voice profile.
7. Open NOVA's Voice settings and select a compatible Voicebox profile.

In Voicebox's model manager, download **Whisper Base** for speech-to-text and **Kokoro** for the default text-to-speech path. Additional engines and voice choices are optional and depend on the Voicebox version and models installed. Voicebox supports multiple TTS engines and preset/custom voice profiles; these optional models are not downloaded automatically by NOVA.

Useful Voicebox guides:
- [Quick Start and voice profiles](https://docs.voicebox.sh/overview/quick-start)
- [Preset voices](https://docs.voicebox.sh/overview/preset-voices)
- [Available TTS models](https://docs.voicebox.sh/developer/model-management)
- [Whisper transcription](https://docs.voicebox.sh/developer/transcription)
- [TTS engine integration](https://docs.voicebox.sh/developer/tts-generation)

Voicebox normally exposes its local API at `http://127.0.0.1:17493`. NOVA uses this local service for Whisper transcription, voice profiles, and speech generation. No hosted Voicebox API key is required for this local connection.

## 8. Install and choose a supported browser

NOVA's Playwright browser automation supports these desktop browsers:

- [Brave](https://brave.com/download/) — use the regular Release/Stable version.
- [Microsoft Edge](https://www.microsoft.com/edge/download) — use the regular Stable version.
- [Google Chrome](https://www.google.com/chrome/) — use the regular Stable version.

**Recommended setup:**

1. Install at least one of the supported browsers.
2. In Windows **Settings → Apps → Default apps**, select Brave, Edge, or Chrome as the default browser if you want NOVA to follow that browser.
3. Keep the browser updated.
4. When NOVA opens its local interface for the first time, allow microphone access if you plan to use Voice Mode.

NOVA's browser runtime detects a supported Windows default browser. If the default browser is not Brave, Edge, or Chrome, the runtime uses Microsoft Edge as its fallback. NOVA does not need you to change your normal browser profile or install a special browser extension.

The browser automation layer uses Playwright for Python and launches the selected Chromium-based browser with a separate NOVA automation profile. Playwright's documentation notes that using a custom installed browser executable is version-sensitive; using a supported stable browser and keeping it updated is recommended.

References:
- [Playwright for Python — browser setup](https://playwright.dev/python/docs/browsers)
- [Playwright BrowserType API](https://playwright.dev/python/docs/api/class-browsertype)

### Browser speech recognition note

The online recognition mode uses the browser's SpeechRecognition/Web Speech API where the browser supports it. Availability and behaviour can vary by browser and version, and standard browser recognition may depend on an online service.

Do not assume that installing stable Edge automatically enables offline browser recognition. Microsoft's documented on-device SpeechRecognition feature is currently limited to suitable Edge Insider Canary/Dev builds with the relevant on-device flag enabled. NOVA's local offline path is **Voicebox + Whisper Base**, which is separate from that experimental Edge feature.

## 9. Start NOVA

Before starting:

- Python dependencies have been installed.
- Frontend dependencies have been installed.
- Ollama is running and both Qwen3 models are downloaded.
- Voicebox is open and its local server is ready if you want voice features.
- `Startup-Portable.bat` is in the main NOVA project folder.

Then:

1. Double-click `Startup-Portable.bat`.
2. Leave the NOVA backend and frontend terminal windows open.
3. Open the frontend address shown by the Vite terminal. The usual development address is `http://127.0.0.1:5173`.
4. The backend health endpoint is `http://127.0.0.1:8000/api/health`.
5. Keep Voicebox running while using local transcription or speech generation.

`Startup-Portable.bat` is a development launcher, not an application installer. It prefers the project's `.venv` Python interpreter; if that environment is missing, it falls back to `python` on Windows `PATH`. Ollama and npm must also be available on `PATH`. The script starts the frontend development server, but it does not install software or download AI models.

---

# 🎙️ What's new in Alpha 0.5

## 1. Voice Mode — the headline feature

Voice Mode is the centrepiece of NOVA Alpha 0.5. It is designed as a separate, more complete way to interact with NOVA, rather than just a microphone button attached to ordinary chat.

### Hybrid online and offline speech recognition

- **Auto mode:** Uses the available online recognition path and provides a local retry/fallback route when required.
- **Online mode:** Uses browser-based speech recognition where supported.
- **Local mode:** Sends captured audio to NOVA's backend, which forwards it to Voicebox and Whisper.
- Local Whisper recognition can work without relying on the browser's online speech-recognition service once the required Voicebox model is installed.

### Live voice interaction

- Animated listening/recording feedback.
- Live transcript shown in the interface.
- Stop control for ending capture.
- Review recognised text before sending it.
- Manual send control.
- A local retry path when browser recognition fails or is unavailable.

### Multiple voices and speech generation

- Voicebox-backed speech output.
- Voice profile selection in NOVA's Voice settings.
- Support for multiple compatible preset/custom voice profiles.
- Speech output can use a different engine from the speech-recognition engine.
- Progressive voice generation and playback handling, including interruption/resume support in the backend integration.

Voice availability depends on the engines and profiles installed in Voicebox. The Alpha 0.5 setup path downloads Kokoro as its default TTS model; optional engines must be installed separately.

## 2. Expanded browser compatibility

NOVA's Playwright automation is no longer tied to Brave alone.

- Brave
- Microsoft Edge
- Google Chrome

The browser runtime detects a supported browser and uses a separate NOVA automation profile for the selected browser. If the Windows default is unsupported, Microsoft Edge is the fallback. NOVA does not change the system-wide default browser.

## 3. Chat and small UI refinements

- Added a search button to the chat interface.
- Made small interface refinements.
- Improved voice-mode controls and interaction feedback.

This is a focused UI update, not a complete redesign.

## 4. Bug fixes and reliability improvements

- More browser-neutral session cleanup and recovery.
- Clearer handling of local voice service failures.
- Improved backend error handling around Voicebox speech generation.
- Additional bug fixes and integration refinements.

---

# 🔌 Local APIs and service connections

NOVA's core AI and voice integrations in this Alpha 0.5 setup are local services on the same computer.

| Component | Local address | What NOVA uses it for |
|---|---|---|
| NOVA Python backend | `http://127.0.0.1:8000` | Frontend-to-backend communication |
| Ollama | `http://127.0.0.1:11434` | Local Qwen3 language models |
| Voicebox | `http://127.0.0.1:17493` | Whisper transcription, voice profiles, and TTS |
| NOVA frontend dev server | `http://127.0.0.1:5173` | Browser-based NOVA interface |

### Important NOVA backend routes

- `GET /api/health` — checks whether the NOVA backend is responding.
- `GET /api/voice/profiles` — lists Voicebox voice profiles exposed to NOVA.
- `GET /api/voice/whisper/status` — checks local Whisper model status.
- `POST /api/voice/transcribe` — sends WAV audio to the local Voicebox transcription path.
- `POST /api/voice/speak` — requests speech generation using the selected Voicebox profile and language.
- `POST /api/voice/whisper/download` and `POST /api/voice/whisper/preload` — manages the local Whisper model through NOVA's backend.

### Ollama connection

NOVA uses Ollama's local REST API, including the chat endpoint:

- `POST http://127.0.0.1:11434/api/chat`

`agent.py` defaults to `qwen3:8b` for planning and browser tasks and `qwen3:1.7b` for faster ordinary chat. The smaller chat model can fall back to the main model if it is not installed. The optional `scripts/preload_nova_models.ps1` helper checks both models and asks Ollama to keep them resident.

Official reference: [Ollama API — chat endpoint](https://docs.ollama.com/api/chat).

### Voicebox connection

NOVA communicates with Voicebox through its local API. The integration checks Voicebox's OpenAPI schema where needed so it can adapt to the request fields exposed by the installed Voicebox build. Important local Voicebox paths used by the setup/integration include:

- `/openapi.json` — inspect the installed API schema.
- `/models/status` and `/models/download` — model status and downloads.
- `/transcribe` — local audio transcription.
- `/profiles` — voice profiles.
- `/generate` — speech generation.

Official references: [Voicebox model management](https://docs.voicebox.sh/developer/model-management), [transcription](https://docs.voicebox.sh/developer/transcription), and [TTS generation](https://docs.voicebox.sh/developer/tts-generation).

### Do I need an API key?

For the local Alpha 0.5 setup described here:

- **Ollama local API:** No cloud API key is required.
- **Voicebox local API:** No hosted API key is required for the local service.
- **Playwright/browser automation:** No separate browser automation API key is required.
- **Browser SpeechRecognition:** No NOVA API key is entered, but the browser's online recognition implementation may use a browser-managed network service.

The reviewed Alpha 0.5 setup files do not specify an OpenAI, Gemini, or Anthropic API key as a requirement for the local Qwen3 + Voicebox workflow. This does not rule out optional integrations added in other branches or later releases. Never place private API keys, passwords, personal file paths, or private recordings in this README or in a public issue.

---

# 🧩 Important project files

- `api.py` — Python API/backend entry point.
- `agent.py` — core AI agent and browser automation logic.
- `requirements.txt` — Python dependencies.
- `frontend/` — NOVA's browser-based interface.
- `nova_browser_runtime.py` — browser detection and browser-specific automation profile support.
- `apply_playwright_browser_compat.py` — development patch utility for browser compatibility.
- `Startup-Portable.bat` — portable development launcher.
- `app.py` — legacy Tkinter interface; it is not used by the current browser-based startup path.

Keep the development tools and backups until a later cleanup. The current Alpha 0.5 interface is still browser-based; the standalone desktop application/EXE is planned separately and is not included in this release.

---

# 🧪 Validation status and known limitations

The Alpha 0.5 automated regression suite was run locally before publication:

- **81 Python regression tests passed.**
- **25 frontend voice tests passed.**
- **106 total tests passed; 0 failed.**

These results cover the automated tests included with this release. They do not represent a clean-machine installation test or guarantee compatibility with every Windows configuration, model, browser, or website.

The current release uses the manual setup instructions above. `Startup-Portable.bat` is a development launcher: it starts the local backend and frontend, but does not install prerequisites or download models. A one-click installer is not included in this release.

The following areas still need broader real-world validation:

- Clean installation on a separate Windows machine.
- Microphone and speech-recognition testing across supported browsers and audio devices.
- Full local model download and load testing across different hardware configurations.
- End-to-end Voice Mode testing with different Voicebox profiles and languages.
- Browser automation testing across a wider range of websites and login/consent flows.

## Troubleshooting checklist

- **Python not found:** Reopen PowerShell after installing Python. Check `py -3 --version` or `python --version`.
- **Python dependency error:** Confirm `.venv` was created with Python 3.11 or newer and rerun `pip install -r requirements.txt` using `.venv\Scripts\python.exe`.
- **npm not found:** Install Node.js LTS, reopen the terminal, and check `node --version` and `npm --version`.
- **Ollama is unavailable:** Open Ollama and run `ollama list`. Confirm the local API responds at `http://127.0.0.1:11434/api/tags`.
- **Voicebox is unavailable:** Open Voicebox and wait for its local server to become ready. Check `http://127.0.0.1:17493/models/status`.
- **No local transcription:** Confirm Whisper Base is downloaded in Voicebox and select Local or retry locally in NOVA's Voice Mode.
- **No voice output:** Confirm Kokoro or another compatible TTS engine is installed, a voice profile exists, and that profile supports the selected language.
- **Microphone not detected:** Allow microphone access for the NOVA local website in Windows and browser site settings.
- **Browser automation cannot launch:** Install/update one of the supported stable browsers and set it as the Windows default. Check the backend console for the detected browser and executable.

---

# 🔗 Official downloads and documentation

- [NOVA project releases](https://github.com/patilomkar7570/NOVA-AI-Agent/releases)
- [Python downloads / Install Manager](https://www.python.org/downloads/)
- [Python on Windows documentation](https://docs.python.org/3/using/windows.html)
- [Node.js downloads](https://nodejs.org/en/download/)
- [Ollama for Windows](https://ollama.com/download/windows)
- [Ollama API documentation](https://docs.ollama.com/api/chat)
- [Voicebox Windows installation](https://docs.voicebox.sh/overview/installation)
- [Voicebox 0.5.0 Windows MSI](https://github.com/jamiepine/voicebox/releases/download/v0.5.0/Voicebox_0.5.0_x64_en-US.msi)
- [Voicebox API and model documentation](https://docs.voicebox.sh/developer/model-management)
- [Brave Stable](https://brave.com/download/)
- [Microsoft Edge Stable](https://www.microsoft.com/edge/download)
- [Google Chrome](https://www.google.com/chrome/)
- [Playwright for Python](https://playwright.dev/python/docs/browsers)


## 📜 Licensing

The NOVA project is licensed under [PolyForm Noncommercial 1.0.0](LICENSE). This licence applies to NOVA's original project code and contributions that the project has the right to license. Third-party components retain their own licence terms and notices; see the [`LICENSES/`](LICENSES/) directory.

---

**NOVA Alpha 0.5 — Voice and UI Update**
*More natural voice interaction. Local and online speech. A more expressive NOVA interface.*

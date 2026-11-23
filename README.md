# NOVA Beta 0.6 — Desktop Control & Multi-Agent Architecture

**Release tag:** `v0.6.0-beta`  
**Release status:** Beta (Development line)  
**Core identity:** NOVA is the core local-first AI assistant in the NOVA ecosystem.

---

## 🚀 Welcome to NOVA Beta

> **We have officially transitioned from Alphas to Betas!**  
> In the **Alpha** series (`v0.1.0-alpha` through `v0.5.0-alpha`), our engineering was dedicated to autonomous browser control, voice synthesis with Voicebox, and conversational foundations. Desktop OS control was intentionally omitted.  
> 
> In the **Beta** series, NOVA expands into full **Desktop Control** and the **Coder Agent** specialist. You can now direct NOVA to interact with Windows applications, manage local files, adjust system controls, write and test code, and seamlessly bridge the gap between your browser and your desktop operating system.  
> 
> **Beta 0.6 is the very first update of the Beta era.**

---

## 🌟 Key Highlights in Beta 0.6

### 1. 🖥️ Native Windows Desktop Control
* **OS-Level UI Automation:** Launch, focus, inspect, and automate Windows applications (Notepad, File Explorer, VS Code, Calculator, Settings) via native Win32 APIs and PowerShell.
* **Perception & Screenshot Grounding:** High-resolution desktop screen capture with dual-pipeline fallback (native GDI/Forms and Pillow) for vision-grounded reasoning.
* **System Hotkeys & Media:** Control system volume (mute/unmute, volume up/down), media playback (play/pause, skip, prev), and window states (minimize all, show desktop, lock workstation).
* **Dedicated Desktop Memory:** Isolated snapshot history in `desktop_memory.py` maintaining action history, window hierarchy, and safety policies.

### 2. 💻 Autonomous Coder Specialist
* **Code Repository Inspection:** Read, search, and analyze source files across your workspace.
* **Syntax Checking & Workspace Patching:** Generate clean diffs and apply patches safely.
* **Automated Test Validation:** Run unit test suites (`unittest`, `pytest`) to verify implementations before execution completes.

### 3. 🎯 Execution Mode Selector (Prompt Bar & Settings)
* **Prompt Bar Dropdown:** Toggle execution strategy on the fly directly from the prompt bar:
  * **Auto Mode (✨):** Intelligent multi-agent routing between Chat, Research, Browser, Computer (Desktop), and Coder specialists.
  * **Browser Mode (🌐):** Routes directly to the dedicated Playwright / Brave browser specialist.
  * **Desktop Mode (🖥️):** Routes directly to the Computer Specialist for native Windows UI automation.
* **Ergonomic Layout:** Prompt bar elevated above quick-action suggestions for rapid input.
* **Capybara Walking Loader:** Playful, animated walking capybara (MIT licensed by Novaxlo) indicating active agent execution.

### 4. 🎛️ Hybrid Dual Engine: Gemini Cloud + Local Ollama
* **Google Gemini Cloud Integration:** High-speed cloud reasoning with Gemini 2.5 Flash, Gemini 2.5 Pro, and Gemini 2.0 Flash.
* **Local Ollama Inference:** 100% offline private processing with Qwen models (`qwen3:1.7b`, `qwen3:8b`).
* **Models & AI Settings Tab:** Configure API keys, test connection latency, and designate specialized models for Chat vs. Work/Planning.
* **Zero-Leak Security Architecture:** Secrets are dynamically initialized at runtime into git-ignored `nova_model_settings.json`. Empty tracking template provided in `nova_model_settings.example.json`.

---

# ⬇️ Installation & Setup

> **Read before installing:** NOVA Beta 0.6 is a local-first Windows development build. The interface runs in modern browsers (Brave, Edge, Chrome) backed by a Python FastAPI server. A standalone desktop application and self-contained installer are in active development; launch immediately via `Startup-Portable.bat`.

## 1. Check System Requirements

- **Operating system:** Windows 10 22H2 (64-bit) or Windows 11 (64-bit).
- **Memory:** 16 GB RAM minimum; 32 GB recommended for running local models and browser automation simultaneously.
- **Storage:** 20 GB free space for virtual environments, Ollama weights, and temporary screenshots.
- **Internet:** Required for initial setup and optional Google Gemini cloud inference.
- **Audio:** Microphone and speakers/headphones for Voice Mode.

## 2. Download the Release

1. Visit the [NOVA GitHub Releases page](https://github.com/patilomkar7570/NOVA-AI-Agent/releases).
2. Download the source archive for **Beta 0.6 / `v0.6.0-beta`**.
3. Extract the archive to a standard writable directory (e.g. `C:\NOVA-AI-Agent`).
4. Ensure files such as `api.py`, `agent.py`, `requirements.txt`, and the `frontend/` directory are intact.

## 3. Install Python Environment

NOVA requires **Python 3.11 or newer** (tested on 3.11, 3.12, and 3.14).

```powershell
# Open PowerShell in the project root directory
py -3 --version

# Create virtual environment and install dependencies
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 4. Install Frontend Dependencies & Build

NOVA requires **Node.js LTS** (Node 20 or newer).

```powershell
cd frontend
npm install
npm run build
cd ..
```

## 5. Local Language Models (Ollama)

For offline, private execution:
1. Download and install [Ollama for Windows](https://ollama.com/download/windows).
2. Pull NOVA's recommended local models:

```powershell
ollama pull qwen3:1.7b
ollama pull qwen3:8b
```

## 6. (Optional) Cloud Models (Google Gemini)

If you prefer cloud-accelerated inference:
1. Obtain an API key from Google AI Studio.
2. Launch NOVA, open **Settings → Models & AI**, enter your API key, and click **Test Key** & **Save**.

## 7. Launching NOVA

Run the portable launcher:

```powershell
.\Startup-Portable.bat
```

Or start the services manually:

```powershell
# Terminal 1: Backend
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000

# Terminal 2: Frontend (Development)
cd frontend
npm run dev
```

Navigate to `http://localhost:5173` in your browser.

---

# 🧩 Important Project Files

- `api.py` — FastAPI backend server and WebSocket event streamer.
- `agent.py` — Core agent dispatch and orchestration runtime.
- `nova_agents/` — Multi-agent specialist framework:
  - `specialists/computer_agent.py` — Windows OS and desktop automation.
  - `specialists/coder_agent.py` — Code analysis, editing, and test runner.
  - `specialists/browser_agent.py` — Playwright web automation.
  - `specialists/chat_agent.py` — Conversational responses.
  - `specialists/research_agent.py` — Information retrieval.
  - `planner.py` & `orchestrator.py` — Intent analysis and multi-agent plan execution.
- `nova_models.py` — Model provider abstractions (Ollama & Gemini).
- `desktop_memory.py` — Desktop state and window history tracking.
- `frontend/` — React 19 + Vite user interface.
- `Startup-Portable.bat` — One-click development launcher.

---

# 🧪 Automated Validation Suite

Before tagging Beta 0.6, the automated regression suite verified:

- **249 Python unit tests executed cleanly:**
  - `test_computer_agent.py`: 51 tests passing (desktop screenshots, window management, audio/media hotkeys, allowlists).
  - `test_agent_mode.py`: Auto/Browser/Desktop routing verification.
  - `test_nova_models.py`: Model fallback and Gemini/Ollama configs.
  - `test_api_approval.py`: Approval policies and sandbox security.
  - `test_registry.py`: Agent specialist catalog and version metadata.
- **Frontend Vite build:** 0 errors, 111 modules compiled.

---

# 📜 Licensing & Attribution

- **NOVA Core Code:** Licensed under the [PolyForm Noncommercial 1.0.0 License](LICENSE).
- **Third-Party Components:** Licensed under the MIT License; see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) and the [`LICENSES/third-party/`](LICENSES/third-party/) folder:
  - *Hard Goose Switch* — [00Kubi on Uiverse.io](https://uiverse.io/00Kubi/hard-goose-47) (MIT)
  - *Capybara Loader* — [Novaxlo on Uiverse.io](https://uiverse.io/Novaxlo/kind-snail-5) (MIT)

---

**NOVA Beta 0.6 — Desktop Control & Multi-Agent Architecture**  
*Sovereign AI for Windows. Expanding from the browser to the full desktop.*

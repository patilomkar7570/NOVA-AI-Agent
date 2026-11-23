# NOVA Beta 0.6 — Desktop Control & Multi-Agent Architecture

**Release tag:** `v0.6.0-beta`  
**Previous release:** `v0.5.0-alpha`  
**Release date:** November 2026  
**License:** [PolyForm Noncommercial 1.0.0](LICENSE) (Third-party components under [MIT](LICENSES/))

---

## 🚀 Welcome to NOVA Beta: Beyond the Browser

NOVA has officially graduated from the **Alpha** series into the **Beta** series. 

* **The Alpha Journey (`v0.1.0-alpha` → `v0.5.0-alpha`):** We developed and refined the foundations of sovereign local AI—focusing on browser automation (Playwright/Brave/Chrome/Edge), conversational intelligence, and local speech-to-text / text-to-speech with Voicebox. Desktop-level OS interaction was intentionally out of scope during Alpha.
* **The Beta Milestone (`v0.6.0-beta`):** The Beta series introduces full **Desktop Control** and the **Coder Agent** specialist. NOVA can now observe your Windows desktop, launch and switch applications, trigger hotkeys, execute safe shell commands, inspect code repositories, and autonomously resolve tasks across both your browser and your local operating system.

---

## 🌟 What's New in Beta 0.6 (Everything Added in Antigravity)

### 1. 🖥️ Native Desktop Control Specialist (`ComputerAgent`)
* **OS-Level Windows Automation:** Directly launch, focus, inspect, and automate Windows applications (File Explorer, Notepad, VS Code, Calculator, Settings, etc.) via native Win32/PowerShell dispatch.
* **Screen Perception & Visual Grounding:** Capture high-resolution desktop screenshots with dual-pipeline capture (native GDI/Forms + Pillow fallback) for vision-grounded reasoning.
* **System & Media Hotkeys:** Control system volume (mute/unmute, volume up/down), media playback (play/pause, skip, prev), and window states (minimize all, show desktop, lock workstation).
* **Isolated Desktop Memory:** Dedicated persistent memory engine (`desktop_memory.py` / `desktop_snapshots`) maintaining action history, window hierarchy, and safety policies.

### 2. 💻 Autonomous Coder Specialist (`CoderAgent`)
* **Code Inspection & Workspace Editing:** Autonomous code analysis, syntax checking, diff generation, and workspace patch application.
* **Unit Test Execution:** Automatically run test runners (`unittest`, `pytest`) to verify fixes and validate code before committing.
* **Grounded Developer Workflows:** Integrated directly with the multi-agent router for coding-related prompts.

### 3. 🎯 Execution Mode Selector (Prompt Bar & Settings)
* **Prompt Bar Dropdown:** Seamless dropdown pill on the right side of the prompt bar to switch instantly between:
  * **Auto Mode (✨):** Intelligent multi-agent routing between Chat, Research, Browser, Computer (Desktop), and Coder specialists.
  * **Browser Mode (🌐):** Routes directly to the dedicated Playwright / Brave browser specialist.
  * **Desktop Mode (🖥️):** Routes directly to the Computer Specialist for native Windows UI automation.
* **Settings Integration:** Execution mode preference configurable and persisted from the new **Models & AI** settings tab.

### 4. 🎛️ Models & AI Settings Tab (Gemini Cloud + Ollama Dual Engine)
* **Google Gemini API Key Management:** Securely input, reveal/mask, and test your Gemini API key with live latency diagnostics.
* **Granular Model Selection:**
  * **Chat & Casual Inference:** Select between Google Gemini (`gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-2.0-flash`) and Local Ollama (`qwen3:1.7b`, `qwen3:8b`).
  * **Planning & Work Inference:** Choose your primary multi-agent planner and coding LLM.
* **Zero-Leak Security Architecture:** API keys are stored in dynamically generated runtime configuration (`nova_model_settings.json`), which is strictly excluded from version control via `.gitignore`. A safe tracking template (`nova_model_settings.example.json`) is provided.

### 5. 🎨 UI & Layout Revamp
* **Ergonomic Layout Reversal:** The main prompt bar is elevated directly above the quick-action suggestions for a more modern, focused command interface. Suggestions sit cleanly below with responsive grid alignment.
* **Capybara Walking Loader:** Added the animated Capybara loader from Uiverse.io (Novaxlo) that walks across the top of the prompt bar during generation and gracefully departs once results arrive.
* **Hard Goose Theme Toggle:** Integrated the tactile Hard Goose voice/theme toggle from Uiverse.io (00Kubi).
* **Streamlined Settings Modal:** Simplified theme selection with centered, high-contrast cards and one-click auto-theme switching.

### 6. ⚖️ Legal Compliance & MIT Licensing
* **Third-Party Directory:** Created `LICENSES/third-party/` housing all upstream licenses (`HARD-GOOSE-MIT.txt`, `CAPYBARA-LOADER-MIT.txt`, `UIVERSE-MIT.txt`).
* **Third-Party Notices:** Comprehensive attribution in `THIRD-PARTY-NOTICES.md` documenting source URLs, authors, and license terms.
* **Core Project Licensing:** Core code remains licensed under PolyForm Noncommercial 1.0.0.

### 7. 🧪 Comprehensive Test Suite & Verification
* **249 Automated Tests:** Passing suite covering ComputerAgent, BrowserAgent, TaskPlanner, AgentMode routing, ModelSettings configuration, and approval policies.
* **Vite Frontend Build:** Verified with zero warnings/errors.

---

## 🏷️ Release Tag Information

```text
Tag: v0.6.0-beta
Message: NOVA Beta 0.6: Desktop Control & Multi-Agent Architecture
Commit: (Pending local commit)
Release Channel: beta
Target Branch: main
```

### Previous Release Sequence:
1. `v0.1.0-alpha` — Initial release & repository setup
2. `v0.2.0-alpha` — Autonomous browser execution
3. `v0.3.0-alpha` — Multi-agent routing & task memory
4. `v0.4.0-alpha` — Voice Integration and Agent Improvements
5. `v0.5.0-alpha` — Voice and UI Update (Mercury Orb, Voicebox TTS)
6. **`v0.6.0-beta` — Desktop Control & Multi-Agent Architecture (Current)**

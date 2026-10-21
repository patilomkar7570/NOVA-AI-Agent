# NOVA — Natural-language Operating & Virtual Assistant

> **Alpha 0.4 — Unreleased | Experimental Windows desktop AI agent**
>
> NOVA is a local-first AI agent that accepts natural-language instructions, plans browser actions with a local Ollama model, and carries them out in Brave using Playwright. Alpha 0.4 focuses on voice input, a refreshed interface, stronger website-aware task handling, and a local website-learning layer.

## Highlights in Alpha 0.4

### 🎙️ Voice-first command input

- Voice input is available from the Home and Chat experiences through a shared microphone interaction.
- A visible listening state and animated microphone feedback make it clearer when NOVA is listening.
- Speech is transcribed into the command composer so you can review or edit it before sending.
- Microphone-permission and speech-service errors are surfaced in the interface.

**Voice support note:** the current voice UI uses the browser's Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`). Availability differs between browsers and may depend on a browser-managed speech service and an internet connection. This is not the same as an offline Whisper transcription engine, and offline voice recognition is not guaranteed. If voice input is unavailable in your browser, try a supported, up-to-date browser such as Microsoft Edge, allow microphone access, and check whether your browser or network is blocking its speech service.

### ✨ Refreshed user interface

- Updated Home and Chat command-entry experiences.
- Shared voice-input behavior between the Home and Chat microphone controls.
- Clearer listening, running, stopped, and error feedback.
- Improved task-progress/activity presentation so users can understand what NOVA is doing without relying only on raw terminal output.
- Responsive styling refinements for the main agent workflow.

### 🧠 Improved website-aware agent behavior

- Uses the local **`qwen3:8b`** model through Ollama for task planning and browser decisions.
- Carries conversational context between related commands and can keep the current website in context for follow-up instructions.
- Uses bounded action plans and limited replanning to keep browser tasks focused.
- Can resolve website names and site-scoped requests before asking the model to guess a destination.

NOVA is experimental. A good plan does not guarantee that every website action will succeed: site layouts, login requirements, consent prompts, network conditions, and browser changes can affect results.

### 🌐 Local website directory

- Includes a searchable directory of website names, URLs, hosts, aliases, and regional variants.
- The current dataset checked for this release contains approximately **1,116 entries**.
- Alias matching helps NOVA recognize common names and direct commands such as “open …” to a suitable website URL.
- Regional preferences help choose an appropriate country-specific destination when one is available; an explicit region in a command can take precedence.

The checked-in `website_directory.json` is reference data used by the resolver, not a record of an individual user's browsing history. Keep personal runtime data and credentials out of this file.

### 📚 Local website learning and memory

NOVA's website-memory module uses a local SQLite database to retain reusable website knowledge, including:

- Page profiles and lightweight page/controls metadata.
- Previously verified element locators for actions such as clicking and typing.
- Reusable workflow patterns scoped to a website and starting page.
- Success/failure and last-used information to help rank previously useful locators and workflows.

This is **retrieval-based local learning**, not fine-tuning or retraining the Qwen model. The database is created locally as needed and is not intended to be committed to the public repository. It is designed to store website metadata and reusable action patterns, not passwords, cookies, or form contents.

### 🧰 Runtime and startup improvements

- Adds a one-click Windows launcher for the backend and Vite frontend.
- Keeps per-installation runtime data, browser profiles, memory, and SQLite state separate from the shared source code.
- Adds a `.gitignore` policy for generated and personal runtime files.
- Includes the website-directory resolver and website-memory modules required by the current agent workflow.

---

## How NOVA works

```text
Voice or typed command
          ↓
      React + Vite UI
          ↓  HTTP API (127.0.0.1:8000)
       Python backend
          ↓
 Website directory + local website memory
          ↓
 Ollama / qwen3:8b plans browser actions
          ↓
 Playwright controls the Brave browser
          ↓
 Progress and results return to the UI
```

NOVA is intended to run on your own Windows PC. The browser agent and its persistent browser profile can interact with websites using the permissions and account state available in that profile. Review a task before using it for sensitive actions.

## Requirements

Install these before launching NOVA:

1. **Windows 10 or 11**.
2. **Python 3.11 or newer** available as `py` or `python` in PowerShell.
3. **Node.js LTS and npm**.
4. **Brave Browser** installed on the machine. The current agent searches standard Brave installation locations.
5. **Ollama for Windows**, running locally.
6. The **`qwen3:8b`** Ollama model downloaded locally.

NOVA currently expects Ollama's `qwen3:8b` model by default. If you change the model in the agent configuration, make sure the corresponding model is installed in Ollama too.

## Start NOVA from scratch

These steps are for a new clone and a first-time setup.

### 1. Clone the repository

Open PowerShell and run:

```powershell
git clone https://github.com/patilomkar7570/NOVA-AI-Agent.git
cd NOVA-AI-Agent
```

If you already downloaded the source as a ZIP, extract it and open PowerShell in the extracted `NOVA-AI-Agent` folder instead.

### 2. Install and prepare Ollama

Install Ollama, launch it, then download the model:

```powershell
ollama pull qwen3:8b
ollama list
```

Make sure `qwen3:8b` appears in the model list and Ollama is running before starting the backend. The first model download can be several gigabytes and will take time depending on your connection.

### 3. Create the Python environment

Run these commands from the **repository root** (the folder containing `api.py`):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell refuses to activate the environment, you can skip activation and install packages using the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Install frontend dependencies

In a second PowerShell command, or after returning to the repository root, run:

```powershell
cd frontend
npm install
```

Keep the frontend dependencies in `frontend/node_modules`; this folder is generated locally and should not be committed.

### 5. Start the backend

Open a PowerShell terminal in the **repository root** and run:

```powershell
.\.venv\Scripts\python.exe api.py
```

Leave this terminal open. The backend starts NOVA's browser worker and may launch Brave. The API listens on `127.0.0.1:8000`.

You can check the local backend health at <http://127.0.0.1:8000/api/health>.

### 6. Start the frontend

Open another PowerShell terminal and run:

```powershell
cd path\to\NOVA-AI-Agent\frontend
npm run dev
```

Replace `path\to\NOVA-AI-Agent` with the actual folder where you cloned or extracted the project. Vite will print the local URL, normally <http://localhost:5173>.

Open that URL in your browser. Keep both the backend and frontend terminals open while using NOVA.

### 7. Use voice input

1. Open NOVA in a browser that supports its Web Speech API integration.
2. Allow microphone permission when prompted.
3. Press the microphone button on Home or in Chat.
4. Speak clearly, then stop listening and review the transcription in the command field.
5. Edit the command if needed and send it.

If the microphone is unavailable, check site permissions and your selected input device. Errors such as `network` or `service-not-allowed` may mean the browser's speech service is unavailable or blocked. Voice input is not guaranteed to work offline.

---

## Optional: One-click Windows startup

The repository includes `NOVA_One_Click_Startup.bat`, which starts the Python backend and frontend in separate terminal windows. Complete the prerequisites above first, including the Ollama model and Python/frontend dependencies.

The portable version of the launcher uses its own folder as the project root, so it can be run after cloning to a different directory. Keep both launched windows open while NOVA is running. If either one reports an error, read that terminal message first; the launcher cannot fix missing browser installations, missing Ollama models, or blocked speech services automatically.

## Local files and privacy

Some files are generated on each installation and should remain local. Depending on which features have been used, these can include:

- `BraveAgentProfile/` — NOVA's dedicated browser profile.
- `chat_history.json` — saved chat records.
- `nova_memory.json` — local agent/conversation memory, if enabled by the current build.
- `nova_page_text/` — local page-text snapshots, if created by the current build.
- `nova_website_memory.sqlite3` and its SQLite WAL/SHM files — website profiles, locator history, and workflow metadata.
- Python virtual environments, `frontend/node_modules/`, logs, and build output.

These are per-installation files, not release assets. The `.gitignore` should continue excluding personal/runtime data. The public website directory `website_directory.json` is different: NOVA uses it as a static, shared lookup dataset.

## Troubleshooting

| Problem | What to check |
|---|---|
| Backend does not start | Activate `.venv`, confirm dependencies were installed from `requirements.txt`, and read the backend terminal error. |
| Ollama/model error | Launch Ollama and check `ollama list` for `qwen3:8b`. |
| Brave does not open | Install Brave Browser and make sure it is available in a standard installation path. |
| UI says the backend is offline | Start `api.py` and confirm `http://127.0.0.1:8000/api/health` responds. |
| Frontend dependencies are missing | Run `npm install` inside `frontend/`. |
| Voice button is unavailable or fails | Allow microphone access, try a supported browser, and check browser/network policies for its speech-recognition service. |
| NOVA chooses the wrong website | Use a more specific command, including the site's name or intended region. Website layouts and aliases can change over time. |

## Development notes

- Backend: Python, local Ollama model, Playwright, and Brave Browser.
- Frontend: React and Vite.
- Local website-memory storage: SQLite.
- Website lookup: `website_directory.py` reads `website_directory.json` at startup.
- The agent is designed for experimentation. Review actions before relying on it for purchases, account changes, or other sensitive work.

## Alpha 0.4 — Unreleased change summary

- **Voice integration:** Home and Chat microphone interaction, animated listening UI, live transcription into the command composer, and more visible voice errors.
- **Interface:** refreshed command-entry, chat and task-status/activity UI.
- **Agent:** improved website-aware context and request routing, using Ollama's `qwen3:8b` to plan browser actions.
- **Learning:** local SQLite storage for website/page metadata, verified locators, and reusable workflow patterns with success/failure tracking.
- **Website directory:** local searchable reference directory with around 1,116 website entries, aliases, URLs, hostnames, and regional variants.
- **Startup and repository hygiene:** one-click Windows launcher; runtime files excluded from version control; shared website directory kept separate from personal browser/memory databases.

> Alpha 0.4 is unreleased and experimental. Feature availability—especially browser speech recognition—depends on local software, browser capabilities, network connectivity, and website behavior. The learning system stores reusable metadata; it does not train a new model.

## License

No license has been specified here yet. Until a license file is added, do not assume the code is available for unrestricted reuse or redistribution.

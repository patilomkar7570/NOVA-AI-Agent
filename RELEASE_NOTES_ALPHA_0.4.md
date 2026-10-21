# NOVA Alpha 0.4 — Unreleased

**A more natural, website-aware NOVA experience.** Alpha 0.4 brings voice command input, interface refinements, improved website-focused agent behavior, a searchable website directory, and a local website-learning layer together in one development release.

## Highlights

### 🎙️ Voice integration
- Microphone controls in the Home and Chat experiences share the same voice-input flow.
- Animated listening feedback helps show when voice capture is active.
- Live speech transcription populates the command field for review/editing before sending.
- Clearer handling for microphone permissions, no-speech events, and browser speech-service/network failures.

### ✨ Interface refinements
- Updated command entry and Chat interactions.
- Improved listening/running/error status feedback.
- Refined task progress/activity presentation and visual styling.

### 🧠 More website-aware browser automation
- Uses Ollama's local `qwen3:8b` model to plan browser actions.
- Retains conversational context for related requests and can keep follow-up commands scoped to the active website.
- Uses limited action plans and replanning rather than relying on an unlimited sequence of steps.

### 🌐 Local website directory
- A bundled website-name resolver covers approximately 1,116 entries in the current dataset.
- Names, aliases, hostnames, URLs, and regional variants help map natural-language requests to destinations.
- Regional preferences support better selection when a website has country-specific versions.

### 📚 Local website learning
- SQLite stores website/page profiles, reusable locator metadata, and workflow patterns.
- Success/failure tracking helps rank previously useful locators and workflows.
- Learning data remains local to the user's installation; this is retrieval-based memory, not Qwen model training.

### 🧰 Startup and local-data hygiene
- Adds a one-click Windows startup workflow for the backend and frontend.
- Separates shared source/reference data from per-installation browser profile, chat history, agent memory, and SQLite files.
- Updates ignore rules so personal runtime state is not intentionally committed with source code.

## Setup reminder

See `README.md` for clean-install instructions. A fresh install requires Python, Node.js/npm, Brave Browser, Ollama, and the local `qwen3:8b` model. Browser speech recognition is browser-dependent and may require the browser's speech service and an internet connection; this release does not guarantee offline Whisper transcription.

## Status

**Unreleased / experimental.** Behavior may vary across websites and browser versions. Voice recognition, browser automation, and learned selectors should be tested before relying on them for important or sensitive actions.

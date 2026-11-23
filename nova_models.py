"""NOVA Multi-Model & Provider Engine.

Supports Local Models (via Ollama/Qwen) alongside Google Gemini Cloud Models (via Gemini API Key).
Provides unified role-based routing (Chat vs Work/Planning), model assignment switching,
API key validation, and runtime persistence.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

SETTINGS_FILE = Path(__file__).resolve().parent / "nova_model_settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "provider": "gemini",  # "local", "gemini", or "hybrid"
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", "").strip(),
    "unified_model": False,  # True = single model for both; False = split models
    "chat_model": {
        "enabled": True,
        "provider": "gemini",  # "local" or "gemini"
        "local_model": "qwen3:1.7b",
        "gemini_model": "gemini-3.5-flash-lite",
    },
    "work_model": {
        "enabled": True,
        "provider": "gemini",  # "local" or "gemini"
        "local_model": "qwen3:8b",
        "gemini_model": "gemini-3.5-flash-lite",
    },
    "updated_at": 0.0,
}

# Available preset models
AVAILABLE_GEMINI_MODELS = [
    {
        "id": "gemini-3.5-flash-lite",
        "name": "Gemini 3.5 Flash Lite",
        "description": "Ultra-fast responsive Google model. Generous rate limits, sub-second latency, ideal for chat and real-time planning.",
        "recommended_for": "chat_and_work",
    },
    {
        "id": "gemini-3-flash-preview",
        "name": "Gemini 3 Flash Preview",
        "description": "High-throughput frontier multimodal reasoning with broad context window.",
        "recommended_for": "work",
    },
    {
        "id": "gemini-3.1-flash-lite",
        "name": "Gemini 3.1 Flash Lite",
        "description": "Balanced speed and reasoning, excellent for automated actions and coding tasks.",
        "recommended_for": "chat_and_work",
    },
    {
        "id": "gemini-flash-lite-latest",
        "name": "Gemini Flash Lite (Latest)",
        "description": "Always routes to Google's latest available production Flash Lite model.",
        "recommended_for": "chat",
    },
    {
        "id": "gemini-3.7-flash",
        "name": "Gemini 3.7 Flash",
        "description": "Google's premier high-capability multimodal model for complex refactoring.",
        "recommended_for": "work",
    },
]

AVAILABLE_LOCAL_MODELS = [
    {
        "id": "qwen3:1.7b",
        "name": "Qwen 2.5 1.7B / Qwen 3 1.7B",
        "description": "Compact, lightning-fast on-device model. Zero GPU strain, ideal for conversational chat.",
        "recommended_for": "chat",
    },
    {
        "id": "qwen3:8b",
        "name": "Qwen 2.5 8B / Qwen 3 8B",
        "description": "Balanced on-device reasoning engine. Great for desktop tool execution and offline coding.",
        "recommended_for": "work",
    },
    {
        "id": "qwen2.5:14b",
        "name": "Qwen 2.5 14B",
        "description": "Heavyweight local model for high-end GPUs. High reasoning fidelity without internet.",
        "recommended_for": "work",
    },
]


def get_model_settings() -> dict[str, Any]:
    """Load model configuration from disk with default fallbacks.
    
    If the settings file does not exist, it is automatically created on first run
    with safe, empty default keys so the project is ready out-of-the-box.
    """
    if not SETTINGS_FILE.is_file():
        initial = dict(DEFAULT_SETTINGS)
        initial["gemini_api_key"] = os.environ.get("GEMINI_API_KEY", "").strip()
        initial["updated_at"] = time.time()
        try:
            SETTINGS_FILE.write_text(json.dumps(initial, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        return initial
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_SETTINGS)
        for k, v in data.items():
            if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        # Also check environment variable for Gemini API key override
        env_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if env_key and not merged.get("gemini_api_key"):
            merged["gemini_api_key"] = env_key
        return merged
    except Exception:
        return dict(DEFAULT_SETTINGS)


def save_model_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist model configuration to disk."""
    current = get_model_settings()
    for key in ("provider", "gemini_api_key", "unified_model"):
        if key in settings:
            current[key] = settings[key]

    for role in ("chat_model", "work_model"):
        if role in settings and isinstance(settings[role], dict):
            current[role] = {**current[role], **settings[role]}

    # Auto-adjust providers if unified
    if current.get("unified_model"):
        chosen_provider = current.get("provider", "local")
        current["chat_model"]["provider"] = chosen_provider
        current["work_model"]["provider"] = chosen_provider

    current["updated_at"] = time.time()

    SETTINGS_FILE.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")

    # Set environment variable so child processes inherit key
    if current.get("gemini_api_key"):
        os.environ["GEMINI_API_KEY"] = current["gemini_api_key"]

    return current


def mask_api_key(key: str) -> str:
    """Mask sensitive API key for safe UI display (e.g. AIzaSy...9Xw)."""
    clean = (key or "").strip()
    if not clean:
        return ""
    if len(clean) <= 8:
        return "••••••••"
    return clean[:6] + "••••••••" + clean[-4:]


def test_gemini_api_key(api_key: str, model: str = "gemini-3.5-flash-lite") -> dict[str, Any]:
    """Test Gemini API key validity by making a lightweight REST call to Google."""
    clean_key = (api_key or "").strip()
    if not clean_key:
        return {"ok": False, "error": "API key cannot be empty"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": "Hello, respond with 'OK'."}]}
        ],
        "generationConfig": {
            "maxOutputTokens": 10,
            "temperature": 0.0,
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            reply_text = ""
            if candidates and candidates[0].get("content", {}).get("parts"):
                reply_text = candidates[0]["content"]["parts"][0].get("text", "").strip()
            return {
                "ok": True,
                "latency_ms": elapsed_ms,
                "model": model,
                "sample_reply": reply_text or "OK",
                "message": f"Gemini API key is active and verified ({elapsed_ms}ms latency).",
            }
    except urllib.error.HTTPError as exc:
        err_msg = f"HTTP {exc.code}"
        try:
            body = json.loads(exc.read().decode("utf-8"))
            err_detail = body.get("error", {}).get("message")
            if err_detail:
                err_msg = f"{err_msg}: {err_detail}"
        except Exception:
            pass
        return {"ok": False, "error": err_msg, "code": exc.code}
    except Exception as exc:
        return {"ok": False, "error": f"Connection error: {exc}"}


def call_gemini(
    messages: list[dict[str, str]],
    api_key: str,
    model: str = "gemini-3.5-flash-lite",
    stream_callback: Callable[[str], None] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> str:
    """Execute chat completion using Google Gemini's REST API.
    
    Supports system instructions, multi-turn history, and streaming SSE callbacks.
    Zero external dependencies.
    """
    clean_key = (api_key or "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
    if not clean_key:
        raise ValueError("Gemini API key is required but was not provided.")

    system_instructions = []
    contents = []

    for msg in messages:
        role = str(msg.get("role") or "user").strip().lower()
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            system_instructions.append(content)
        elif role in ("assistant", "model"):
            contents.append({"role": "model", "parts": [{"text": content}]})
        else:
            contents.append({"role": "user", "parts": [{"text": content}]})

    if not contents:
        contents.append({"role": "user", "parts": [{"text": "Hello"}]})

    # Ensure consecutive turns alternate properly for Gemini API requirement
    sanitized_contents = []
    for item in contents:
        if sanitized_contents and sanitized_contents[-1]["role"] == item["role"]:
            # Combine consecutive messages from same role
            sanitized_contents[-1]["parts"][0]["text"] += "\n\n" + item["parts"][0]["text"]
        else:
            sanitized_contents.append(item)

    # First turn must be user
    if sanitized_contents and sanitized_contents[0]["role"] == "model":
        sanitized_contents.insert(0, {"role": "user", "parts": [{"text": "Continue."}]})

    payload: dict[str, Any] = {
        "contents": sanitized_contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
    }
    if system_instructions:
        payload["systemInstruction"] = {
            "parts": [{"text": "\n\n".join(system_instructions)}]
        }

    use_stream = callable(stream_callback)
    if use_stream:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={clean_key}"
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )

    t0 = time.perf_counter()
    if not use_stream:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates and candidates[0].get("content", {}).get("parts"):
                return candidates[0]["content"]["parts"][0].get("text", "")
            return ""

    # Streaming SSE handling
    collected = []
    with urllib.request.urlopen(req, timeout=35) as resp:
        for line in resp:
            decoded = line.decode("utf-8", errors="replace").strip()
            if decoded.startswith("data: "):
                raw_json = decoded[6:].strip()
                if not raw_json or raw_json == "[DONE]":
                    continue
                try:
                    chunk_data = json.loads(raw_json)
                    cands = chunk_data.get("candidates", [])
                    if cands and cands[0].get("content", {}).get("parts"):
                        delta = cands[0]["content"]["parts"][0].get("text", "")
                        if delta:
                            collected.append(delta)
                            try:
                                stream_callback(delta)
                            except Exception:
                                pass
                except Exception:
                    continue

    return "".join(collected)


def ask_ai(
    messages: list[dict[str, str]],
    role: str = "work",
    stream_callback: Callable[[str], None] | None = None,
    model: str | None = None,
) -> str:
    """Unified entrypoint for invoking the user's selected model based on role ('chat' vs 'work').
    
    Automatically routes to Gemini Cloud if configured or Local Ollama as requested.
    """
    settings = get_model_settings()
    role_key = "chat_model" if role == "chat" else "work_model"
    role_config = settings.get(role_key, {})

    # Check if role is enabled
    if not role_config.get("enabled", True):
        msg = f"## AI {role.title()} Disabled\n\nAI {role.title()} capabilities have been disabled in Settings -> Models & AI."
        if callable(stream_callback):
            stream_callback(msg)
        return msg

    target_provider = role_config.get("provider", "local")
    gemini_key = settings.get("gemini_api_key", "").strip()

    # If Gemini is chosen and key is present
    if target_provider == "gemini" and gemini_key:
        gemini_model_id = model or role_config.get("gemini_model", "gemini-3.5-flash-lite")
        try:
            return call_gemini(
                messages,
                api_key=gemini_key,
                model=gemini_model_id,
                stream_callback=stream_callback,
            )
        except Exception as exc:
            # Graceful local fallback if Gemini call fails
            print(f"⚠️ [NOVA MODEL ROUTER] Gemini API call failed: {exc}. Falling back to local model.")

    # Local Ollama model invocation
    local_model_id = model or role_config.get("local_model")
    if not local_model_id:
        local_model_id = "qwen3:1.7b" if role == "chat" else "qwen3:8b"

    try:
        from ollama import chat as ollama_chat
        stream_enabled = callable(stream_callback)
        response = ollama_chat(
            model=local_model_id,
            messages=messages,
            stream=stream_enabled,
            options={"temperature": 0.2},
        )
        if not stream_enabled:
            return getattr(getattr(response, "message", None), "content", "") or ""

        parts = []
        for chunk in response:
            msg = getattr(chunk, "message", None)
            delta = str(getattr(msg, "content", "") or "")
            if delta:
                parts.append(delta)
                if stream_callback:
                    stream_callback(delta)
        return "".join(parts)
    except Exception as exc:
        err = f"QWEN_ERROR: {exc}"
        if callable(stream_callback):
            stream_callback(err)
        return err

import os
import sys
import json
import time
import threading
import subprocess
import re
from urllib.parse import quote_plus, urljoin
from ollama import chat
from playwright.sync_api import sync_playwright

try:
    import website_memory as _website_memory
except Exception as _website_memory_import_error:
    _website_memory = None
    print(f"⚠️ Website memory is unavailable: {_website_memory_import_error}")

try:
    import website_directory as _website_directory
except Exception as _website_directory_import_error:
    _website_directory = None
    print(f"⚠️ Local website directory is unavailable: {_website_directory_import_error}")

# ============================================================
# CONFIGURATION
# ============================================================

def find_brave_path():
    candidates = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    program_files = os.environ.get("PROGRAMFILES")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)")

    if local_app_data:
        candidates.append(os.path.join(
            local_app_data, "BraveSoftware", "Brave-Browser",
            "Application", "brave.exe"
        ))
    if program_files:
        candidates.append(os.path.join(
            program_files, "BraveSoftware", "Brave-Browser",
            "Application", "brave.exe"
        ))
    if program_files_x86:
        candidates.append(os.path.join(
            program_files_x86, "BraveSoftware", "Brave-Browser",
            "Application", "brave.exe"
        ))

    for path in candidates:
        if os.path.isfile(path):
            return path

    return None

BRAVE_PATH = find_brave_path()

PROFILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "BraveAgentProfile",
)

MODEL = "qwen3:8b"

# Keep these modest: the goal is fast planning, not endless reasoning.
MAX_ACTIONS = 10
MAX_REPLANS = 2

PAGE_TEXT_LIMIT = 1600
MAX_LINKS = 24
MAX_BUTTONS = 12
MAX_INPUTS = 8

QWEN_CONTEXT = 2048
QWEN_TOKENS = 80

CLICK_TIMEOUT = 700
TYPE_TIMEOUT = 700
NAV_TIMEOUT = 6000
RENDER_WAIT = 0.05

# Number of previous user/agent turns supplied to Qwen.
CONTEXT_TURNS = 8

# Additive persistence + screen awareness. Existing features stay enabled.
MEMORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_memory.json")
PAGE_TEXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_page_text")
LAST_PAGE_TEXT = os.path.join(PAGE_TEXT_DIR, "latest.txt")
MEMORY_TASK_LIMIT = 30

# Conversational mode: casual messages are handled without opening/observing
# the browser. This keeps NOVA feeling like a real chat assistant.
FAST_GREETING_REPLIES = {
    "hi": "Hi! 👋 What can I do for you?",
    "hello": "Hello! 👋 What can I do for you?",
    "hey": "Hey! 👋 What are we doing?",
    "hii": "Hii! 👋 What can I do for you?",
    "yo": "Yo! 😄 What's up?",
    "thanks": "You're welcome! 😊",
    "thank you": "You're welcome! 😊",
    "thx": "Anytime! 😊",
    "bye": "Bye! 👋",
    "goodbye": "Bye! 👋",
}

# ============================================================
# GLOBAL STATE
# ============================================================

stop_event = threading.Event()
exit_event = threading.Event()

_browser_context = None
_page = None
_playwright = None
_listener = None

CURRENT_COMMAND = ""
CONVERSATION_HISTORY = []

# The active destination persists between conversational commands.
# Examples:
#   open youtube
#   search for mr beast        -> YouTube search
#   open first video           -> current-page video action
#
# Explicit "web/google search" commands override this context.
ACTIVE_SITE = ""


def _load_agent_memory():
    """Load persistent notes without making startup depend on the file."""
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
        data.setdefault("history", [])
        data.setdefault("completed_tasks", [])
        data.setdefault("recipes", [])
        return data
    except (OSError, ValueError, TypeError):
        return {"history": [], "completed_tasks": [], "recipes": []}


AGENT_MEMORY = _load_agent_memory()


def _ensure_runtime_paths():
    """Create NOVA's private runtime folder and empty memory file on first run.

    Existing user data is never replaced. Runtime state should stay local and
    should not be committed to the source repository.
    """
    try:
        os.makedirs(PAGE_TEXT_DIR, exist_ok=True)
    except OSError as e:
        print(f"⚠️ Could not create NOVA page-text folder: {e}")

    if not os.path.exists(MEMORY_PATH):
        # Exclusive creation prevents overwriting a file created by another process.
        try:
            with open(MEMORY_PATH, "x", encoding="utf-8") as f:
                json.dump(
                    {"history": [], "completed_tasks": [], "recipes": []},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except FileExistsError:
            pass
        except OSError as e:
            print(f"⚠️ Could not initialize NOVA memory: {e}")


_ensure_runtime_paths()


def _save_agent_memory():
    """Persist memory atomically so a partial write doesn't corrupt it."""
    temp_path = MEMORY_PATH + ".tmp"
    try:
        os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(AGENT_MEMORY, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, MEMORY_PATH)
    except OSError as e:
        print(f"⚠️ Could not save NOVA memory: {e}")


def _remember_completed_task(command, result, status="done", start_url="", end_url="", actions=None):
    """Keep a durable task log; never treat old actions as already completed now."""
    item = {
        "user": str(command).strip(),
        "result": str(result or "").strip()[:1000],
        "status": str(status),
        "start_url": str(start_url or ""),
        "end_url": str(end_url or ""),
        "actions": actions if isinstance(actions, list) else [],
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    tasks = AGENT_MEMORY.setdefault("completed_tasks", [])
    tasks.append(item)
    AGENT_MEMORY["completed_tasks"] = tasks[-MEMORY_TASK_LIMIT:]
    _save_agent_memory()


def memory_for_qwen():
    """Short persistent memory context for faster, more consistent planning."""
    tasks = AGENT_MEMORY.get("completed_tasks", [])
    if not tasks:
        return "No saved task memories yet."
    lines = []
    for item in tasks[-6:]:
        lines.append(
            f"TASK: {item.get('user', '')} | STATUS: {item.get('status', '')} | "
            f"START: {item.get('start_url', '')} | END: {item.get('end_url', '')} | "
            f"RESULT: {item.get('result', '')[:180]}"
        )
    return "\n".join(lines)


def _save_page_text_snapshot(observation):
    """Save a readable text snapshot of the current page, not an image."""
    if not isinstance(observation, dict) or not observation.get("url"):
        return ""
    try:
        os.makedirs(PAGE_TEXT_DIR, exist_ok=True)
        lines = [
            "NOVA PAGE TEXT SNAPSHOT",
            "=" * 72,
            f"Captured: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Title: {observation.get('title', '')}",
            f"URL: {observation.get('url', '')}",
            "",
            "PAGE TEXT",
            "=" * 72,
            str(observation.get("page_text_full") or observation.get("text") or ""),
            "",
            "VISIBLE LINKS",
            "=" * 72,
        ]
        for i, link in enumerate(observation.get("links", []), 1):
            lines.append(
                f"{i}. {link.get('text', '')} | aria={link.get('aria', '')} | href={link.get('href', '')}"
            )
        lines.extend(["", "VISIBLE BUTTONS", "=" * 72])
        for i, button in enumerate(observation.get("buttons", []), 1):
            lines.append(f"{i}. {button.get('text', '')} | aria={button.get('aria', '')}")
        lines.extend(["", "VISIBLE INPUTS", "=" * 72])
        for i, field in enumerate(observation.get("inputs", []), 1):
            lines.append(
                f"{i}. type={field.get('type', '')} | placeholder={field.get('placeholder', '')} | "
                f"aria={field.get('aria', '')} | name={field.get('name', '')}"
            )
        with open(LAST_PAGE_TEXT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return LAST_PAGE_TEXT
    except Exception as e:
        print(f"⚠️ Could not save page text snapshot: {e}")
        return ""


# ============================================================
# ESC KILL SWITCH
# ============================================================

def esc_listener():
    try:
        import ctypes

        user32 = ctypes.windll.user32
        was_down = False

        while not exit_event.is_set():
            is_down = bool(user32.GetAsyncKeyState(0x1B) & 0x8000)

            if is_down and not was_down:
                if stop_event.is_set():
                    print("\n🛑 ESC pressed again — closing agent...")
                    exit_event.set()
                else:
                    print("\n🛑 ESC pressed — stopping current task...")
                    stop_event.set()

            was_down = is_down
            time.sleep(0.035)

    except Exception:
        pass


# ============================================================
# BRAVE
# ============================================================

def kill_brave():
    """Stop only Brave processes launched with NOVA's dedicated profile.

    Never terminate every brave.exe process: the user may have unrelated
    Brave windows open. If the profile is not in use, this does nothing.
    """
    if os.name != "nt":
        return
    try:
        profile = os.path.normcase(os.path.abspath(PROFILE_PATH))
        ps = (
            "$profile = [System.IO.Path]::GetFullPath('" + profile.replace("'", "''") + "'); "
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -ieq 'brave.exe' -and $_.CommandLine -and "
            "$_.CommandLine.ToLower().Contains($profile.ToLower()) } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        time.sleep(0.30)
    except Exception:
        pass


def start_browser():
    global _browser_context, _page, _playwright, _listener

    # Do not trust a non-None page reference: Brave or its tab may have been
    # closed by the user, or Playwright's context may have crashed.
    if _page is not None and _browser_context is not None and _playwright is not None:
        try:
            pages = _browser_context.pages
            if not _page.is_closed() and any(page == _page for page in pages):
                _ = _page.url
                return True
        except Exception:
            pass
        close_browser()

    try:
        if not BRAVE_PATH or not os.path.isfile(BRAVE_PATH):
            print("❌ Brave executable was not found. Install Brave or correct BRAVE_PATH.")
            _browser_context = None
            _page = None
            _playwright = None
            return False

        os.makedirs(PROFILE_PATH, exist_ok=True)
        kill_brave()
        _playwright = sync_playwright().start()

        _browser_context = _playwright.chromium.launch_persistent_context(
            user_data_dir=PROFILE_PATH,
            headless=False,
            executable_path=BRAVE_PATH,
            viewport={"width": 1400, "height": 900},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-default-apps",
            ],
        )

        if _browser_context.pages:
            _page = _browser_context.pages[0]
        else:
            _page = _browser_context.new_page()

        _page.set_default_timeout(CLICK_TIMEOUT)

        if _listener is None:
            _listener = threading.Thread(
                target=esc_listener,
                daemon=True,
            )
            _listener.start()

        print("✅ Brave started.")
        return True

    except Exception as e:
        print(f"❌ Could not start Brave:\\n{e}")
        try:
            if _browser_context is not None:
                _browser_context.close()
        except Exception:
            pass
        try:
            if _playwright is not None:
                _playwright.stop()
        except Exception:
            pass
        _browser_context = None
        _page = None
        _playwright = None
        return False


def close_browser():
    global _browser_context, _page, _playwright

    try:
        if _browser_context:
            _browser_context.close()
    except Exception:
        pass

    try:
        if _playwright:
            _playwright.stop()
    except Exception:
        pass

    _browser_context = None
    _page = None
    _playwright = None


def _browser_is_usable():
    """Return whether the current Playwright page/context can still be used."""
    if _page is None or _browser_context is None or _playwright is None:
        return False
    try:
        pages = _browser_context.pages
        # is_closed() alone can miss a stale page after Chromium exits.
        if _page.is_closed() or not any(page == _page for page in pages):
            return False
        _ = _page.url
        return True
    except Exception:
        return False


def _ensure_browser_ready():
    """Reopen NOVA's Brave window when its page/context was closed."""
    if _browser_is_usable():
        return True, ""

    print("⚠️ Brave page/context is no longer usable. Rebuilding the session…")
    close_browser()
    started = start_browser()
    if started and _browser_is_usable():
        print("✅ Brave session recovered; continuing the task.")
        return True, ""

    message = (
        "Browser recovery failed: NOVA could not create a live Brave page. "
        "Check the Brave installation, backend console, and whether "
        "BraveAgentProfile is locked by another process."
    )
    print("❌ " + message)
    return False, message


def _is_closed_browser_error(error):
    message = str(error).lower()
    return any(term in message for term in (
        "target page, context or browser has been closed",
        "browser has been closed",
        "context has been closed",
        "page has been closed",
        "target closed",
        "browser.new_page: target page, context or browser has been closed",
    ))


def tiny_wait():
    time.sleep(RENDER_WAIT)


# ============================================================
# QWEN
# ============================================================

def ask_qwen(messages):
    try:
        response = chat(
            model=MODEL,
            messages=messages,
            think=False,
            keep_alive="20m",
            options={
                "num_predict": QWEN_TOKENS,
                "num_ctx": QWEN_CONTEXT,
                "temperature": 0,
            },
        )
        return response.message.content
    except Exception as e:
        return "QWEN_ERROR: " + str(e)


def extract_json(text):
    if not text:
        return None

    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        return None

    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


# ============================================================
# CONVERSATION CONTEXT
# ============================================================

def add_history(user_command, result=None):
    item = {
        "user": str(user_command).strip(),
        "result": str(result or "").strip(),
    }

    CONVERSATION_HISTORY.append(item)

    if len(CONVERSATION_HISTORY) > CONTEXT_TURNS:
        del CONVERSATION_HISTORY[:-CONTEXT_TURNS]

    # Keep a small persistent conversational memo across restarts.
    persistent = AGENT_MEMORY.setdefault("history", [])
    persistent.append(item)
    AGENT_MEMORY["history"] = persistent[-CONTEXT_TURNS:]
    _save_agent_memory()


def history_for_qwen():
    lines = []

    if not CONVERSATION_HISTORY:
        lines.append("No previous conversation in this session.")

    for item in CONVERSATION_HISTORY:
        lines.append("USER: " + item["user"])

        if item["result"]:
            lines.append("AGENT RESULT: " + item["result"][:500])

    persistent_history = AGENT_MEMORY.get("history", [])
    if persistent_history:
        lines.append("PERSISTENT RECENT HISTORY:")
        for item in persistent_history[-4:]:
            lines.append("USER: " + str(item.get("user", "")))
            if item.get("result"):
                lines.append("AGENT RESULT: " + str(item.get("result", ""))[:250])

    return "\n".join(lines)


# ============================================================
# CONVERSATIONAL MODE
# ============================================================

def normalize_chat_text(text):
    return re.sub(r"\s+", " ", str(text).strip().lower())


def is_explicit_task_command(text):
    """Conservative check: explicit action requests stay in task mode."""
    lower = normalize_chat_text(text)

    task_prefixes = (
        "open ", "go to ", "visit ", "navigate to ",
        "search ", "find ", "look up ", "browse ",
        "click ", "press ", "type ", "scroll ",
        "read ", "watch ", "play ", "download ",
        "go back", "go forward", "refresh ",
    )

    if lower.startswith(task_prefixes):
        return True

    if re.search(
        r"\b(open|launch|start)\s+(youtube|yt|google|instagram|reddit|"
        r"facebook|twitter|x|github|minecraft)\b",
        lower,
    ):
        return True

    return False


def fast_conversation_reply(command):
    """
    Return (handled, reply).

    Greetings use local canned replies with zero model latency.
    Normal conversation uses Qwen directly, without browser startup,
    page observation, or action planning.
    """
    clean = normalize_chat_text(command)

    if not clean:
        return False, ""

    if clean in FAST_GREETING_REPLIES:
        return True, FAST_GREETING_REPLIES[clean]

    if not is_explicit_task_command(command):
        history = history_for_qwen()
        prompt = f"""
You are NOVA, a local conversational AI assistant.
Answer the user's message naturally and concisely.
This is a conversation, NOT a browser task.
Do not output JSON.
Do not claim to have performed an action.

RECENT CONVERSATION:
{history}

USER:
{command}
"""
        raw = ask_qwen([
            {
                "role": "system",
                "content": (
                    "You are NOVA's chat mode. "
                    "Be friendly, natural, and concise. "
                    "Never output tool JSON in this mode."
                ),
            },
            {"role": "user", "content": prompt},
        ])

        if raw.startswith("QWEN_ERROR:"):
            return True, "I'm having trouble reaching my local model right now."

        return True, raw.strip()

    return False, ""


def handle_conversation(command):
    handled, reply = fast_conversation_reply(command)

    if not handled:
        return False, ""

    print()
    print("💬 NOVA")
    print(reply)
    print()
    add_history(command, reply)
    return True, reply


# ============================================================
# WEBSITE MEMORY HELPERS
# ============================================================

def _website_memory_scope():
    """Return the current host/path scope without query strings or fragments."""
    if _page is None:
        return "", "/"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(_page.url)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/") or "/"
        return host, path
    except Exception:
        return "", "/"


def _refresh_page_map_if_navigated(previous_url):
    """Immediately learn a newly reached page after a navigation action."""
    try:
        if _page is not None and _page.url and _page.url != str(previous_url or ""):
            observe_page()
    except Exception:
        pass


def _persist_page_profile(observation):
    """Persist page identity and useful interface metadata, never page body text."""
    if _website_memory is None or not isinstance(observation, dict):
        return
    url = str(observation.get("url") or "")
    if not url.startswith(("http://", "https://")):
        return
    try:
        from urllib.parse import urlsplit, urlunsplit
        import hashlib
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/") or "/"
        title = str(observation.get("title") or "")[:240]
        links = observation.get("links") if isinstance(observation.get("links"), list) else []
        buttons = observation.get("buttons") if isinstance(observation.get("buttons"), list) else []
        inputs = observation.get("inputs") if isinstance(observation.get("inputs"), list) else []
        forms = observation.get("forms") if isinstance(observation.get("forms"), list) else []
        # Persist link destinations without query strings/fragments; these can contain
        # tracking identifiers or user-specific tokens. The live DOM still retains them.
        safe_links = []
        for item in links[:60]:
            if not isinstance(item, dict):
                continue
            link = dict(item)
            href = str(link.get("href") or "")
            if href:
                try:
                    from urllib.parse import urljoin, urlunsplit
                    parsed_href = urlsplit(urljoin(url, href))
                    if parsed_href.scheme in ("http", "https"):
                        link["href"] = urlunsplit((parsed_href.scheme, parsed_href.netloc, parsed_href.path, "", ""))
                except Exception:
                    pass
            safe_links.append(link)
        controls = {"links": safe_links, "buttons": buttons[:40], "inputs": inputs[:30], "forms": forms[:20]}
        signature = json.dumps({
            "title": title,
            "links": [(x.get("text", ""), x.get("href", "")) for x in links[:30] if isinstance(x, dict)],
            "buttons": [(x.get("text", ""), x.get("aria", ""), x.get("title", "")) for x in buttons[:20] if isinstance(x, dict)],
            "inputs": [(x.get("type", ""), x.get("placeholder", ""), x.get("aria", ""), x.get("name", "")) for x in inputs[:15] if isinstance(x, dict)]
        }, ensure_ascii=False, sort_keys=True)
        fingerprint = hashlib.sha256(signature.encode("utf-8", "ignore")).hexdigest()[:24]
        low = (title + " " + path).lower()
        if "wikipedia.org" in host and path == "/":
            purpose = "Wikipedia language selection"
        elif any(word in low for word in ("search", "results")):
            purpose = "search or results page"
        elif any(word in low for word in ("login", "signin", "sign-in")):
            purpose = "sign-in page"
        else:
            purpose = ("page titled " + title) if title else "web page"
        normalized_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", "", ""))
        _website_memory.save_page_profile(host, path, title, normalized_url, purpose, fingerprint, controls)
        profiles = _website_memory.get_page_profiles(host, path, limit=1)
        if profiles and profiles[0].get("fingerprint") == fingerprint:
            print(f"🧠 Page map saved: {host}{path} · {len(links)} links · {len(buttons)} buttons · {len(inputs)} inputs")
    except Exception as error:
        print(f"⚠️ Could not save page map: {error}")


def _semantic_click_visible_target(target):
    """Find a high-confidence semantic match, e.g. 'English Wikipedia' -> 'English'."""
    if _page is None or not target:
        return False, "No page or target."
    try:
        match = _page.evaluate(r"""
        (target) => {
          const clean = v => (v || "").replace(/\s+/g, " ").trim();
          const norm = v => clean(v).toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
          const visible = el => { const r=el.getBoundingClientRect(), s=getComputedStyle(el); return r.width>0 && r.height>0 && s.display!=="none" && s.visibility!=="hidden"; };
          const raw = norm(target);
          const ignored = new Set(["open","go","to","visit","click","tap","press","on","the","a","an","page","website","site","please","wikipedia","edition","button","link","tab","option","menu","item","control","icon","language"]);
          const tokens = raw.split(/\s+/).filter(t => t && !ignored.has(t));
          const candidates = [...document.querySelectorAll('a[href],button,[role="button"],[role="link"],[role="menuitem"],[role="tab"]')].filter(visible);
          const scored = candidates.map(el => {
            const label = clean(el.innerText || el.getAttribute("aria-label") || el.getAttribute("title") || el.getAttribute("alt"));
            const aria = clean(el.getAttribute("aria-label"));
            const title = clean(el.getAttribute("title"));
            const href = clean(el.getAttribute("href") || el.href || "");
            const context = norm([label, aria, title, href].join(" "));
            const nl = norm(label || aria || title);
            let score = 0;
            if (nl === raw) score = 1.0;
            else if (nl && raw && (nl.includes(raw) || raw.includes(nl))) score = 0.88;
            const matched = tokens.filter(t => context.includes(t)).length;
            if (tokens.length) score = Math.max(score, (matched / tokens.length) * 0.78);
            if (tokens.includes("english") && /(^|\\.)en\\.wikipedia\\.org/i.test(href)) score = Math.max(score, 0.98);
            if (tokens.includes("english") && /(^|\/)wiki\//i.test(href) && /english/i.test(label)) score = Math.max(score, 0.92);
            return {el, label, href, score, role: el.getAttribute("role") || (el.tagName === "A" ? "link" : "button")};
          }).sort((a,b) => b.score-a.score);
          if (!scored.length || scored[0].score < 0.70) return null;
          if (scored[1] && scored[0].score - scored[1].score < 0.08 && scored[0].label !== scored[1].label) return null;
          const best = scored[0];
          return {label: best.label, href: best.href, role: best.role, score: best.score};
        }
        """, str(target))
        if not match:
            return False, "No confident semantic match found."
        href = str(match.get("href") or "")
        label = str(match.get("label") or "")
        role = str(match.get("role") or "")
        locator = None
        if role and label:
            try:
                candidate = _page.get_by_role(role, name=label, exact=True)
                if candidate.count() == 1:
                    locator = candidate
            except Exception:
                pass
        if locator is None and href:
            try:
                candidate = _page.locator("a").filter(has=_page.locator(f'a[href="{href}"]'))
                if candidate.count() == 1:
                    locator = candidate
            except Exception:
                pass
        if locator is None:
            return False, "Semantic match could not be converted to a unique Playwright locator."
        previous_url = _page.url
        locator.click(timeout=CLICK_TIMEOUT)
        tiny_wait()
        _refresh_page_map_if_navigated(previous_url)
        if label:
            actual_descriptor = _describe_target_locator("CLICK_TEXT", label)
            _remember_website_locator("CLICK_TEXT", target, actual_descriptor, _website_memory_scope())
        print(f"🧭 Semantic match: '{target}' → '{label}' (confidence {match.get('score', 0):.2f})")
        return True, f"Clicked {label or target} using semantic match."
    except Exception as error:
        return False, f"Semantic matching failed: {error}"


def search_current_page(query):
    """Search the current site using its live search field/form, including icon-only submit buttons."""
    if _page is None:
        return False, "Browser unavailable."
    query = str(query or "").strip()
    if not query:
        return False, "Empty search query."
    try:
        before_url = _page.url
        before_text = _page.locator("body").inner_text(timeout=1000)[:1200]
    except Exception:
        before_url, before_text = "", ""

    # Reuse a previously validated search-field locator first, but only after
    # checking uniqueness and visibility on the current page.
    if _website_memory is not None:
        host, path = _website_memory_scope()
        try:
            records = _website_memory.get_locators(host, path, "TYPE_TEXT", "search") if host else []
        except Exception:
            records = []
        for record in records:
            try:
                remembered_field = _locator_from_memory(record)
                if remembered_field is None or remembered_field.count() != 1 or not remembered_field.is_visible():
                    _website_memory.record_locator_result(record["id"], False)
                    continue
                remembered_field.fill(query, timeout=TYPE_TIMEOUT)
                try:
                    remembered_field.press("Enter", timeout=TYPE_TIMEOUT)
                except Exception:
                    pass
                tiny_wait()
                try:
                    changed = _page.url != before_url or _page.locator("body").inner_text(timeout=1000)[:1200] != before_text
                except Exception:
                    changed = _page.url != before_url
                if changed:
                    _website_memory.record_locator_result(record["id"], True)
                    print(f"🧠 Website memory hit: {host} · search field")
                    return True, f"Searched current website for: {query}"
                _website_memory.record_locator_result(record["id"], False)
            except Exception:
                try:
                    _website_memory.record_locator_result(record["id"], False)
                except Exception:
                    pass

    try:
        spec = _page.evaluate(r"""
        () => {
          const clean = v => (v || "").replace(/\s+/g," ").trim();
          const visible = el => { const r=el.getBoundingClientRect(),s=getComputedStyle(el); return r.width>0&&r.height>0&&s.display!=="none"&&s.visibility!=="hidden"&&!el.disabled; };
          const all = [...document.querySelectorAll('input,textarea,[contenteditable="true"]')];
          const candidates = all.map((el,index) => {
            if (!visible(el)) return null;
            const type = (el.getAttribute("type")||"").toLowerCase();
            const hint = clean([el.getAttribute("placeholder"),el.getAttribute("aria-label"),el.getAttribute("name"),el.getAttribute("title"),el.labels?[...el.labels].map(x=>x.innerText).join(" "):""].join(" ")).toLowerCase();
            let score = type === "search" ? 1.0 : 0;
            if (/search|query|keyword|find/.test(hint)) score = Math.max(score,0.92);
            if (el.form && el.form.querySelector('button[type="submit"],input[type="submit"]')) score = Math.max(score,0.72);
            if (type === "text" && el.form) score = Math.max(score,0.45);
            return {index,score,type,placeholder:el.getAttribute("placeholder")||"",aria:el.getAttribute("aria-label")||"",name:el.getAttribute("name")||"",id:el.id||"",formIndex:el.form?[...document.forms].indexOf(el.form):-1};
          }).filter(Boolean).sort((a,b)=>b.score-a.score);
          return candidates.length && candidates[0].score >= 0.45 ? candidates[0] : null;
        }
        """)
        if not spec:
            return False, "No likely search field found on the current page."
        all_inputs = _page.locator('input,textarea,[contenteditable="true"]')
        field = all_inputs.nth(int(spec["index"]))
        if field.count() != 1 or not field.is_visible():
            return False, "Search field changed during inspection."
        scope_before = _website_memory_scope()
        descriptor = _describe_target_locator("TYPE_TEXT", "search")
        field.fill(query, timeout=TYPE_TIMEOUT)
        # Enter is the least brittle method and works with most HTML search forms.
        try:
            field.press("Enter", timeout=TYPE_TIMEOUT)
        except Exception:
            pass
        tiny_wait()
        try:
            changed = _page.url != before_url or _page.locator("body").inner_text(timeout=1000)[:1200] != before_text
        except Exception:
            changed = _page.url != before_url
        if changed:
            _remember_website_locator("TYPE_TEXT", "search", descriptor, scope_before)
            print(f"🔎 Current-site search submitted with Enter: {query}")
            return True, f"Searched current website for: {query}"
        # If Enter did not submit, try a submit/icon button associated with that input's form.
        try:
            form = field.locator("xpath=ancestor::form[1]")
            if form.count() == 1:
                submit = form.locator('button[type="submit"],input[type="submit"],[aria-label*="search" i],[title*="search" i],button:has(svg)')
                visible = [submit.nth(i) for i in range(min(submit.count(), 8)) if submit.nth(i).is_visible()]
                if visible:
                    visible[0].click(timeout=CLICK_TIMEOUT)
                    tiny_wait()
                    _remember_website_locator("TYPE_TEXT", "search", descriptor, scope_before)
                    print(f"🔎 Current-site search submitted with form control: {query}")
                    return True, f"Searched current website for: {query}"
        except Exception:
            pass
        # Do not report success if no meaningful page transition was observed.
        return False, "Search was entered, but submission could not be verified."
    except Exception as error:
        return False, f"Current-site search failed: {error}"


def _describe_target_locator(action, target):
    """Describe a stable locator for the intended visible control, if possible."""
    if _page is None:
        return None
    try:
        return _page.evaluate(r"""
            ({action, target}) => {
                const clean = value => (value || "").replace(/\s+/g, " ").trim();
                const visible = el => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.display !== "none" &&
                           s.visibility !== "hidden" && s.pointerEvents !== "none";
                };
                const norm = value => clean(value).toLocaleLowerCase();
                const label = el => clean(el.getAttribute("aria-label") || el.innerText ||
                                          el.getAttribute("title") || el.getAttribute("alt"));
                let el = null;
                if (action === "CLICK_HREF") {
                    el = [...document.querySelectorAll("a[href]")].find(a => {
                        const raw = a.getAttribute("href") || "";
                        return visible(a) && (raw === target || a.href === target);
                    });
                } else if (action === "CLICK_TEXT") {
                    const candidates = [...document.querySelectorAll('a,button,[role="button"],[role="link"]')].filter(visible);
                    const wanted = norm(target);
                    el = candidates.find(a => norm(label(a)) === wanted) ||
                         candidates.find(a => norm(label(a)).includes(wanted));
                    if (!el) {
                        el = [...document.querySelectorAll("body *")].find(node => {
                            if (!visible(node) || node.children.length > 0) return false;
                            return norm(label(node) || node.textContent) === wanted;
                        });
                    }
                } else if (action === "TYPE_TEXT") {
                    const candidates = [...document.querySelectorAll('input,textarea,select,[contenteditable="true"]')].filter(visible);
                    const wanted = norm(target);
                    el = candidates.find(node => {
                        if (!wanted) return false;
                        const values = [node.getAttribute("placeholder"), node.getAttribute("aria-label"),
                                        node.getAttribute("name"), node.getAttribute("title"), node.getAttribute("type"),
                                        node.labels ? [...node.labels].map(x => x.innerText).join(" ") : ""];
                        return values.some(value => norm(value) === wanted || norm(value).includes(wanted));
                    });
                }
                if (!el) return null;
                const attrs = ["data-testid", "data-test", "data-qa"];
                for (const attr of attrs) {
                    const value = el.getAttribute(attr);
                    if (value && document.querySelectorAll(`[${attr}="${CSS.escape(value)}"]`).length === 1)
                        return {type: "testid", value};
                }
                const id = el.getAttribute("id");
                if (id && document.querySelectorAll(`[id="${CSS.escape(id)}"]`).length === 1)
                    return {type: "id", value: id};
                if (action === "TYPE_TEXT") {
                    const placeholder = el.getAttribute("placeholder");
                    if (placeholder && [...document.querySelectorAll("input,textarea")].filter(x => visible(x) && x.getAttribute("placeholder") === placeholder).length === 1)
                        return {type: "placeholder", value: placeholder};
                    const name = el.getAttribute("name");
                    if (name && document.querySelectorAll(`[name="${CSS.escape(name)}"]`).length === 1)
                        return {type: "name", value: name};
                    const inputType = el.getAttribute("type");
                    if (inputType && [...document.querySelectorAll("input")].filter(x => visible(x) && x.getAttribute("type") === inputType).length === 1)
                        return {type: "input_type", value: inputType};
                }
                if (action === "CLICK_HREF") {
                    const href = el.getAttribute("href");
                    if (href) return {type: "href", value: href};
                }
                const role = el.getAttribute("role") ||
                    (el.tagName === "A" ? "link" : el.tagName === "BUTTON" ? "button" :
                     /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) ? (el.type === "search" ? "searchbox" : "textbox") : "");
                const name = label(el) || (el.labels ? clean([...el.labels].map(x => x.innerText).join(" ")) : "");
                if (role && name) return {type: "role", value: JSON.stringify({role, name})};
                if (action === "TYPE_TEXT" && el.getAttribute("aria-label"))
                    return {type: "aria", value: el.getAttribute("aria-label")};
                return null;
            }
        """, {"action": str(action).upper(), "target": str(target or "")})
    except Exception:
        return None


def _locator_from_memory(record):
    """Convert a stored descriptor to a Playwright locator."""
    kind = record.get("locator_type")
    value = record.get("locator_value", "")
    if kind == "testid":
        return _page.get_by_test_id(value)
    if kind == "id":
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return _page.locator(f'[id="{escaped}"]')
    if kind == "placeholder":
        return _page.get_by_placeholder(value, exact=True)
    if kind == "name":
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return _page.locator(f'[name="{escaped}"]')
    if kind == "input_type":
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return _page.locator(f'input[type="{escaped}"]:visible')
    if kind == "href":
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return _page.locator(f'a[href="{escaped}"]')
    if kind == "aria":
        return _page.get_by_label(value, exact=True)
    if kind == "role":
        spec = json.loads(value)
        return _page.get_by_role(spec["role"], name=spec["name"], exact=True)
    return None


def _try_website_memory(action, target, text_to_fill=None):
    """Try verified stored locators first. Any memory error falls back safely."""
    if _website_memory is None or _page is None or not target:
        return None
    host, path = _website_memory_scope()
    if not host:
        return None
    try:
        records = _website_memory.get_locators(host, path, action, target)
    except Exception:
        return None
    for record in records:
        try:
            locator = _locator_from_memory(record)
            if locator is None or locator.count() != 1 or not locator.is_visible():
                _website_memory.record_locator_result(record["id"], False)
                continue
            if action in {"CLICK_TEXT", "CLICK_HREF"}:
                previous_url = _page.url
                locator.click(timeout=CLICK_TIMEOUT)
                tiny_wait()
                _refresh_page_map_if_navigated(previous_url)
                _website_memory.record_locator_result(record["id"], True)
                print(f"🧠 Website memory hit: {host} · {action} · {target}")
                return True, f"Clicked saved target: {target}"
            if action == "TYPE_TEXT":
                locator.fill(str(text_to_fill or ""), timeout=TYPE_TIMEOUT)
                _website_memory.record_locator_result(record["id"], True)
                print(f"🧠 Website memory hit: {host} · input · {target}")
                return True, f"Typed into saved target: {target}"
        except Exception:
            try:
                _website_memory.record_locator_result(record["id"], False)
            except Exception:
                pass
    return None


def _remember_website_locator(action, target, descriptor, scope=None):
    if _website_memory is None or not descriptor or not target:
        return
    try:
        host, path = scope or _website_memory_scope()
        if host:
            _website_memory.save_locator(
                host, path, action, target,
                descriptor.get("type", ""), descriptor.get("value", "")
            )
    except Exception as error:
        print(f"⚠️ Could not save website locator: {error}")


def _load_safe_task_recipe(command):
    """Load a learned low-risk navigation workflow for this exact command and start URL."""
    if _website_memory is None:
        return None
    try:
        recipe = _website_memory.get_workflow(command, page_identity())
        if not recipe:
            return None
        print("🧠 Saved website workflow found — validating steps before replay.")
        return recipe + [{"action": "DONE", "args": {}}]
    except Exception as error:
        print(f"⚠️ Could not load website workflow: {error}")
        return None


def _maybe_save_safe_task_recipe(command, actions, start_url=None, end_url=None):
    """Persist only verified, low-risk navigation/observation workflows."""
    if _website_memory is None:
        return
    try:
        saved = _website_memory.save_workflow(command, start_url or "", end_url or page_identity(), actions or [])
        if saved:
            print("🧠 Saved verified website workflow for future reuse.")
    except Exception as error:
        print(f"⚠️ Could not save website workflow: {error}")


# ============================================================
# PAGE OBSERVATION
# ============================================================

def observe_page():
    global _page

    result = {
        "url": "",
        "title": "",
        "text": "",
        "links": [],
        "buttons": [],
        "inputs": [],
        "forms": [],
        "page_text_full": "",
        "page_text_file": "",
    }

    if _page is None:
        return result

    try:
        result["url"] = _page.url
    except Exception:
        pass

    try:
        result["title"] = _page.title()
    except Exception:
        pass

    try:
        data = _page.evaluate(
            """
            () => {
                const visible = el => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 &&
                           s.visibility !== "hidden" &&
                           s.display !== "none";
                };

                const clean = v => (v || "")
                    .replace(/\\s+/g, " ")
                    .trim();

                const links = [];
                const buttons = [];
                const inputs = [];
                const forms = [];

                for (const el of document.querySelectorAll("a")) {
                    if (!visible(el)) continue;

                    const text = clean(
                        el.innerText ||
                        el.getAttribute("aria-label") ||
                        el.getAttribute("title")
                    );

                    const href = el.getAttribute("href") || "";

                    if (!text && !href) continue;

                    links.push({
                        text: text.slice(0, 120),
                        aria: clean(
                            el.getAttribute("aria-label")
                        ).slice(0, 120),
                        href: href.slice(0, 220)
                    });
                }

                for (const el of document.querySelectorAll(
                    'button,[role="button"]'
                )) {
                    if (!visible(el)) continue;

                    const text = clean(
                        el.innerText || el.getAttribute("aria-label") ||
                        el.getAttribute("title") || el.getAttribute("alt")
                    );
                    const svg = !!el.querySelector("svg");
                    const type = clean(el.getAttribute("type"));
                    // Keep icon-only controls too; their surrounding form and accessibility metadata matter.
                    buttons.push({
                        text: text.slice(0, 120),
                        aria: clean(el.getAttribute("aria-label")).slice(0, 120),
                        title: clean(el.getAttribute("title")).slice(0, 120),
                        type: type.slice(0, 40),
                        has_icon: svg,
                        form_action: el.form ? clean(el.form.getAttribute("action")).slice(0, 220) : ""
                    });
                }

                for (const el of document.querySelectorAll(
                    'input,textarea,select,[contenteditable="true"]'
                )) {
                    if (!visible(el)) continue;

                    inputs.push({
                        type: (el.getAttribute("type") || el.tagName.toLowerCase()),
                        placeholder: clean(el.getAttribute("placeholder")).slice(0, 100),
                        aria: clean(el.getAttribute("aria-label")).slice(0, 100),
                        title: clean(el.getAttribute("title")).slice(0, 100),
                        name: clean(el.getAttribute("name")).slice(0, 80),
                        id: clean(el.getAttribute("id")).slice(0, 80),
                        associated_label: el.labels ? clean([...el.labels].map(x => x.innerText).join(" ")).slice(0, 120) : "",
                        form_action: el.form ? clean(el.form.getAttribute("action")).slice(0, 220) : ""
                    });
                }

                for (const form of document.querySelectorAll("form")) {
                    if (!visible(form)) continue;
                    forms.push({
                        action: clean(form.getAttribute("action")).slice(0, 220),
                        method: clean(form.getAttribute("method") || "get").toLowerCase(),
                        role: clean(form.getAttribute("role")),
                        input_count: form.querySelectorAll('input,textarea,select,[contenteditable="true"]').length,
                        submit_count: form.querySelectorAll('button[type="submit"],input[type="submit"],button:not([type])').length
                    });
                }

                const fullText = (document.body && document.body.innerText) || "";

                return {
                    text: clean(fullText).slice(0, 1800),
                    page_text_full: fullText.slice(0, 100000),
                    links: links.slice(0, 60),
                    buttons: buttons.slice(0, 40),
                    inputs: inputs.slice(0, 30),
                    forms: forms.slice(0, 20)
                };
            }
            """
        )

        if isinstance(data, dict):
            result.update(data)

    except Exception:
        pass

    # Save a compact structured page map separately from the optional text snapshot.
    _persist_page_profile(result)

    # Save a text file snapshot of the page content and visible controls.
    # Keep the shorter `text` field for fast model prompts, while the .txt
    # snapshot contains a much larger page-text extract.
    result["page_text_file"] = _save_page_text_snapshot(result)
    result["page_text_full"] = ""  # Avoid carrying the large copy through every planner call.
    return result


def page_identity():
    if _page is None:
        return ""

    try:
        return _page.url
    except Exception:
        return ""


# ============================================================
# DESTINATION / SITE CONTEXT
# ============================================================

SITE_ALIASES = {
    "youtube": "youtube",
    "yt": "youtube",
    "you tube": "youtube",
    "google": "google",
    "reddit": "reddit",
    "instagram": "instagram",
    "insta": "instagram",
    "facebook": "facebook",
    "fb": "facebook",
    "github": "github",
    "twitter": "x",
    "x": "x",
    "wikipedia": "wikipedia",
}

SITE_URLS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "reddit": "https://www.reddit.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "github": "https://github.com",
    "x": "https://x.com",
    "wikipedia": "https://www.wikipedia.org",
}

def normalize_site_name(name):
    value = re.sub(r"\s+", " ", str(name).strip().lower())
    value = value.replace(".com", "")
    return SITE_ALIASES.get(value, value)

def site_from_url(url):
    global ACTIVE_SITE
    try:
        from urllib.parse import urlparse
        host = urlparse(str(url)).hostname or ""
        host = host.lower().removeprefix("www.")

        if "youtube." in host:
            return "youtube"
        if host.endswith("google.com") or host == "google.com":
            return "google"
        if "reddit." in host:
            return "reddit"
        if "instagram." in host:
            return "instagram"
        if "facebook." in host:
            return "facebook"
        if "github." in host:
            return "github"
        if host == "x.com" or "twitter." in host:
            return "x"
        if "wikipedia." in host:
            return "wikipedia"

        return host
    except Exception:
        return ""

def update_active_site(url):
    global ACTIVE_SITE
    detected = site_from_url(url)
    if detected:
        ACTIVE_SITE = detected

def current_site():
    if ACTIVE_SITE:
        return ACTIVE_SITE

    if _page is not None:
        try:
            return site_from_url(_page.url)
        except Exception:
            pass

    return ""

def resolve_destination_with_qwen(destination):
    """
    Qwen-only destination resolver.

    IMPORTANT:
    - No Google search.
    - No web search.
    - No guessed browser navigation by Python.
    - Qwen must return a URL it actually knows.
    - If it does not know, it must return null.
    """
    destination = str(destination).strip()
    if not destination:
        return None

    prompt = f"""
You are NOVA's local website URL resolver.

The user wants to OPEN this destination:
{destination}

Use your own learned knowledge only.
Do NOT suggest Google search.
Do NOT suggest web search.
Do NOT invent a fake domain.

Return ONLY valid JSON in exactly this shape:
{{"url":"https://example.com"}}

If you genuinely do not know the official website URL, return:
{{"url":null}}

Prefer the official homepage.
"""
    raw = ask_qwen([
        {
            "role": "system",
            "content": (
                "Resolve website destinations from your internal knowledge. "
                "Never browse and never invent a domain. Return JSON only."
            ),
        },
        {"role": "user", "content": prompt},
    ])

    data = extract_json(raw)
    if not isinstance(data, dict):
        return None

    url = data.get("url")
    if not url or not isinstance(url, str):
        return None

    url = url.strip()
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        return None

    return url

def explicit_web_search_query(text):
    lower = text.strip().lower()
    prefixes = (
        "search google for ",
        "search google ",
        "google ",
        "google search for ",
        "search the web for ",
        "search the web ",
        "search web for ",
        "search web ",
        "do a web search for ",
        "do a web search ",
        "web search for ",
        "web search ",
    )
    for prefix in prefixes:
        if lower.startswith(prefix):
            return text[len(prefix):].strip()
    return None

def explicit_youtube_search_query(text):
    lower = text.strip().lower()
    prefixes = (
        "search youtube for ",
        "search youtube ",
        "youtube search for ",
        "youtube search ",
        "find this on youtube ",
        "find on youtube ",
    )
    for prefix in prefixes:
        if lower.startswith(prefix):
            return text[len(prefix):].strip()
    return None

def generic_search_query(text):
    lower = text.strip().lower()
    for prefix in ("search for ", "search ", "find "):
        if lower.startswith(prefix):
            query = text[len(prefix):].strip()
            if query:
                return query
    return None


# ============================================================
# GENERIC BROWSER SEARCH
# ============================================================

def search_web(query):
    query = str(query).strip()

    if not query:
        return False, "Empty search."

    url = (
        "https://www.google.com/search?q="
        + quote_plus(query)
    )

    return open_url(url)


def search_youtube(query):
    query = str(query).strip()

    if not query:
        return False, "Empty YouTube search."

    url = (
        "https://www.youtube.com/results?search_query="
        + quote_plus(query)
    )

    return open_url(url)


# ============================================================
# FIRST ORGANIC SEARCH RESULT
# ============================================================

def open_first_organic_result():
    """Open Google's first organic result, not Google's own UI links.

    Google search pages contain many links (Google apps, Images, Maps,
    Shopping, account controls, etc.) before/around the actual results.
    The reliable marker for an ordinary web result is a result title inside
    an <h3> within the #search results area.
    """
    global _page

    if _page is None:
        return False, "Browser unavailable."

    try:
        candidate = _page.evaluate(r"""
        () => {
            const clean = s => (s || "").replace(/\s+/g, " ").trim();

            const unwrapGoogleUrl = href => {
                if (!href) return "";
                try {
                    const u = new URL(href, location.href);
                    const host = u.hostname.toLowerCase();

                    // Google may wrap an external result as /url?q=... or
                    // /url?url=... . Extract the real destination first.
                    if (host === "www.google.com" || host === "google.com") {
                        const q = u.searchParams.get("q") ||
                                  u.searchParams.get("url") ||
                                  u.searchParams.get("u");
                        if (q && /^https?:\/\//i.test(q)) return q;
                    }
                    return u.href;
                } catch (_) {
                    return "";
                }
            };

            const isExternalHttp = href => {
                try {
                    const u = new URL(href, location.href);
                    if (!/^https?:$/i.test(u.protocol)) return false;
                    const host = u.hostname.toLowerCase();
                    if (
                        host === "google.com" ||
                        host.endsWith(".google.com") ||
                        host === "google.co.uk" ||
                        host.endsWith(".google.co.uk") ||
                        host === "gstatic.com" ||
                        host.endsWith(".gstatic.com") ||
                        host.endsWith("googleusercontent.com")
                    ) return false;
                    return true;
                } catch (_) {
                    return false;
                }
            };

            const sponsored = el => {
                let node = el;
                for (let i = 0; node && i < 8; i++, node = node.parentElement) {
                    const id = clean(node.id).toLowerCase();
                    const cls = clean(typeof node.className === "string" ? node.className : "").toLowerCase();
                    const aria = clean(node.getAttribute("aria-label")).toLowerCase();
                    const txt = clean(node.innerText).toLowerCase().slice(0, 350);

                    if (
                        id === "tads" || id.includes("tads") ||
                        id.includes("commercial") ||
                        cls.includes("sponsored") || cls.includes("advert") ||
                        cls.includes("adcontainer") ||
                        aria.includes("sponsored") || aria === "ad" ||
                        aria.includes("advertisement") ||
                        txt.startsWith("sponsored") ||
                        txt.startsWith("ad ·") ||
                        txt.startsWith("ad ")
                    ) return true;
                }
                return false;
            };

            const visible = el => {
                const r = el.getBoundingClientRect();
                const st = getComputedStyle(el);
                return r.width > 0 && r.height > 0 &&
                       st.display !== "none" && st.visibility !== "hidden";
            };

            // ============================================================
            // GOOGLE-SPECIFIC PATH
            // ============================================================
            // Do NOT scan every <a> on the page. That is what can select
            // "Google apps", Images, Maps, etc. Instead require the anchor
            // to belong to an organic result containing an H3 title.
            const searchRoot = document.querySelector("#search");

            if (searchRoot) {
                const anchors = Array.from(searchRoot.querySelectorAll("a[href]"));

                for (const a of anchors) {
                    if (!visible(a)) continue;
                    if (sponsored(a)) continue;

                    // The result title is an H3. It can be inside the anchor
                    // or inside a nearby ancestor result container.
                    const h3Inside = a.querySelector("h3");
                    const resultContainer = a.closest("div[data-snhf], div.MjjYud, div.g, div[data-hveid]");
                    const h3Nearby = resultContainer ? resultContainer.querySelector("h3") : null;

                    if (!h3Inside && !h3Nearby) continue;

                    let href = unwrapGoogleUrl(a.getAttribute("href") || a.href || "");
                    if (!isExternalHttp(href)) continue;

                    const title = clean((h3Inside || h3Nearby).innerText) ||
                                  clean(a.innerText) || "first result";

                    return { href, text: title.slice(0, 180) };
                }
            }

            // ============================================================
            // FALLBACK FOR OTHER SEARCH RESULT LAYOUTS
            // ============================================================
            // Only use this if Google did not expose its normal #search/H3
            // structure. Still require a meaningful external link and reject
            // obvious navigation/ad links.
            const anchors = Array.from(document.querySelectorAll("a[href]"));
            for (const a of anchors) {
                if (!visible(a) || sponsored(a)) continue;

                const text = clean(a.innerText || a.getAttribute("aria-label") || a.title);
                if (!text || text.length < 2) continue;

                const href = unwrapGoogleUrl(a.getAttribute("href") || a.href || "");
                if (!isExternalHttp(href)) continue;

                // Avoid obvious Google navigation labels in the fallback.
                const low = text.toLowerCase();
                if (["google apps", "images", "maps", "shopping", "news", "videos", "more"].includes(low)) continue;

                return { href, text: text.slice(0, 180) };
            }

            return null;
        }
        """)

        if not candidate or not candidate.get("href"):
            return False, "No organic Google search result found."

        href = candidate["href"]
        text = candidate.get("text", "first result")

        ok, result = open_url(href)
        if ok:
            return True, f"Opened first organic result: {text}"
        return False, result

    except Exception as e:
        return False, f"Could not open first organic result: {e}"

# ============================================================
# FIRST VIDEO ON CURRENT PAGE
# ============================================================

def open_first_video():
    """
    Generic current-page video opener.

    It intentionally does not assume YouTube. It looks for:
      - YouTube /watch?v=
      - common /video/ URLs
      - links whose text/aria/title contains video/watch/play
    """

    global _page

    if _page is None:
        return False, "Browser unavailable."

    try:
        candidate = _page.evaluate(
            """
            () => {
                const visible = el => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 &&
                           s.visibility !== "hidden" &&
                           s.display !== "none";
                };

                const clean = s => (s || "")
                    .replace(/\\s+/g, " ")
                    .trim();

                const links = [...document.querySelectorAll("a")]
                    .filter(visible);

                const score = a => {
                    const href = a.href || "";
                    const text = clean(
                        a.innerText ||
                        a.getAttribute("aria-label") ||
                        a.getAttribute("title")
                    ).toLowerCase();

                    let score = 0;

                    if (href.includes("youtube.com/watch?v=")) score += 100;
                    if (href.includes("/watch?v=")) score += 90;
                    if (/\\/video(?:\\/|$)/i.test(href)) score += 80;
                    if (/\\/videos?(?:\\/|$)/i.test(href)) score += 75;

                    if (
                        text.includes("watch") ||
                        text.includes("video") ||
                        text.includes("play")
                    ) score += 30;

                    return score;
                };

                let best = null;
                let bestScore = 0;

                for (const a of links) {
                    const href = a.href || "";
                    if (!href) continue;

                    const s = score(a);

                    if (s > bestScore) {
                        bestScore = s;
                        best = {
                            href: href,
                            text: clean(
                                a.innerText ||
                                a.getAttribute("aria-label") ||
                                a.getAttribute("title")
                            ).slice(0, 160)
                        };
                    }
                }

                return best;
            }
            """
        )

        if not candidate:
            return False, "No video link found on the current page."

        ok, result = open_url(candidate["href"])

        if ok:
            return True, (
                "Opened first video"
                + (
                    ": " + candidate["text"]
                    if candidate.get("text")
                    else ""
                )
            )

        return False, result

    except Exception as e:
        return False, f"Could not open first video: {e}"


# ============================================================
# NAVIGATION
# ============================================================

def open_url(url):
    global _page

    url = str(url).strip()
    if not url:
        return False, "No URL provided."

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    ready, error = _ensure_browser_ready()
    if not ready:
        return False, error

    # A page can close between the health check and goto(). If that happens,
    # rebuild the browser once and retry the navigation exactly once.
    for attempt in range(2):
        try:
            _page.goto(
                url,
                wait_until="commit",
                timeout=NAV_TIMEOUT,
            )
            tiny_wait()
            update_active_site(url)
            try:
                observe_page()
            except Exception:
                pass
            return True, f"Opened {url}"
        except Exception as e:
            if attempt == 0 and _is_closed_browser_error(e):
                print("⚠️ Navigation lost its browser tab. Reopening Brave and retrying once…")
                close_browser()
                ready, recovery_error = _ensure_browser_ready()
                if ready:
                    continue
                return False, f"Navigation failed: {recovery_error} Original error: {e}"
            return False, f"Navigation failed: {e}"

    return False, "Navigation failed after browser recovery."


def go_back():
    if _page is None:
        return False, "Browser unavailable."

    try:
        _page.go_back(
            wait_until="commit",
            timeout=5000,
        )
        tiny_wait()
        return True, "Went back."
    except Exception as e:
        return False, f"Back failed: {e}"


def go_forward():
    if _page is None:
        return False, "Browser unavailable."

    try:
        _page.go_forward(
            wait_until="commit",
            timeout=5000,
        )
        tiny_wait()
        return True, "Went forward."
    except Exception as e:
        return False, f"Forward failed: {e}"


def wait_seconds(seconds=1):
    try:
        seconds = float(seconds)
    except Exception:
        seconds = 1

    seconds = max(0.1, min(seconds, 5))
    time.sleep(seconds)

    return True, f"Waited {seconds:.1f}s"


# ============================================================
# CLICK / TYPE / KEYBOARD
# ============================================================

def click_text(text):
    if _page is None:
        return False, "Browser unavailable."

    original_text = str(text).strip()
    text = _normalize_click_target(original_text)

    if not text:
        return False, "No target text."

    scope_before = _website_memory_scope()
    descriptor = _describe_target_locator("CLICK_TEXT", text)
    remembered = _try_website_memory("CLICK_TEXT", text)
    if remembered is not None:
        return remembered

    strategies = [
        lambda: _page.get_by_role(
            "link",
            name=text,
            exact=True,
        ).first.click(timeout=CLICK_TIMEOUT),

        lambda: _page.get_by_role(
            "button",
            name=text,
            exact=True,
        ).first.click(timeout=CLICK_TIMEOUT),

        lambda: _page.get_by_text(
            text,
            exact=True,
        ).first.click(timeout=CLICK_TIMEOUT),

        lambda: _page.get_by_text(
            text,
            exact=False,
        ).first.click(timeout=CLICK_TIMEOUT),
    ]

    for i, strategy in enumerate(strategies):
        try:
            previous_url = _page.url
            strategy()
            tiny_wait()
            _refresh_page_map_if_navigated(previous_url)

            kind = (
                "link"
                if i == 0
                else "button"
                if i == 1
                else "text"
            )

            _remember_website_locator("CLICK_TEXT", text, descriptor, scope_before)
            return True, f"Clicked {kind}: {text}"
        except Exception:
            pass

    # Natural-language targets may describe a destination rather than its exact label:
    # e.g. "English Wikipedia" should match the visible link named "English".
    semantic_ok, semantic_message = _semantic_click_visible_target(text)
    if semantic_ok:
        descriptor_after = _describe_target_locator("CLICK_TEXT", text)
        _remember_website_locator("CLICK_TEXT", text, descriptor_after, _website_memory_scope())
        return True, semantic_message

    return False, f"Could not find clickable target: {text}. {semantic_message}"


def click_href(href):
    if _page is None:
        return False, "Browser unavailable."

    href = str(href).strip()

    if not href:
        return False, "No href."

    scope_before = _website_memory_scope()
    descriptor = _describe_target_locator("CLICK_HREF", href)
    remembered = _try_website_memory("CLICK_HREF", href)
    if remembered is not None:
        return remembered

    try:
        locator = _page.locator(
            f'a[href="{href}"]'
        ).first

        previous_url = _page.url
        locator.click(timeout=CLICK_TIMEOUT)
        tiny_wait()
        _refresh_page_map_if_navigated(previous_url)

        _remember_website_locator("CLICK_HREF", href, descriptor, scope_before)
        return True, f"Clicked link: {href}"

    except Exception:
        pass

    # Also support absolute-vs-relative href differences.
    try:
        locator = _page.locator("a").filter(
            has=_page.locator(f'[href="{href}"]')
        ).first
        locator.click(timeout=CLICK_TIMEOUT)
        tiny_wait()
        _remember_website_locator("CLICK_HREF", href, descriptor, scope_before)
        return True, f"Clicked link: {href}"
    except Exception:
        pass

    return False, f"Could not click href: {href}"


def type_text(text, target=None):
    if _page is None:
        return False, "Browser unavailable."

    text = str(text)

    if target:
        target = str(target).strip()
        scope_before = _website_memory_scope()
        descriptor = _describe_target_locator("TYPE_TEXT", target)
        remembered = _try_website_memory("TYPE_TEXT", target, text)
        if remembered is not None:
            return remembered

        try:
            _page.get_by_placeholder(
                target,
                exact=True,
            ).first.fill(
                text,
                timeout=TYPE_TIMEOUT,
            )
            _remember_website_locator("TYPE_TEXT", target, descriptor, scope_before)
            return True, f"Typed into {target}"
        except Exception:
            pass

        try:
            _page.get_by_label(
                target,
                exact=True,
            ).first.fill(
                text,
                timeout=TYPE_TIMEOUT,
            )
            _remember_website_locator("TYPE_TEXT", target, descriptor, scope_before)
            return True, f"Typed into {target}"
        except Exception:
            pass

    try:
        _page.locator(
            'input:visible,textarea:visible,[contenteditable="true"]'
        ).first.fill(
            text,
            timeout=TYPE_TIMEOUT,
        )
        return True, "Text entered."
    except Exception:
        pass

    return False, "No usable input found."


def press_key(key):
    if _page is None:
        return False, "Browser unavailable."

    try:
        _page.keyboard.press(str(key))
        tiny_wait()
        return True, f"Pressed {key}"
    except Exception as e:
        return False, f"Key press failed: {e}"


def scroll_page(amount=700):
    if _page is None:
        return False, "Browser unavailable."

    try:
        amount = int(amount)
    except Exception:
        amount = 700

    amount = max(-2500, min(amount, 2500))

    try:
        _page.mouse.wheel(0, amount)
        tiny_wait()
        return True, f"Scrolled {amount}px"
    except Exception as e:
        return False, f"Scroll failed: {e}"


# ============================================================
# TARGET VALIDATION
# ============================================================

def target_visible(action, args):
    if _page is None:
        return False

    action = str(action).upper().strip()
    args = args if isinstance(args, dict) else {}

    if action == "CLICK_TEXT":
        target = str(args.get("text", "")).strip()

        if not target:
            return False

        try:
            return bool(_page.evaluate(
                """
                target => {
                    const norm = s => (s || "")
                        .replace(/\\s+/g, " ")
                        .trim()
                        .toLowerCase();

                    const wanted = norm(target);

                    for (const el of document.querySelectorAll(
                        'a,button,[role="button"],[role="link"]'
                    )) {
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);

                        if (
                            r.width <= 0 ||
                            r.height <= 0 ||
                            s.visibility === "hidden" ||
                            s.display === "none"
                        ) continue;

                        const text = norm(
                            el.innerText ||
                            el.getAttribute("aria-label") ||
                            el.getAttribute("title") ||
                            el.getAttribute("alt")
                        );
                        const href = norm(el.getAttribute("href") || el.href || "");
                        if (text === wanted || text.includes(wanted) || wanted.includes(text) && text.length >= 3) return true;

                        // Semantic validation: "English Wikipedia" can refer to a
                        // visible control labelled simply "English". This is only a
                        // presence check; click_text still selects the unique best match.
                        const ignored = new Set(["open","go","to","visit","click","tap","press","on","the","a","an","page","website","site","please","wikipedia","edition","button","link","tab","option","menu","item","control","icon","language"]);
                        const tokens = wanted.split(/\\s+/).filter(t => t && !ignored.has(t));
                        const matched = tokens.filter(t => text.includes(t) || href.includes(t)).length;
                        if (tokens.length && matched === tokens.length) return true;
                        if (tokens.includes("english") && /(^|\\.)en\\.wikipedia\\.org/.test(href)) return true;
                    }

                    return false;
                }
                """,
                target,
            ))
        except Exception:
            return False

    if action == "CLICK_HREF":
        href = str(args.get("href", "")).strip()

        if not href:
            return False

        try:
            return bool(_page.evaluate(
                """
                href => !!document.querySelector(
                    `a[href="${CSS.escape(href)}"]`
                )
                """,
                href,
            ))
        except Exception:
            return False

    if action == "TYPE_TEXT":
        target = str(args.get("target", "")).strip()

        try:
            return bool(_page.evaluate(
                """
                target => {
                    const els = document.querySelectorAll(
                        'input,textarea,select,[contenteditable="true"]'
                    );

                    for (const el of els) {
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);

                        if (
                            r.width <= 0 ||
                            r.height <= 0 ||
                            s.visibility === "hidden" ||
                            s.display === "none"
                        ) continue;

                        if (!target) return true;

                        const values = [
                            el.getAttribute("placeholder"),
                            el.getAttribute("aria-label"),
                            el.getAttribute("name")
                        ]
                        .filter(Boolean)
                        .map(v => v.toLowerCase());

                        const wanted = target.toLowerCase();

                        if (
                            values.some(
                                v => v === wanted || v.includes(wanted)
                            )
                        ) return true;
                    }

                    return false;
                }
                """,
                target,
            ))
        except Exception:
            return False

    return True


# ============================================================
# ACTIONS
# ============================================================

ACTIONS = """
OPEN_URL
{"url":"https://example.com"}

SEARCH_WEB
{"query":"latest AI news"}

SEARCH_CURRENT_PAGE
{"query":"artificial intelligence"}

SEARCH_YOUTUBE
{"query":"MrBeast"}

OPEN_FIRST_ORGANIC_RESULT
{}

OPEN_FIRST_VIDEO
{}

OPEN_FIRST_YOUTUBE_VIDEO
{}

CLICK_TEXT
{"text":"Analytics"}

CLICK_HREF
{"href":"/analytics"}

TYPE_TEXT
{"text":"hello","target":"Search"}

PRESS
{"key":"Enter"}

SCROLL
{"amount":700}

BACK
{}

FORWARD
{}

WAIT
{"seconds":1}

READ_PAGE
{}

ANSWER
{}

DONE
{}
"""


# ============================================================
# PLANNER
# ============================================================

PLANNER_SYSTEM = """
You are the fast planning brain of a general-purpose computer/browser agent.

Your job is to understand what the user MEANS, using:
1. the current browser page,
2. the user's original request,
3. recent conversation history.

Do not treat every command as an isolated command.

CRITICAL CONTEXT RULE:
If the user says things like:
- "open the first video"
- "click the first one"
- "go back"
- "now open it"
- "do that"
- "click it"
- "what about the second one"

interpret them using the CURRENT PAGE and RECENT CONVERSATION.

Examples:
- If the previous command searched Google for something and the user says
  "open the first video", act on the current search results. Do NOT search
  for a website called "the first video".
- If the current page is a search-results page and the user says
  "open the first link", use OPEN_FIRST_ORGANIC_RESULT.
- If the current page contains videos and the user says
  "open the first video", use OPEN_FIRST_VIDEO.
- If the user explicitly says "open <thing>", "go to <thing>", or
  "visit <thing>" and <thing> is a named destination rather than an
  explicit URL, ALWAYS use SEARCH_WEB for that name, then
  OPEN_FIRST_ORGANIC_RESULT, then DONE. Do NOT invent a URL and do NOT
  directly OPEN_URL from model memory. The search is intentionally VISIBLE
  in the browser because the user asked the browser to find the destination.
- This rule is generic and applies to any website/destination name.
- The first search result must be organic, not sponsored. The executor
  filters advertising containers.
- Never invent a website domain just because the name looks like a domain.
- If the user explicitly asks to search Google/the web, use SEARCH_WEB.
- If the user explicitly asks to search YouTube, use SEARCH_YOUTUBE.
- A generic "search for X" means SEARCH_YOUTUBE when ACTIVE SITE is youtube.
- A generic "search for X" means SEARCH_WEB only when ACTIVE SITE is google.
- On other sites, prefer SEARCH_CURRENT_PAGE; it identifies the site's search field/form and can use Enter or an icon-only submit control.
- Match natural-language targets semantically when a visible control's label is a shorter form of the requested destination (e.g. "English Wikipedia" can match a unique link labelled "English"). Verify the destination after clicking.
- Do NOT turn generic "search for X" into Google just because "search" is present.
- Do NOT search Google to discover a website URL. Website destinations are resolved by NOVA/Qwen before planning.
- If the user asks to open/click a named section, tab, menu, or page, first check whether that target is visibly present on the CURRENT PAGE. If it is visible, click it. If it is not visible, use current page + conversation context to decide what to do; do not invent a destination.
- "open Shorts section" means first look for a visible Shorts control/section on the current page.
- Do not use SEARCH_WEB for a section that is already visible on the current page.
- Do not use SEARCH_WEB merely because you are confused about a follow-up
  that can be solved from the current page.

TASK DECOMPOSITION (IMPORTANT):
- For a request with multiple goals, a publisher + section + article, or an implied sequence, decompose the FULL request once before acting.
- Think in logical phases, then convert those phases into executable browser actions in the correct order.
- Execute prerequisites first. For a publisher/section/article request, the order is: open the publisher, navigate to the requested section, then locate and open the matching article.
- Do not search Google first when the user asked to navigate inside a specific publisher's website.
- Use the supplied SITE-SCOPED REQUEST HINT, if present, as grounding for the site, section, and article subject. Do not replace it with a generic web search.
- Return one ordered action list for the whole task. The executor will run it sequentially; do not plan later clicks against controls that only appear after navigation unless the action is explicitly a later step.
- Keep the plan lean and fast: one Qwen planning call for the whole task, not one call per step. Replanning is only for a failed or unavailable step.

FAST RULES:
- Make the shortest realistic plan.
- Usually make 1-6 actions for multi-stage tasks and 1-4 for simple tasks.
- Do not call Qwen after every action.
- Do not repeat an action that already succeeded.
- Navigation can invalidate old targets; if that happens, replan from the
  NEW page toward the SAME original goal.
- Never click an unrelated visible link merely because it exists.
- Never invent refs, shell commands, PowerShell, or Python.
- Do not invent a website URL. NOVA resolves destinations before planning.
- Respect ACTIVE SITE for generic search commands.
- For factual questions, gather page evidence and use ANSWER.
- DONE means an action-only request is complete.
- ANSWER means answer the user's original question.
- Return ONLY valid JSON.

General examples:
"open oracle" ->
SEARCH_WEB("oracle") -> OPEN_FIRST_ORGANIC_RESULT -> DONE

"open appleswebsite" ->
SEARCH_WEB("appleswebsite") -> OPEN_FIRST_ORGANIC_RESULT -> DONE

"visit minecraft website" ->
SEARCH_WEB("minecraft website") -> OPEN_FIRST_ORGANIC_RESULT -> DONE

"open the first video" ->
Use CURRENT PAGE + RECENT CONVERSATION -> OPEN_FIRST_VIDEO -> DONE

"search for bla bla back sheep" ->
SEARCH_WEB("bla bla back sheep") -> DONE

after that, "open the first video" ->
OPEN_FIRST_VIDEO -> DONE

"open the first link" on a search page ->
OPEN_FIRST_ORGANIC_RESULT -> DONE
""" + ACTIONS


def create_plan(command):
    observation = observe_page()

    # Structured grounding for Qwen: resolve the requested publisher/section
    # locally, but let Qwen produce the ordered multi-step action plan.
    scoped_hint = None
    if _website_directory is not None:
        try:
            scoped_hint = _website_directory.resolve_site_scoped_request(command)
        except Exception:
            scoped_hint = None

    page_memory = {}
    if _website_memory is not None and observation.get("url"):
        try:
            from urllib.parse import urlsplit
            parsed = urlsplit(observation["url"])
            host = (parsed.hostname or "").lower().removeprefix("www.")
            path = parsed.path or "/"
            if path != "/":
                path = path.rstrip("/") or "/"
            profiles = _website_memory.get_page_profiles(host, path, limit=1)
            if profiles:
                profile = profiles[0]
                controls = profile.get("controls", {})
                page_memory = {
                    "page_title": profile.get("page_title", ""),
                    "purpose": profile.get("purpose", ""),
                    "visit_count": profile.get("visit_count", 1),
                    "fingerprint": profile.get("fingerprint", ""),
                    "last_verified": profile.get("last_verified"),
                    "known_search_fields": [x for x in controls.get("inputs", []) if isinstance(x, dict) and any(k in str(x).lower() for k in ("search", "query", "keyword"))][:5],
                    "known_links": controls.get("links", [])[:12],
                    "known_buttons": controls.get("buttons", [])[:10],
                }
        except Exception:
            page_memory = {}

    prompt = f"""
ORIGINAL USER REQUEST:
{command}

SITE-SCOPED REQUEST HINT (resolved from NOVA's local website directory; null if not applicable):
{json.dumps(scoped_hint, ensure_ascii=False, separators=(",", ":")) if scoped_hint else "null"}

If the hint is present, preserve the requested site and section. For an article request, plan the ordered journey: open the site's home page first, click/navigate to the requested section second, then find and open the article matching the subject. Use CLICK_TEXT for a visible section link; after navigating, use the current site's search field if needed, then open the matching article result. Do not open Google search results as the final destination.

RECENT CONVERSATION:
{history_for_qwen()}

CURRENT BROWSER:
URL: {observation["url"]}
TITLE: {observation["title"]}
ACTIVE SITE: {current_site()}
TEXT:
{observation["text"]}

LINKS:
{json.dumps(observation["links"], ensure_ascii=False, separators=(",", ":"))}

BUTTONS:
{json.dumps(observation["buttons"], ensure_ascii=False, separators=(",", ":"))}

INPUTS:
{json.dumps(observation["inputs"], ensure_ascii=False, separators=(",", ":"))}

PREVIOUSLY LEARNED PAGE MAP (validate against the current page; stale details are hints only):
{json.dumps(page_memory, ensure_ascii=False, separators=(",", ":"))}

PERSISTENT TASK MEMORY (reference only; never assume the current task is already done):
{memory_for_qwen()}

PAGE TEXT SNAPSHOT FILE:
{observation.get("page_text_file", "")}

Decide what the user means in this context.
Choose the shortest plan that actually accomplishes the ORIGINAL request.
Return ONLY:
{{"plan":[{{"action":"ACTION_NAME","args":{{}}}}]}}
"""

    raw = ask_qwen([
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": prompt},
    ])

    if raw.startswith("QWEN_ERROR:"):
        print("❌ " + raw)
        return []

    data = extract_json(raw)

    if not data or not isinstance(data.get("plan"), list):
        print("❌ Qwen returned an invalid plan.")
        return []

    allowed = {
        "OPEN_URL",
        "SEARCH_WEB",
        "SEARCH_CURRENT_PAGE",
        "SEARCH_YOUTUBE",
        "OPEN_FIRST_ORGANIC_RESULT",
        "OPEN_FIRST_VIDEO",
        "OPEN_FIRST_YOUTUBE_VIDEO",
        "CLICK_TEXT",
        "CLICK_HREF",
        "TYPE_TEXT",
        "PRESS",
        "SCROLL",
        "BACK",
        "FORWARD",
        "WAIT",
        "READ_PAGE",
        "ANSWER",
        "DONE",
    }

    clean = []

    for step in data["plan"][:MAX_ACTIONS]:
        if not isinstance(step, dict):
            continue

        action = str(
            step.get("action", "")
        ).upper().strip()

        args = step.get("args", {})

        if not isinstance(args, dict):
            args = {}

        if action in allowed:
            clean.append({
                "action": action,
                "args": args,
            })

    # For known publisher + section + article requests, validate the order
    # of Qwen's decomposition. The AI still chooses the article-finding actions,
    # but prerequisites are guaranteed to run first.
    if scoped_hint and scoped_hint.get("section"):
        ordered = [
            {"action": "OPEN_URL", "args": {"url": scoped_hint["site_url"]}},
            {"action": "CLICK_TEXT", "args": {"text": scoped_hint["section"]}},
        ]
        remaining = []
        for item in clean:
            action = item["action"]
            args = item["args"]
            if action == "OPEN_URL":
                continue
            # Avoid a generic Google detour for a publisher-scoped task.
            if action == "SEARCH_WEB":
                continue
            if action == "CLICK_TEXT" and str(args.get("text", "")).strip().lower() == str(scoped_hint["section"]).lower():
                continue
            if action == "DONE":
                continue
            remaining.append(item)
        if not remaining:
            remaining = [
                {"action": "SEARCH_CURRENT_PAGE", "args": {"query": scoped_hint.get("subject", "")}},
                {"action": "OPEN_FIRST_ORGANIC_RESULT", "args": {}},
            ]
        ordered.extend(remaining)
        ordered.append({"action": "DONE", "args": {}})
        clean = ordered[:MAX_ACTIONS]
        print("🧠 Qwen plan ordered into phases: 1) open publisher  2) enter section  3) find/open article")

    return clean


# ============================================================
# ANSWER FROM PAGE
# ============================================================

def answer_from_page(command):
    observation = observe_page()

    prompt = f"""
ORIGINAL USER QUESTION:
{command}

RECENT CONTEXT:
{history_for_qwen()}

CURRENT PAGE:
URL: {observation["url"]}
TITLE: {observation["title"]}
TEXT:
{observation["text"]}

LINKS:
{json.dumps(observation["links"], ensure_ascii=False, separators=(",", ":"))}

Answer the ORIGINAL question using the useful information currently
available in the browser. Do not guess. Be concise.
"""

    raw = ask_qwen([
        {
            "role": "system",
            "content": (
                "You are the final answerer for a browser agent. "
                "Answer only the user's question."
            ),
        },
        {"role": "user", "content": prompt},
    ])

    if raw.startswith("QWEN_ERROR:"):
        return False, raw

    raw = raw.strip()

    if not raw:
        return False, "Empty answer."

    return True, raw


# ============================================================
# EXECUTE ACTION
# ============================================================

def execute_action(action, args):
    action = str(action).upper().strip()
    args = args if isinstance(args, dict) else {}

    if action not in {"DONE", "ANSWER"}:
        ready, error = _ensure_browser_ready()
        if not ready:
            return False, error

    if action == "OPEN_URL":
        return open_url(args.get("url", ""))

    if action == "SEARCH_WEB":
        return search_web(args.get("query", ""))

    if action == "SEARCH_CURRENT_PAGE":
        return search_current_page(args.get("query", ""))

    if action == "SEARCH_YOUTUBE":
        return search_youtube(args.get("query", ""))

    if action == "OPEN_FIRST_ORGANIC_RESULT":
        return open_first_organic_result()

    if action == "OPEN_FIRST_VIDEO":
        return open_first_video()

    if action == "OPEN_FIRST_YOUTUBE_VIDEO":
        # Kept as a separate action for existing plans.
        return open_first_video()

    if action == "CLICK_TEXT":
        return click_text(args.get("text", ""))

    if action == "CLICK_HREF":
        return click_href(args.get("href", ""))

    if action == "TYPE_TEXT":
        return type_text(
            args.get("text", ""),
            args.get("target"),
        )

    if action == "PRESS":
        return press_key(args.get("key", "Enter"))

    if action == "SCROLL":
        return scroll_page(args.get("amount", 700))

    if action == "BACK":
        return go_back()

    if action == "FORWARD":
        return go_forward()

    if action == "WAIT":
        return wait_seconds(args.get("seconds", 1))

    if action == "READ_PAGE":
        observation = observe_page()
        return True, (
            f"Read page: {observation['title']} "
            f"({len(observation['text'])} chars)"
        )

    if action == "ANSWER":
        message = args.get("message")
        if message:
            return True, str(message)
        return answer_from_page(CURRENT_COMMAND)

    if action == "DONE":
        return True, "Task complete."

    return False, f"Unknown action: {action}"


# ============================================================
# VERY FAST UNIVERSAL COMMAND SHORTCUTS
# ============================================================

def visible_target_text(target):
    """Fast browser-side check for an exact visible label."""
    if _page is None:
        return False

    target = str(target).strip()
    if not target:
        return False

    try:
        return bool(_page.evaluate("""
        (target) => {
            const clean = s => (s || "").replace(/\\s+/g, " ").trim().toLowerCase();
            const wanted = clean(target);
            if (!wanted) return false;

            const visible = el => {
                const r = el.getBoundingClientRect();
                const st = getComputedStyle(el);
                return r.width > 0 && r.height > 0 &&
                       st.display !== "none" && st.visibility !== "hidden";
            };

            for (const el of document.querySelectorAll(
                'a,button,[role="button"],[role="tab"],[role="menuitem"]'
            )) {
                if (!visible(el)) continue;
                const text = clean(
                    el.innerText ||
                    el.getAttribute("aria-label") ||
                    el.getAttribute("title")
                );
                if (text === wanted) return true;
            }
            return false;
        }
        """, target))
    except Exception:
        return False


def _normalize_click_target(raw_target):
    """Remove conversational wrappers and element-type words from click targets."""
    target = re.sub(r"\s+", " ", str(raw_target or "")).strip()
    target = re.sub(r"^(?:please\s+)?(?:click|press|tap)\s+(?:on\s+)?", "", target, flags=re.IGNORECASE)
    target = re.sub(r"^(?:the|a|an)\s+", "", target, flags=re.IGNORECASE)
    # These words describe the control type, not its label.
    target = re.sub(r"\s+(?:button|link|tab|option|menu item|menu|control|icon|language link|language button)$", "", target, flags=re.IGNORECASE)
    return target.strip(" \"'`.,!? ")


def fast_command(command):
    """Handle common browser actions without spending a Qwen call."""
    text = str(command).strip()
    lower = re.sub(r"\s+", " ", text.lower())

    # Current-page navigation/actions.
    if lower in {
        "open the first video", "open first video",
        "open the first youtube video", "open first youtube video",
        "play the first video", "play first video",
    }:
        return [
            {"action": "OPEN_FIRST_VIDEO", "args": {}},
            {"action": "DONE", "args": {}},
        ]

    if lower in {
        "open the first link", "open first link",
        "click the first link", "click first link",
    }:
        if current_site() == "google":
            return [
                {"action": "OPEN_FIRST_ORGANIC_RESULT", "args": {}},
                {"action": "DONE", "args": {}},
            ]

    if lower in {"go back", "back", "go backwards"}:
        return [
            {"action": "BACK", "args": {}},
            {"action": "DONE", "args": {}},
        ]

    if lower in {"go forward", "forward", "go forwards"}:
        return [
            {"action": "FORWARD", "args": {}},
            {"action": "DONE", "args": {}},
        ]

    if lower in {"scroll down", "scroll down a bit"}:
        return [
            {"action": "SCROLL", "args": {"amount": 700}},
            {"action": "DONE", "args": {}},
        ]

    if lower in {"scroll up", "scroll up a bit"}:
        return [
            {"action": "SCROLL", "args": {"amount": -700}},
            {"action": "DONE", "args": {}},
        ]

    if lower in {"press enter", "hit enter", "press return", "hit return"}:
        return [
            {"action": "PRESS", "args": {"key": "Enter"}},
            {"action": "DONE", "args": {}},
        ]

    if lower in {"read this page", "read the page", "read page"}:
        return [
            {"action": "READ_PAGE", "args": {}},
            {"action": "DONE", "args": {}},
        ]

    # Natural-language click commands are resolved against the live page first.
    # Examples: "click on the English button", "tap English", "press Search".
    m = re.match(r"^(?:click|press|tap)\s+(?:on\s+)?(.+)$", text, flags=re.IGNORECASE)
    if m:
        target = _normalize_click_target(m.group(1))
        if target:
            # Let click_text perform the actual match/click exactly once. The fast
            # parser must never trigger a semantic click as a side effect.
            return [
                {"action": "CLICK_TEXT", "args": {"text": target}},
                {"action": "DONE", "args": {}},
            ]

    return None


def obvious_command(command):
    """
    Deterministic intent routing.

    Core rules:
    1. Explicit destination aliases open directly when we know the URL.
    2. Unknown destinations are resolved by Qwen itself, NOT by Google.
    3. Generic "search for X" stays on the active site.
    4. Only explicit web/Google wording uses SEARCH_WEB.
    5. Contextual phrases ("first video", "it", "that", etc.) go to Qwen.
    """
    text = str(command).strip()
    lower = text.lower()

    # ------------------------------------------------------------
    # 0. Site- and section-scoped article/content requests.
    # Example: "Open Google Sundar Pichai article in Times of India inside tech section".
    # Search the requested publisher/section, then OPEN the first organic result;
    # do not treat the whole sentence as a Google query and stop on the results page.
    # ------------------------------------------------------------
    if _website_directory is not None:
        try:
            scoped_request = _website_directory.resolve_site_scoped_request(text)
        except Exception as _scoped_error:
            scoped_request = None
            print(f"⚠️ Site-scoped request parser failed: {_scoped_error}")
        if scoped_request:
            section_desc = f" / {scoped_request['section']} section" if scoped_request.get("section") else ""
            print(
                f"🎯 Site-scoped task: {scoped_request['site_name']}{section_desc}; "
                "ordered fallback: open publisher -> enter section -> find article"
            )
            fallback = [
                {"action": "OPEN_URL", "args": {"url": scoped_request["site_url"]}},
            ]
            if scoped_request.get("section"):
                fallback.append({"action": "CLICK_TEXT", "args": {"text": scoped_request["section"]}})
            fallback.extend([
                {"action": "SEARCH_CURRENT_PAGE", "args": {"query": scoped_request.get("subject", "")}},
                {"action": "OPEN_FIRST_ORGANIC_RESULT", "args": {}},
                {"action": "DONE", "args": {}},
            ])
            return fallback

    # ------------------------------------------------------------
    # 1. Explicit URL.
    # ------------------------------------------------------------
    for prefix in (
        "open https://", "go to https://", "visit https://",
        "open http://", "go to http://", "visit http://",
    ):
        if lower.startswith(prefix):
            url = text[len(prefix):].strip()
            return [
                {"action": "OPEN_URL", "args": {"url": url}},
                {"action": "DONE", "args": {}},
            ]

    # ------------------------------------------------------------
    # 2. Explicit web / Google search ALWAYS overrides site context.
    # ------------------------------------------------------------
    query = explicit_web_search_query(text)
    if query:
        return [
            {"action": "SEARCH_WEB", "args": {"query": query}},
            {"action": "DONE", "args": {}},
        ]

    # ------------------------------------------------------------
    # 3. Explicit YouTube search.
    # ------------------------------------------------------------
    query = explicit_youtube_search_query(text)
    if query:
        return [
            {"action": "SEARCH_YOUTUBE", "args": {"query": query}},
            {"action": "DONE", "args": {}},
        ]

    # ------------------------------------------------------------
    # 4. Explicit destination: "open YouTube", "go to GitHub", etc.
    # ------------------------------------------------------------
    destination_match = re.match(
        r"^(?:open|go to|visit)\s+(?:the\s+)?(.+?)\s*$",
        text,
        flags=re.IGNORECASE,
    )

    if destination_match:
        destination = destination_match.group(1).strip()
        low_dest = destination.lower()

        # Never steal contextual commands from Qwen.
        contextual = (
            low_dest in {"it", "that", "this"},
            low_dest.startswith("the first"),
            low_dest.startswith("first"),
            low_dest.startswith("the second"),
            low_dest.startswith("second"),
            low_dest.startswith("the third"),
            low_dest.startswith("third"),
            low_dest.startswith("the next"),
            low_dest.startswith("next"),
            low_dest.startswith("a video"),
            low_dest.startswith("the video"),
            low_dest.endswith(" section"),
            low_dest.endswith(" tab"),
            low_dest.endswith(" menu"),
            low_dest.endswith(" page"),
        )

        if not any(contextual):
            # Remove words that are only describing the destination.
            cleaned = re.sub(
                r"\b(website|site|domain)\b",
                " ",
                destination,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(r"\s+", " ", cleaned).strip()

            # Resolve known websites locally BEFORE calling Qwen. The supplied directory
            # is already keyed from URL hostnames, so common destinations need no model call.
            # Do this before on-page matching so "open YouTube" means navigate to YouTube,
            # even if the current page happens to contain a YouTube link.
            directory_match = None
            if _website_directory is not None:
                try:
                    directory_match = _website_directory.resolve_website(cleaned)
                except Exception as _directory_error:
                    print(f"⚠️ Website directory lookup failed: {_directory_error}")

            if directory_match and directory_match.get("url"):
                resolved_url = str(directory_match["url"])
                display_name = str(directory_match.get("name") or cleaned)
                matched_by = str(directory_match.get("matched_by") or "local directory")
                print(f"📚 Local website directory hit: {display_name} → {resolved_url} ({matched_by}; no Qwen URL lookup)")
                return [
                    {"action": "OPEN_URL", "args": {"url": resolved_url}},
                    {"action": "DONE", "args": {}},
                ]

            # If the requested destination is represented by a visible control on the
            # current page, use it when the phrase is a sub-page/edition, e.g.
            # "open English Wikipedia" while on wikipedia.org should click "English".
            on_page_label = re.sub(r"\b(wikipedia|website|site|page|edition|homepage|home page)\b", " ", cleaned, flags=re.IGNORECASE)
            on_page_label = re.sub(r"\s+", " ", on_page_label).strip()
            if on_page_label and visible_target_text(on_page_label):
                return [
                    {"action": "CLICK_TEXT", "args": {"text": on_page_label}},
                    {"action": "DONE", "args": {}},
                ]

            # A plain domain such as "open example.org" is already a destination;
            # don't waste a Qwen call trying to discover its URL.
            if _website_directory is not None:
                try:
                    if _website_directory.is_domain_like(cleaned):
                        explicit_domain = cleaned.strip()
                        if not explicit_domain.lower().startswith(("http://", "https://")):
                            explicit_domain = "https://" + explicit_domain
                        print(f"🌐 Direct domain supplied by user: {explicit_domain}")
                        return [
                            {"action": "OPEN_URL", "args": {"url": explicit_domain}},
                            {"action": "DONE", "args": {}},
                        ]
                except Exception:
                    pass

            normalized = normalize_site_name(cleaned)

            if normalized in SITE_URLS:
                return [
                    {
                        "action": "OPEN_URL",
                        "args": {"url": SITE_URLS[normalized]},
                    },
                    {"action": "DONE", "args": {}},
                ]

            # Qwen resolves unknown destinations from its own knowledge.
            resolved = resolve_destination_with_qwen(cleaned)
            if resolved:
                return [
                    {"action": "OPEN_URL", "args": {"url": resolved}},
                    {"action": "DONE", "args": {}},
                ]

            print(
                f"❌ Qwen does not know the official URL for "
                f"'{cleaned}'. No web search was performed."
            )
            return [
                {
                    "action": "ANSWER",
                    "args": {
                        "message": (
                            f"I don't know the official URL for '{cleaned}' "
                            "from my local Qwen knowledge."
                        )
                    },
                }
            ]

    # ------------------------------------------------------------
    # 5. Generic search follows active site context.
    # ------------------------------------------------------------
    query = generic_search_query(text)
    if query:
        site = current_site()

        if site == "youtube":
            return [
                {"action": "SEARCH_YOUTUBE", "args": {"query": query}},
                {"action": "DONE", "args": {}},
            ]

        if site == "google":
            return [
                {"action": "SEARCH_WEB", "args": {"query": query}},
                {"action": "DONE", "args": {}},
            ]

        # Search the current site by inspecting its live fields and form controls.
        # If no suitable field exists, normal failure handling can replan via Qwen.
        return [
            {"action": "SEARCH_CURRENT_PAGE", "args": {"query": query}},
            {"action": "DONE", "args": {}},
        ]

    # ------------------------------------------------------------
    # 6. Visible section/tab/menu.
    # ------------------------------------------------------------
    section_match = re.match(
        r"^(?:open|go to|visit|click)\s+(?:the\s+)?(.+?)\s+"
        r"(?:section|tab|menu|page)\s*$",
        text,
        flags=re.IGNORECASE,
    )

    if section_match:
        target = section_match.group(1).strip()
        if target and visible_target_text(target):
            return [
                {"action": "CLICK_TEXT", "args": {"text": target}},
                {"action": "DONE", "args": {}},
            ]
        return None

    return None


# ============================================================
# REPLAN
# ============================================================

def replan_after_failure(command, failed_action, failure):
    observation = observe_page()

    prompt = f"""
ORIGINAL USER REQUEST:
{command}

RECENT CONVERSATION:
{history_for_qwen()}

FAILED ACTION:
{json.dumps(failed_action, ensure_ascii=False, separators=(",", ":"))}

FAILURE:
{failure}

CURRENT BROWSER:
URL: {observation["url"]}
TITLE: {observation["title"]}
ACTIVE SITE: {current_site()}
TEXT:
{observation["text"]}

LINKS:
{json.dumps(observation["links"], ensure_ascii=False, separators=(",", ":"))}

BUTTONS:
{json.dumps(observation["buttons"], ensure_ascii=False, separators=(",", ":"))}

PAGE TEXT SNAPSHOT FILE:
{observation.get("page_text_file", "")}

PERSISTENT TASK MEMORY:
{memory_for_qwen()}

The previous action failed or became invalid.
Think about what the USER MEANS in the CURRENT CONTEXT.
Continue toward the SAME original goal.
Do not click an unrelated link.
Do not repeat the failed action unless the page now clearly supports it.

If the user originally asked to open a named destination, use:
SEARCH_WEB -> OPEN_FIRST_ORGANIC_RESULT.

If the user says "first link", use the current page.
If the user says "first video", use the current page.
Do not turn a contextual phrase into a website name.

Return ONLY JSON:
{{"plan":[{{"action":"ACTION_NAME","args":{{}}}}]}}
"""

    raw = ask_qwen([
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": prompt},
    ])

    data = extract_json(raw)

    if not data or not isinstance(data.get("plan"), list):
        return []

    allowed = {
        "OPEN_URL",
        "SEARCH_WEB",
        "SEARCH_CURRENT_PAGE",
        "SEARCH_YOUTUBE",
        "OPEN_FIRST_ORGANIC_RESULT",
        "OPEN_FIRST_VIDEO",
        "OPEN_FIRST_YOUTUBE_VIDEO",
        "CLICK_TEXT",
        "CLICK_HREF",
        "TYPE_TEXT",
        "PRESS",
        "SCROLL",
        "BACK",
        "FORWARD",
        "WAIT",
        "READ_PAGE",
        "ANSWER",
        "DONE",
    }

    clean = []

    for step in data["plan"][:MAX_ACTIONS]:
        if not isinstance(step, dict):
            continue

        action = str(
            step.get("action", "")
        ).upper().strip()

        args = step.get("args", {})

        if not isinstance(args, dict):
            args = {}

        if action in allowed:
            clean.append({
                "action": action,
                "args": args,
            })

    return clean


# ============================================================
# PRINT PLAN
# ============================================================

def print_plan(plan, title="📋 PLAN"):
    print()
    print(title)

    for i, step in enumerate(plan, 1):
        print(
            f"{i}. {step.get('action')} "
            f"{step.get('args', {})}"
        )

    print()


# ============================================================
# MAIN TASK ENGINE
# ============================================================

def _needs_ai_decomposition(command):
    """True for multi-stage requests that should be planned by Qwen once."""
    text = re.sub(r"\s+", " ", str(command or "").strip().lower())
    if not text:
        return False
    if _website_directory is not None:
        try:
            if _website_directory.resolve_site_scoped_request(command):
                return True
        except Exception:
            pass
    # Multiple explicit actions, or a destination + section/content target,
    # need ordering; simple one-step commands should stay on the fast path.
    action_words = re.findall(r"\b(open|go to|visit|click|search|find|read|scroll|type|press)\b", text)
    has_section = bool(re.search(r"\b(section|category|tab|menu)\b", text))
    has_content_target = bool(re.search(r"\b(article|story|video|page|post|result)\b", text))
    return len(action_words) >= 2 or (has_section and has_content_target)


def run_task(command):
    global CURRENT_COMMAND

    CURRENT_COMMAND = str(command).strip()

    if not CURRENT_COMMAND:
        return

    stop_event.clear()

    start_time = time.time()

    print()
    print("=" * 64)
    print("🤖 TASK")
    print(CURRENT_COMMAND)
    print("=" * 64)

    # --------------------------------------------------------
    # Conversation path BEFORE browser startup.
    # "hi" must not launch Brave or run the browser planner.
    # --------------------------------------------------------
    handled, _reply = handle_conversation(CURRENT_COMMAND)
    if handled:
        return

    if not start_browser():
        return

    task_start_url = page_identity()
    successful_actions = []
    task_status = "failed"
    task_result = ""

    # --------------------------------------------------------
    # Fast path for truly unambiguous commands.
    # Generic "open X" deliberately goes to Qwen because X may
    # be a destination OR a contextual instruction.
    # --------------------------------------------------------

    plan = _load_safe_task_recipe(CURRENT_COMMAND)
    if not plan:
        plan = fast_command(CURRENT_COMMAND)

    # Complex prompts go through one Qwen decomposition pass before any
    # navigation. Simple commands retain the deterministic zero-Qwen path.
    if not plan and _needs_ai_decomposition(CURRENT_COMMAND):
        print("🧠 Qwen breaking the request into ordered steps...")
        plan = create_plan(CURRENT_COMMAND)

    if not plan:
        plan = obvious_command(CURRENT_COMMAND)

    if plan:
        print("⚡ Direct action / saved workflow" if not _needs_ai_decomposition(CURRENT_COMMAND) else "🧠 Ordered task plan ready")
    else:
        print("👀 Observing page...")
        print("🧠 Qwen understanding context...")
        plan = create_plan(CURRENT_COMMAND)

    if not plan:
        print("❌ No usable plan.")
        add_history(CURRENT_COMMAND, "No usable plan.")
        _remember_completed_task(CURRENT_COMMAND, "No usable plan.", "failed", task_start_url, page_identity(), [])
        return

    print_plan(plan)

    replans = 0
    executed_actions = 0
    last_signature = None

    while (
        plan
        and executed_actions < MAX_ACTIONS
        and not stop_event.is_set()
        and not exit_event.is_set()
    ):
        step = plan.pop(0)

        if not isinstance(step, dict):
            continue

        action = str(
            step.get("action", "")
        ).upper().strip()

        args = step.get("args", {})

        if not isinstance(args, dict):
            args = {}

        signature = (
            action,
            json.dumps(
                args,
                sort_keys=True,
                ensure_ascii=False,
            ),
        )

        # Prevent an immediate infinite repetition.
        if signature == last_signature:
            print("⚠️ Same action repeated — rethinking.")

            if replans >= MAX_REPLANS:
                print("❌ Maximum replans reached.")
                add_history(
                    CURRENT_COMMAND,
                    "Stopped after repeated action.",
                )
                return

            replans += 1

            plan = replan_after_failure(
                CURRENT_COMMAND,
                {
                    "action": action,
                    "args": args,
                },
                "The exact same action was about to repeat.",
            )

            last_signature = None

            if plan:
                print_plan(
                    plan,
                    "📋 NEW PLAN — CURRENT CONTEXT",
                )

            continue

        last_signature = signature

        # Validate click/type targets after navigation.
        if action in {
            "CLICK_TEXT",
            "CLICK_HREF",
            "TYPE_TEXT",
        }:
            if not target_visible(action, args):
                print(
                    "👀 Planned target is not on the current page."
                )
                print(
                    "🧠 Re-understanding the current context..."
                )

                if replans >= MAX_REPLANS:
                    print("❌ Maximum replans reached.")
                    add_history(
                        CURRENT_COMMAND,
                        "Target disappeared and replanning failed.",
                    )
                    return

                replans += 1

                new_plan = replan_after_failure(
                    CURRENT_COMMAND,
                    {
                        "action": action,
                        "args": args,
                    },
                    "The planned target is not visible on the current page.",
                )

                if not new_plan:
                    print("❌ Could not create a new plan.")
                    add_history(
                        CURRENT_COMMAND,
                        "Could not replan.",
                    )
                    return

                plan = new_plan

                last_signature = None

                print_plan(
                    plan,
                    "📋 NEW PLAN — CURRENT CONTEXT",
                )

                continue

        print(
            f"⚡ STEP {executed_actions + 1}: {action}"
        )

        if args:
            print(
                "   ",
                json.dumps(
                    args,
                    ensure_ascii=False,
                ),
            )

        before = page_identity()

        ok, result = execute_action(
            action,
            args,
        )

        executed_actions += 1

        if ok:
            print("   ✅", result)
            if action not in {"DONE", "ANSWER"}:
                successful_actions.append({"action": action, "args": args})
            task_result = str(result)
        else:
            task_result = str(result)
            print("   ❌", result)

            # Infrastructure/thread failures cannot be repaired by choosing
            # another browser selector. Stop instead of looping.
            low_result = str(result).lower()
            infrastructure_error = any(term in low_result for term in (
                "cannot switch to a different thread",
                "thread which happens to have exited",
                "playwright",
                "target page, context or browser has been closed",
            ))
            if infrastructure_error:
                # We already attempted automatic recovery before each action and
                # OPEN_URL retries once. If the failure persists, stop clearly
                # rather than letting the model loop on a dead Playwright page.
                print("🛑 Browser infrastructure failure — automatic recovery did not resolve it.")
                print("❌ Task stopped. Check Brave/Playwright and try the command again.")
                add_history(CURRENT_COMMAND, result)
                return

            if replans >= MAX_REPLANS:
                print("❌ Maximum replans reached.")
                add_history(CURRENT_COMMAND, result)
                return

            replans += 1

            print()
            print("🧠 Action failed — re-understanding context...")
            print("🔄 Rethinking from the current page...")

            new_plan = replan_after_failure(
                CURRENT_COMMAND,
                {
                    "action": action,
                    "args": args,
                },
                result,
            )

            if not new_plan:
                print("❌ Could not create a new plan.")
                add_history(CURRENT_COMMAND, result)
                return

            plan = new_plan
            last_signature = None

            print_plan(
                plan,
                "📋 NEW PLAN — CURRENT CONTEXT",
            )

            continue

        # ----------------------------------------------------
        # ANSWER / DONE
        # ----------------------------------------------------

        if action == "ANSWER":
            print()
            print("📌 ANSWER")
            print(result)
            print()
            print("🎉 Task complete.")

            add_history(
                CURRENT_COMMAND,
                result,
            )
            task_status = "done"
            task_result = str(result)
            _remember_completed_task(CURRENT_COMMAND, task_result, task_status, task_start_url, page_identity(), successful_actions)

            break

        if action == "DONE":
            print()
            print("🎉 Task complete.")

            add_history(
                CURRENT_COMMAND,
                result,
            )
            task_status = "done"
            task_result = str(result)
            _maybe_save_safe_task_recipe(CURRENT_COMMAND, successful_actions, task_start_url, page_identity())
            _remember_completed_task(CURRENT_COMMAND, task_result, task_status, task_start_url, page_identity(), successful_actions)

            break

        # ----------------------------------------------------
        # If a navigation action changed the page, validate the
        # next planned action. We do NOT call Qwen unless needed.
        # ----------------------------------------------------

        after = page_identity()

        if before != after:
            tiny_wait()

            if plan:
                next_step = plan[0]

                if isinstance(next_step, dict):
                    next_action = str(
                        next_step.get("action", "")
                    ).upper().strip()

                    next_args = next_step.get(
                        "args",
                        {},
                    )

                    if not isinstance(next_args, dict):
                        next_args = {}

                    if next_action in {
                        "CLICK_TEXT",
                        "CLICK_HREF",
                        "TYPE_TEXT",
                    }:
                        if not target_visible(
                            next_action,
                            next_args,
                        ):
                            print(
                                "👀 Page changed; old target is invalid."
                            )
                            print(
                                "🧠 Re-understanding the new page..."
                            )

                            if replans >= MAX_REPLANS:
                                print(
                                    "❌ Maximum replans reached."
                                )
                                add_history(
                                    CURRENT_COMMAND,
                                    "Page changed and replanning stopped.",
                                )
                                return

                            replans += 1

                            new_plan = replan_after_failure(
                                CURRENT_COMMAND,
                                {
                                    "action": next_action,
                                    "args": next_args,
                                },
                                (
                                    "The browser page changed and the "
                                    "next planned target is no longer "
                                    "visible. Use the current page and "
                                    "conversation context to continue "
                                    "toward the same goal."
                                ),
                            )

                            if not new_plan:
                                print(
                                    "❌ Could not create a new plan."
                                )
                                add_history(
                                    CURRENT_COMMAND,
                                    "Could not replan after navigation.",
                                )
                                return

                            plan = new_plan
                            last_signature = None

                            print_plan(
                                plan,
                                "📋 NEW PLAN — CURRENT CONTEXT",
                            )

    else:
        if not stop_event.is_set() and not exit_event.is_set():
            if not plan:
                print("🎉 Task complete.")
            elif executed_actions >= MAX_ACTIONS:
                print("⚠️ Maximum actions reached.")

    elapsed = time.time() - start_time

    print()
    if task_status != "done":
        if stop_event.is_set() or exit_event.is_set():
            task_status = "stopped"
        if not task_result:
            task_result = "Task ended without an explicit DONE/ANSWER action."
        _remember_completed_task(CURRENT_COMMAND, task_result, task_status, task_start_url, page_identity(), successful_actions)

    print(f"⏱️ Time: {elapsed:.1f}s")
    print("=" * 64)
    print()


# ============================================================
# AGENT CONTROL
# ============================================================

def start_agent():
    stop_event.clear()
    exit_event.clear()
    return start_browser()


def send_command(command):
    command = str(command).strip()

    if not command or exit_event.is_set():
        return

    run_task(command)


def stop_agent():
    stop_event.set()


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print(
        "╔════════════════════════════════════════════════════════════╗"
    )
    print(
        "║                 🤖 AI BROWSER AGENT                       ║"
    )
    print(
        "║                                                            ║"
    )
    print(
        "║          Qwen3 8B + Playwright + Brave                    ║"
    )
    print(
        "║                                                            ║"
    )
    print(
        "║             GENERAL-PURPOSE AGENT                         ║"
    )
    print(
        "╚════════════════════════════════════════════════════════════╝"
    )
    print()

    print("Commands:")
    print("  • Type any browser task normally")
    print("  • ESC = stop current task")
    print("  • ESC again = close agent")
    print("  • exit / quit = close agent")
    print()

    if not start_agent():
        print("❌ Browser could not start.")
        return

    try:
        while not exit_event.is_set():
            try:
                command = input("🤖 > ").strip()

            except EOFError:
                break

            except KeyboardInterrupt:
                print()
                break

            if not command:
                continue

            if command.lower() in {
                "exit",
                "quit",
                "close",
                "stop agent",
            }:
                print("👋 Closing agent...")
                break

            send_command(command)

    finally:
        print()
        print("🧹 Closing browser...")
        close_browser()
        print("👋 Agent closed.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

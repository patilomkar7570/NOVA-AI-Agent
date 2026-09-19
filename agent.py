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
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "brave.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.30)
    except Exception:
        pass


def start_browser():
    global _browser_context, _page, _playwright, _listener

    if _page is not None:
        return True

    try:
        os.makedirs(PROFILE_PATH, exist_ok=True)

        # Only done when the agent itself starts.
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
        print(f"❌ Could not start Brave:\n{e}")
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


def history_for_qwen():
    if not CONVERSATION_HISTORY:
        return "No previous conversation."

    lines = []

    for item in CONVERSATION_HISTORY:
        lines.append("USER: " + item["user"])

        if item["result"]:
            lines.append("AGENT RESULT: " + item["result"][:500])

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
                        el.innerText ||
                        el.getAttribute("aria-label") ||
                        el.getAttribute("title")
                    );

                    if (!text) continue;

                    buttons.push({
                        text: text.slice(0, 120),
                        aria: clean(
                            el.getAttribute("aria-label")
                        ).slice(0, 120)
                    });
                }

                for (const el of document.querySelectorAll(
                    'input,textarea,select,[contenteditable="true"]'
                )) {
                    if (!visible(el)) continue;

                    inputs.push({
                        type: (
                            el.getAttribute("type") ||
                            el.tagName.toLowerCase()
                        ),
                        placeholder: clean(
                            el.getAttribute("placeholder")
                        ).slice(0, 100),
                        aria: clean(
                            el.getAttribute("aria-label")
                        ).slice(0, 100),
                        name: clean(
                            el.getAttribute("name")
                        ).slice(0, 80)
                    });
                }

                return {
                    text: clean(document.body.innerText).slice(0, 1800),
                    links: links.slice(0, 35),
                    buttons: buttons.slice(0, 16),
                    inputs: inputs.slice(0, 10)
                };
            }
            """
        )

        if isinstance(data, dict):
            result.update(data)

    except Exception:
        pass

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
            const clean = s => (s || "").replace(/\\s+/g, " ").trim();

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
                        if (q && /^https?:\\/\\//i.test(q)) return q;
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

    if _page is None:
        return False, "Browser unavailable."

    url = str(url).strip()

    if not url:
        return False, "No URL provided."

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        _page.goto(
            url,
            wait_until="commit",
            timeout=NAV_TIMEOUT,
        )
        tiny_wait()
        update_active_site(url)
        return True, f"Opened {url}"

    except Exception as e:
        return False, f"Navigation failed: {e}"


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

    text = str(text).strip()

    if not text:
        return False, "No target text."

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
            strategy()
            tiny_wait()

            kind = (
                "link"
                if i == 0
                else "button"
                if i == 1
                else "text"
            )

            return True, f"Clicked {kind}: {text}"
        except Exception:
            pass

    return False, f"Could not find clickable target: {text}"


def click_href(href):
    if _page is None:
        return False, "Browser unavailable."

    href = str(href).strip()

    if not href:
        return False, "No href."

    try:
        locator = _page.locator(
            f'a[href="{href}"]'
        ).first

        locator.click(timeout=CLICK_TIMEOUT)
        tiny_wait()

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

        try:
            _page.get_by_placeholder(
                target,
                exact=True,
            ).first.fill(
                text,
                timeout=TYPE_TIMEOUT,
            )
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

                        if (
                            text === wanted ||
                            text.includes(wanted)
                        ) return true;
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
- Do NOT turn generic "search for X" into Google just because "search" is present.
- Do NOT search Google to discover a website URL. Website destinations are resolved by NOVA/Qwen before planning.
- If the user asks to open/click a named section, tab, menu, or page, first check whether that target is visibly present on the CURRENT PAGE. If it is visible, click it. If it is not visible, use current page + conversation context to decide what to do; do not invent a destination.
- "open Shorts section" means first look for a visible Shorts control/section on the current page.
- Do not use SEARCH_WEB for a section that is already visible on the current page.
- Do not use SEARCH_WEB merely because you are confused about a follow-up
  that can be solved from the current page.

FAST RULES:
- Make the shortest realistic plan.
- Usually make 1-4 actions.
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

    prompt = f"""
ORIGINAL USER REQUEST:
{command}

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

    if action == "OPEN_URL":
        return open_url(args.get("url", ""))

    if action == "SEARCH_WEB":
        return search_web(args.get("query", ""))

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

    # Exact visible clicks: safe and much faster than asking Qwen to plan.
    m = re.match(r"^(?:click|press)\s+(.+)$", lower)
    if m:
        target = text.split(None, 1)[1].strip()
        if target and visible_target_text(target):
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

        # For another known active website, let Qwen use the current
        # page and choose the correct site's search UI.
        return None

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

    # --------------------------------------------------------
    # Fast path for truly unambiguous commands.
    # Generic "open X" deliberately goes to Qwen because X may
    # be a destination OR a contextual instruction.
    # --------------------------------------------------------

    plan = fast_command(CURRENT_COMMAND)
    if not plan:
        plan = obvious_command(CURRENT_COMMAND)

    if plan:
        print("⚡ Direct action")
    else:
        print("👀 Observing page...")
        print("🧠 Qwen understanding context...")
        plan = create_plan(CURRENT_COMMAND)

    if not plan:
        print("❌ No usable plan.")
        add_history(CURRENT_COMMAND, "No usable plan.")
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
        else:
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
                print("🛑 Browser infrastructure failure — stopping task.")
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

            break

        if action == "DONE":
            print()
            print("🎉 Task complete.")

            add_history(
                CURRENT_COMMAND,
                result,
            )

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

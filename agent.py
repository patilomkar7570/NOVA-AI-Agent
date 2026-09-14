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

BRAVE_PATH = (
    r"C:\Users\dudha\AppData\Local\BraveSoftware\Brave-Browser"
    r"\Application\brave.exe"
)

PROFILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "BraveAgentProfile",
)

MODEL = "qwen3:8b"

# Keep these modest: the goal is fast planning, not endless reasoning.
MAX_ACTIONS = 10
MAX_REPLANS = 2

PAGE_TEXT_LIMIT = 1800
MAX_LINKS = 35
MAX_BUTTONS = 16
MAX_INPUTS = 10

QWEN_CONTEXT = 3072
QWEN_TOKENS = 120

CLICK_TIMEOUT = 1200
TYPE_TIMEOUT = 1200
NAV_TIMEOUT = 8000
RENDER_WAIT = 0.12

# Number of previous user/agent turns supplied to Qwen.
CONTEXT_TURNS = 6

# ============================================================
# DIRECT WEBSITE SHORTCUTS
# ============================================================

DIRECT_WEBSITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "google docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com",
    "google slides": "https://slides.google.com",
    "google maps": "https://maps.google.com",
    "google photos": "https://photos.google.com",
    "google translate": "https://translate.google.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "linkedin": "https://www.linkedin.com",
    "pinterest": "https://www.pinterest.com",
    "tiktok": "https://www.tiktok.com",
    "discord": "https://discord.com",
    "twitch": "https://www.twitch.tv",
    "wikipedia": "https://www.wikipedia.org",
    "amazon": "https://www.amazon.com",
    "ebay": "https://www.ebay.com",
    "walmart": "https://www.walmart.com",
    "flipkart": "https://www.flipkart.com",
    "myntra": "https://www.myntra.com",
    "meesho": "https://www.meesho.com",
    "etsy": "https://www.etsy.com",
    "best buy": "https://www.bestbuy.com",
    "ikea": "https://www.ikea.com",
    "netflix": "https://www.netflix.com",
    "prime video": "https://www.primevideo.com",
    "disney plus": "https://www.disneyplus.com",
    "hulu": "https://www.hulu.com",
    "max": "https://www.max.com",
    "spotify": "https://open.spotify.com",
    "apple music": "https://music.apple.com",
    "soundcloud": "https://soundcloud.com",
    "imdb": "https://www.imdb.com",
    "letterboxd": "https://letterboxd.com",
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "stackoverflow": "https://stackoverflow.com",
    "python": "https://www.python.org",
    "pypi": "https://pypi.org",
    "npm": "https://www.npmjs.com",
    "docker": "https://www.docker.com",
    "kaggle": "https://www.kaggle.com",
    "replit": "https://replit.com",
    "codepen": "https://codepen.io",
    "microsoft": "https://www.microsoft.com",
    "microsoft 365": "https://www.microsoft365.com",
    "outlook": "https://outlook.live.com",
    "onedrive": "https://onedrive.live.com",
    "bing": "https://www.bing.com",
    "teams": "https://teams.microsoft.com",
    "office": "https://www.office.com",
    "apple": "https://www.apple.com",
    "icloud": "https://www.icloud.com",
    "samsung": "https://www.samsung.com",
    "openai": "https://openai.com",
    "chatgpt": "https://chatgpt.com",
    "anthropic": "https://www.anthropic.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "perplexity": "https://www.perplexity.ai",
    "hugging face": "https://huggingface.co",
    "ollama": "https://ollama.com",
    "midjourney": "https://www.midjourney.com",
    "canva": "https://www.canva.com",
    "nvidia": "https://www.nvidia.com",
    "amd": "https://www.amd.com",
    "intel": "https://www.intel.com",
    "lenovo": "https://www.lenovo.com",
    "hp": "https://www.hp.com",
    "dell": "https://www.dell.com",
    "asus": "https://www.asus.com",
    "acer": "https://www.acer.com",
    "logitech": "https://www.logitech.com",
    "razer": "https://www.razer.com",
    "minecraft": "https://www.minecraft.net",
    "curseforge": "https://www.curseforge.com",
    "modrinth": "https://modrinth.com",
    "steam": "https://store.steampowered.com",
    "epic games": "https://store.epicgames.com",
    "xbox": "https://www.xbox.com",
    "playstation": "https://www.playstation.com",
    "roblox": "https://www.roblox.com",
    "ea": "https://www.ea.com",
    "ubisoft": "https://www.ubisoft.com",
    "cloudflare": "https://www.cloudflare.com",
    "oracle": "https://www.oracle.com",
    "adobe": "https://www.adobe.com",
    "dropbox": "https://www.dropbox.com",
    "notion": "https://www.notion.so",
    "trello": "https://trello.com",
    "zoom": "https://zoom.us",
    "coursera": "https://www.coursera.org",
    "udemy": "https://www.udemy.com",
    "w3schools": "https://www.w3schools.com",
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
            keep_alive="10m",
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
    """Hard-wired Google first-result click. Never asks Qwen to choose."""
    global _page

    if _page is None:
        return False, "Browser unavailable."

    try:
        try:
            _page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        time.sleep(1.0)

        # Google result titles are H3 elements. We deliberately start from
        # the first H3 inside the main search-results area and walk UP to
        # its containing <a>. This avoids accidentally clicking a random
        # Google link such as Images, Maps, Sign in, etc.
        h3_selectors = [
            '#search h3',
            'div#rso h3',
            'main h3',
        ]

        for h3_selector in h3_selectors:
            h3s = _page.locator(h3_selector)
            count = h3s.count()

            for i in range(min(count, 20)):
                h3 = h3s.nth(i)
                try:
                    if not h3.is_visible():
                        continue

                    title = (h3.inner_text() or '').strip()
                    if not title:
                        continue

                    # The result title itself is inside the clickable <a>.
                    link = h3.locator('xpath=ancestor::a[1]')
                    if link.count() == 0:
                        continue
                    link = link.first
                    if not link.is_visible():
                        continue

                    # Skip obvious sponsored blocks.
                    try:
                        block = h3.locator(
                            'xpath=ancestor::*[@id="tads" or @id="tadblock"][1]'
                        )
                        if block.count() and block.first.is_visible():
                            continue
                    except Exception:
                        pass

                    # Also skip anything explicitly marked sponsored.
                    try:
                        txt = link.locator('xpath=ancestor::*[self::div or self::li][1]').inner_text().lower()
                        if 'sponsored' in txt or 'sponsored' in txt:
                            continue
                    except Exception:
                        pass

                    # THIS IS THE IMPORTANT PART: click the exact first
                    # organic result's <a>, not an arbitrary discovered URL.
                    link.scroll_into_view_if_needed(timeout=2000)
                    link.click(timeout=5000, force=False)

                    try:
                        _page.wait_for_load_state('domcontentloaded', timeout=7000)
                    except Exception:
                        pass
                    time.sleep(0.5)

                    return True, f'Clicked first Google result: {title[:180]}'
                except Exception:
                    continue

        return False, 'Could not locate Google result H3/link.'

    except Exception as e:
        return False, f'Could not click first Google result: {e}'

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
- Never invent refs, URLs, shell commands, PowerShell, or Python.
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
        return answer_from_page(CURRENT_COMMAND)

    if action == "DONE":
        return True, "Task complete."

    return False, f"Unknown action: {action}"


# ============================================================
# VERY FAST UNIVERSAL COMMAND SHORTCUTS
# ============================================================

def direct_website_command(command):
    text = str(command).strip()
    lower = text.lower()

    prefixes = (
        "open website ",
        "go to website ",
        "visit website ",
        "open ",
        "go to ",
        "visit ",
    )

    for prefix in prefixes:
        if lower.startswith(prefix):
            name = text[len(prefix):].strip().lower()
            name = re.sub(r"\s+(website|site|domain)$", "", name, flags=re.IGNORECASE).strip()
            name = name.rstrip(".")

            if name in DIRECT_WEBSITES:
                return DIRECT_WEBSITES[name]

    return None


def obvious_command(command):
    """
    Only handles commands whose meaning is unambiguous WITHOUT Qwen.

    IMPORTANT:
    "open the first video" is NOT treated as a destination.
    Contextual commands go through Qwen so the current page/history can
    determine what the user means.
    """

    text = command.strip()
    lower = text.lower()

    # Known websites open directly without Google or Qwen.
    direct_url = direct_website_command(command)
    if direct_url:
        return [
            {"action": "OPEN_URL", "args": {"url": direct_url}},
            {"action": "DONE", "args": {}},
        ]

    # Explicit full URL.
    for prefix in (
        "open https://",
        "go to https://",
        "visit https://",
        "open http://",
        "go to http://",
        "visit http://",
    ):
        if lower.startswith(prefix):
            url = text[len(prefix):].strip()

            return [
                {
                    "action": "OPEN_URL",
                    "args": {"url": url},
                },
                {
                    "action": "DONE",
                    "args": {},
                },
            ]

    # Exact YouTube destination.
    if lower in {
        "open youtube",
        "go to youtube",
        "visit youtube",
        "open youtube.com",
        "go to youtube.com",
        "visit youtube.com",
    }:
        return [
            {
                "action": "OPEN_URL",
                "args": {
                    "url": "https://www.youtube.com"
                },
            },
            {
                "action": "DONE",
                "args": {},
            },
        ]

    # Explicit YouTube search.
    youtube_prefixes = (
        "search youtube for ",
        "search youtube ",
        "youtube search for ",
        "youtube search ",
    )

    for prefix in youtube_prefixes:
        if lower.startswith(prefix):
            query = text[len(prefix):].strip()
            query = re.sub(r"\s+(?:website|site|domain)$", "", query, flags=re.IGNORECASE).strip()

            if query:
                return [
                    {
                        "action": "SEARCH_YOUTUBE",
                        "args": {"query": query},
                    },
                    {
                        "action": "DONE",
                        "args": {},
                    },
                ]

    # Explicit Google/web search.
    search_prefixes = (
        "search google for ",
        "search the web for ",
        "search web for ",
        "search google ",
        "search the web ",
        "search web ",
    )

    for prefix in search_prefixes:
        if lower.startswith(prefix):
            query = text[len(prefix):].strip()

            if query:
                return [
                    {
                        "action": "SEARCH_WEB",
                        "args": {"query": query},
                    },
                    {
                        "action": "DONE",
                        "args": {},
                    },
                ]

    # Generic named destinations:
    # If the user explicitly asks to OPEN / GO TO / VISIT a named thing,
    # search for that name in the browser and automatically open the first
    # organic result. This is intentionally generic — no website-specific
    # hardcoding and no hidden/background search.
    #
    # Contextual phrases such as "open it", "open the first video",
    # "open the first link", etc. are NOT handled here; they go to Qwen so
    # current-page state + recent conversation can determine the target.
    destination_prefixes = (
        "open ",
        "go to ",
        "visit ",
        "open website ",
        "go to website ",
        "visit website ",
    )

    contextual_prefixes = (
        "open it",
        "open that",
        "open this",
        "open the first",
        "open first",
        "open second",
        "open third",
        "click it",
        "click that",
        "click this",
        "go back and open",
        "then open",
    )

    if any(lower.startswith(p) for p in contextual_prefixes):
        return None

    for prefix in destination_prefixes:
        if lower.startswith(prefix):
            query = text[len(prefix):].strip()

            if query:
                return [
                    {
                        "action": "SEARCH_WEB",
                        "args": {"query": query},
                    },
                    {
                        "action": "OPEN_FIRST_ORGANIC_RESULT",
                        "args": {},
                    },
                    {
                        "action": "DONE",
                        "args": {},
                    },
                ]

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

    if not start_browser():
        return

    # --------------------------------------------------------
    # Fast path for truly unambiguous commands.
    # Generic "open X" deliberately goes to Qwen because X may
    # be a destination OR a contextual instruction.
    # --------------------------------------------------------

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

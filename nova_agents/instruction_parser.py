"""Dynamic natural language instruction parser for NOVA AI Agent.

Dissects conversational user requests into typed, structured execution intents:
- Identifies requested application (Word, Notepad, Browser, Excel, etc.)
- Separates conversational framing ("okay now", "could you please", etc.)
- Decouples task topic and content payloads from application targets
- Extracts explicit length constraints (e.g. "of 100 lines", "5 paragraphs")
- Identifies save operations and target filenames
- Detects non-application natural prepositions (e.g. "on inflation in developing countries")
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

PREFIX_RE = re.compile(
    r"^(?:(?:okay|ok|alright|so|now|please|then|can\s+you|could\s+you|would\s+you|will\s+you|hey\s+nova|hi\s+nova|hello\s+nova)\b[\s,\.!\?]*)+",
    re.IGNORECASE,
)

SUFFIX_RE = re.compile(
    r"(?:[\s,]+(?:bro+|mate|dude|man|thanks|thank\s+you|please|pls|yo|okay|ok))+[\.\?!]*$",
    re.IGNORECASE,
)

KNOWN_APPS: dict[str, list[str]] = {
    "word": ["word", "winword", "microsoft word", "ms word", "doc", "docs", "docx"],
    "notepad": ["notepad", "notes", "text editor", "textedit"],
    "browser": ["browser", "chrome", "edge", "firefox", "brave", "web browser", "the browser", "internet"],
    "excel": ["excel", "spreadsheet", "sheets", "ms excel", "microsoft excel"],
    "powerpoint": ["powerpoint", "ppt", "presentation", "slides", "ms powerpoint"],
    "calculator": ["calculator", "calc"],
    "explorer": ["explorer", "file explorer", "files"],
    "paint": ["paint", "mspaint"],
    "terminal": ["terminal", "cmd", "powershell", "command prompt", "wt"],
    "discord": ["discord"],
    "whatsapp": ["whatsapp"],
    "telegram": ["telegram"],
    "spotify": ["spotify"],
    "slack": ["slack"],
    "vlc": ["vlc", "vlc media player"],
    "voicebox": ["voicebox", "voice box"],
    "photoshop": ["photoshop", "adobe photoshop"],
    "blender": ["blender"],
    "obs": ["obs", "obs studio", "obs64"],
    "steam": ["steam"],
    "zoom": ["zoom"],
    "teams": ["teams", "microsoft teams"],
    "firefox": ["firefox", "mozilla firefox"],
}


@dataclass
class ParsedInstruction:
    raw_command: str
    clean_command: str = ""
    application: str | None = None
    objective: str = ""
    content_topic: str | None = None
    content_type: str | None = None
    length_constraints: dict[str, Any] = field(default_factory=dict)
    required_actions: list[str] = field(default_factory=list)
    save_required: bool = False
    save_path: str | None = None
    is_computer_action: bool = False
    is_browser_action: bool = False
    is_creative_generation: bool = False
    is_system_control: bool = False
    system_action: str | None = None
    system_arg: Any = None
    is_screenshot: bool = False
    recipient: str | None = None
    message_payload: str | None = None
    is_messaging_action: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "application": self.application,
            "objective": self.objective,
            "content_topic": self.content_topic,
            "content_type": self.content_type,
            "length_constraints": self.length_constraints,
            "required_actions": list(self.required_actions),
            "save_required": self.save_required,
            "save_path": self.save_path,
            "is_computer_action": self.is_computer_action,
            "is_browser_action": self.is_browser_action,
            "is_creative_generation": self.is_creative_generation,
            "is_system_control": self.is_system_control,
            "system_action": self.system_action,
            "system_arg": self.system_arg,
            "is_screenshot": self.is_screenshot,
            "recipient": self.recipient,
            "message_payload": self.message_payload,
            "is_messaging_action": self.is_messaging_action,
        }


def resolve_known_app(token: str | None) -> str | None:
    """Normalize and validate whether a token refers to a known desktop or browser application."""
    if not token:
        return None
    clean = re.sub(r"^(?:the\s+)", "", token.strip(), flags=re.IGNORECASE)
    clean = re.sub(r"\s+(?:app|application|program)$", "", clean, flags=re.IGNORECASE).strip().lower()
    for canon, aliases in KNOWN_APPS.items():
        if clean == canon or clean in aliases:
            return canon
    return None


def is_probable_application_name(token: str | None) -> bool:
    """Check if token is genuinely an application name and not a topic or common preposition object."""
    if not token:
        return False
    return resolve_known_app(token) is not None


def strip_conversational_prefixes(command: str) -> str:
    """Remove natural language conversational prefixes, courtesy phrases, and trailing conversational noise cleanly."""
    cmd = str(command or "").strip()
    cmd = PREFIX_RE.sub("", cmd).strip()
    cmd = SUFFIX_RE.sub("", cmd).strip()
    return cmd


def parse_instruction(raw_command: str) -> ParsedInstruction:
    """Parse a user command into a structured, validated instruction object."""
    cmd = str(raw_command or "").strip()
    clean_cmd = strip_conversational_prefixes(cmd)
    clean_cmd = clean_cmd.rstrip(".!?")

    parsed = ParsedInstruction(raw_command=raw_command, clean_command=clean_cmd, objective=cmd)

    # 0a. Check Screenshot Intent (e.g. "take a screenshot", "capture screen", "what's on my screen")
    screenshot_match = re.search(
        r"^(?:(?:can\s+you|could\s+you|please|hey\s+nova)\s+)?(?:take\s+(?:a\s+)?screenshot|capture\s+(?:the\s+)?(?:screen|desktop)|screenshot(?:\s+(?:the|my)\s+(?:screen|desktop))?|what(?:'?s|\s+is)\s+on\s+(?:the|my)\s+screen)$",
        clean_cmd,
        re.IGNORECASE,
    )
    if screenshot_match:
        parsed.is_screenshot = True
        parsed.is_computer_action = True
        parsed.required_actions = ["capture_screenshot"]
        return parsed

    # 0b. Check System Hardware / Media / Desktop Controls (inspired by Mark-XXXIX-OR)
    # Volume controls:
    if re.search(r"^(?:please\s+)?(?:mute|silence)(?:\s+(?:the\s+)?(?:system|audio|sound|volume|pc|computer))?$", clean_cmd, re.I):
        parsed.is_system_control = True
        parsed.system_action = "volume_mute"
        parsed.is_computer_action = True
        parsed.required_actions = ["volume_mute"]
        return parsed

    if re.search(r"^(?:please\s+)?(?:unmute)(?:\s+(?:the\s+)?(?:system|audio|sound|volume|pc|computer))?$", clean_cmd, re.I):
        parsed.is_system_control = True
        parsed.system_action = "volume_unmute"
        parsed.is_computer_action = True
        parsed.required_actions = ["volume_unmute"]
        return parsed

    if re.search(r"^(?:please\s+)?(?:volume\s+up|turn\s+up(?:\s+the)?\s+volume|increase(?:\s+the)?\s+volume|raise(?:\s+the)?\s+volume|louder)$", clean_cmd, re.I):
        parsed.is_system_control = True
        parsed.system_action = "volume_up"
        parsed.is_computer_action = True
        parsed.required_actions = ["volume_up"]
        return parsed

    if re.search(r"^(?:please\s+)?(?:volume\s+down|turn\s+down(?:\s+the)?\s+volume|decrease(?:\s+the)?\s+volume|lower(?:\s+the)?\s+volume|softer|quieter)$", clean_cmd, re.I):
        parsed.is_system_control = True
        parsed.system_action = "volume_down"
        parsed.is_computer_action = True
        parsed.required_actions = ["volume_down"]
        return parsed

    # Media controls:
    if re.search(r"^(?:please\s+)?(?:pause(?:\s+music|\s+song|\s+audio|\s+playback)?|play(?:\s+music|\s+song|\s+audio|\s+playback)?|resume(?:\s+music|\s+playback)?|toggle\s+playback)$", clean_cmd, re.I):
        parsed.is_system_control = True
        parsed.system_action = "media_play_pause"
        parsed.is_computer_action = True
        parsed.required_actions = ["media_play_pause"]
        return parsed

    if re.search(r"^(?:please\s+)?(?:next\s+(?:track|song|music)|skip(?:\s+(?:track|song|this))?)$", clean_cmd, re.I):
        parsed.is_system_control = True
        parsed.system_action = "media_next"
        parsed.is_computer_action = True
        parsed.required_actions = ["media_next"]
        return parsed

    if re.search(r"^(?:please\s+)?(?:previous\s+(?:track|song|music)|prev\s+(?:track|song)|back\s+(?:a\s+)?track)$", clean_cmd, re.I):
        parsed.is_system_control = True
        parsed.system_action = "media_prev"
        parsed.is_computer_action = True
        parsed.required_actions = ["media_prev"]
        return parsed

    if re.search(r"^(?:please\s+)?(?:stop\s+(?:music|playback|song|audio))$", clean_cmd, re.I):
        parsed.is_system_control = True
        parsed.system_action = "media_stop"
        parsed.is_computer_action = True
        parsed.required_actions = ["media_stop"]
        return parsed

    # Desktop & Workstation controls:
    if re.search(r"^(?:please\s+)?(?:show(?:\s+(?:the|my))?\s+desktop|minimize\s+all(?:\s+windows)?|go\s+to(?:\s+(?:the|my))?\s+desktop)$", clean_cmd, re.I):
        parsed.is_system_control = True
        parsed.system_action = "show_desktop"
        parsed.is_computer_action = True
        parsed.required_actions = ["show_desktop"]
        return parsed

    if re.search(r"^(?:please\s+)?(?:lock(?:\s+(?:the|my))?\s+(?:screen|pc|workstation|computer)|lock\s+(?:screen|pc|workstation|computer)|lock)$", clean_cmd, re.I):
        parsed.is_system_control = True
        parsed.system_action = "lock_workstation"
        parsed.is_computer_action = True
        parsed.required_actions = ["lock_workstation"]
        return parsed

    # 1. Extract Length Constraints (e.g., "of 100 lines", "100 lines", "5 paragraphs", "500 words")
    len_match = re.search(r"\b(?:of\s+)?(\d+)\s+(lines?|paragraphs?|words?|pages?)\b", clean_cmd, re.IGNORECASE)
    if len_match:
        qty = int(len_match.group(1))
        unit = len_match.group(2).lower().rstrip("s") + "s"
        parsed.length_constraints[unit] = qty

    # 2. Extract Save Requirements (e.g. "and save it in Word", "and save it as ...", "save as ...")
    save_match = re.search(
        r"\b(?:and\s+)?save\s+(?:it\s+)?(?:in|to|as)?\s*([a-zA-Z0-9_\-\. ]+)?$",
        clean_cmd,
        re.IGNORECASE,
    )
    if save_match:
        parsed.save_required = True
        save_target = (save_match.group(1) or "").strip()
        app_from_save = resolve_known_app(save_target)
        if app_from_save:
            parsed.application = app_from_save
        elif save_target:
            if save_target.lower() not in ("it", "the document", "the file", "this", "file"):
                parsed.save_path = save_target

    # 3. Check Browser and Search Actions
    # e.g., "open the browser and search for the history of Pune", "search for ... on google"
    browser_match = re.search(
        r"\b(?:open\s+(?:the\s+)?(browser|chrome|edge|web)\s+(?:and\s+)?)?(?:search|look\s*up|find)\s+(?:for\s+)?(.+)",
        clean_cmd,
        re.IGNORECASE,
    )
    if browser_match and (browser_match.group(1) or re.search(r"\b(?:browser|google|web|online|search\s+for|history\s+of)\b", clean_cmd, re.IGNORECASE)):
        parsed.is_browser_action = True
        parsed.application = resolve_known_app(browser_match.group(1)) or "browser"
        parsed.content_topic = browser_match.group(2).strip().rstrip(".!?")
        parsed.content_type = "search"
        parsed.required_actions = ["open_browser", "search"]
        return parsed

    # 3b. Check Messaging / Communication actions (e.g. "open <app> and send <text> to <person>")
    msg_match1 = re.search(
        r"^(?:(?:open|launch|start)\s+([a-zA-Z0-9_\-]+)\s+(?:and|,|then)\s+)?(?:send|message|text|dm)\s+[\"']?(.*?)[\"']?\s+to\s+(?:my\s+(?:friend|mate|brother|sister|colleague)\s+)?([a-zA-Z0-9_\- ]+?)(?:\s+(?:on|in|via|through)\s+([a-zA-Z0-9_\-]+))?$",
        clean_cmd,
        re.I,
    )
    if msg_match1:
        app_cand = msg_match1.group(1) or msg_match1.group(4)
        msg_text = (msg_match1.group(2) or "").strip()
        recipient = (msg_match1.group(3) or "").strip()
        target_app = resolve_known_app(app_cand) if app_cand else (app_cand.lower().strip() if app_cand else None)
        if target_app:
            parsed.application = target_app
            parsed.recipient = recipient
            parsed.message_payload = msg_text or "hello"
            parsed.is_messaging_action = True
            parsed.is_computer_action = True
            parsed.required_actions = ["open_app", "send_message"]
            return parsed

    # 4. Check Document / Writing Actions
    # Check leading application: "open <app> and ..."
    leading_app_match = re.search(
        r"^(?:open|launch|start|run)\s+(?:the\s+)?([a-zA-Z0-9_\- ]+?)\s+(?:and|,|then)\s+(.+)$",
        clean_cmd,
        re.IGNORECASE,
    )
    action_part = clean_cmd
    if leading_app_match:
        app_cand = resolve_known_app(leading_app_match.group(1))
        if app_cand:
            parsed.application = app_cand
            action_part = leading_app_match.group(2).strip()

    # Check trailing application: "... in Notepad", "... into Word"
    trailing_app_match = re.search(
        r"\b(?:in|into|inside)\s+(?:the\s+)?([a-zA-Z0-9_\- ]+?)$",
        action_part,
        re.IGNORECASE,
    )
    if trailing_app_match:
        app_cand = resolve_known_app(trailing_app_match.group(1))
        if app_cand:
            parsed.application = app_cand
            action_part = action_part[:trailing_app_match.start()].strip()

    # Determine content type and topic from action_part
    write_match = re.search(
        r"^(?:write|draft|compose|create|type|make)\s+"
        r"(?:(?:a|an)\s+)?"
        r"(essay|story|letter|report|poem|article|summary|paragraph|notes?|document|speech|review)?\s*"
        r"(?:(on|about|regarding|for)\s+)?"
        r"(.+)$",
        action_part,
        re.IGNORECASE,
    )

    if write_match:
        genre = write_match.group(1)
        prep = write_match.group(2)
        topic_raw = write_match.group(3).strip()

        # Clean length constraints, save clauses, trailing noise or prepositions from topic
        clean_topic = re.sub(r"\b(?:of\s+)?\d+\s+(?:lines?|paragraphs?|words?|pages?)\b", "", topic_raw, flags=re.IGNORECASE)
        clean_topic = re.sub(r"\b(?:and\s+)?save\s+.*$", "", clean_topic, flags=re.IGNORECASE).strip()
        clean_topic = re.sub(r"^(?:on|about|for|regarding)\s+", "", clean_topic, flags=re.IGNORECASE).strip()
        clean_topic = SUFFIX_RE.sub("", clean_topic).strip()
        clean_topic = clean_topic.rstrip(".!?")

        anaphoric_terms = {"it", "it in", "this", "that", "here", "there", "the summary", "the text", "the result", "the data"}
        is_anaphoric = clean_topic.lower() in anaphoric_terms or topic_raw.lower() in anaphoric_terms

        # Genuine creative generation requires either a creative genre (essay, poem, report...)
        # or an explicit topic preposition (on, about, regarding, for), and must not be anaphoric.
        if (genre or prep) and not is_anaphoric:
            parsed.content_type = (genre or "document").lower()
            parsed.content_topic = clean_topic or topic_raw
            parsed.is_creative_generation = True
            parsed.is_computer_action = True
            if not parsed.application:
                parsed.application = "word"  # Default authoring canvas for essays / documents
            parsed.required_actions = ["open_app", "prepare_canvas", "generate_content", "paste_content", "verify_content"]
            if parsed.save_required:
                parsed.required_actions.append("save_document")
                if not parsed.save_path and parsed.content_topic:
                    ext = ".docx" if parsed.application == "word" else ".txt"
                    topic_title = re.sub(r"[^\w\s-]", "", parsed.content_topic).strip().title()
                    parsed.save_path = f"{parsed.content_type.title()} on {topic_title}{ext}"
            return parsed

    # 5. Check Direct Launch Command: "open Word", "launch Notepad"
    launch_match = re.search(r"^(?:open|launch|start|run)\s+(?:the\s+)?([a-zA-Z0-9_\- ]+)$", clean_cmd, re.IGNORECASE)
    if launch_match:
        app_cand = resolve_known_app(launch_match.group(1))
        if app_cand:
            parsed.application = app_cand
            parsed.is_computer_action = True
            parsed.required_actions = ["open_app", "verify_running"]
            return parsed

    # 6. Check Close / Quit Command: "close Word", "quit Notepad"
    close_match = re.search(r"^(?:close|quit|exit|kill)\s+(?:the\s+)?([a-zA-Z0-9_\- ]+)$", clean_cmd, re.IGNORECASE)
    if close_match:
        app_cand = resolve_known_app(close_match.group(1))
        if app_cand:
            parsed.application = app_cand
            parsed.is_computer_action = True
            parsed.required_actions = ["close_app"]
            return parsed

    return parsed

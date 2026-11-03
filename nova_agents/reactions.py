"""Deterministic, zero-LLM reactions for exact, low-risk social utterances.

These are deliberately exact phrase matches after normalisation. NOVA never
swallows a longer command just because it begins with a greeting or contains a
word such as "great" or "thanks".
"""
from __future__ import annotations

import re


_WAKE_PREFIX = re.compile(
    r"^(?:(?:hey|hi|hello|yo|okay|ok)\s+)?nova\b[\s,:;.!?\-]*",
    re.IGNORECASE,
)
_TRAILING_NAME = re.compile(r"\s+nova$", re.IGNORECASE)


def _normalise(text: str) -> str:
    value = str(text or "").lower().strip()
    value = value.replace("’", "'").replace("`", "'")
    value = re.sub(r"[!?.,;:]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    # Accept natural wake-word forms such as "Hey NOVA, are you there?" while
    # leaving any action that follows the wake word intact for Qwen to classify.
    without_wake = _WAKE_PREFIX.sub("", value, count=1).strip()
    if without_wake != value:
        value = without_wake or "nova"

    value = _TRAILING_NAME.sub("", value).strip()
    value = value.replace("hows ", "how's ").replace("whats ", "what's ")
    value = value.replace("ur ", "your ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


_REPLIES = {
    # Wake word / presence checks
    "nova": "I'm here! 👋 What can I help you with?",
    "are you there": "I'm here! 👋 What do you need?",
    "you there": "Right here. What's up?",
    "can you hear me": "Loud and clear! 🎙️ I'm listening.",
    "are you listening": "Yes, I'm listening. Go ahead! 👂",
    "testing": "I can hear you. NOVA is ready! ✅",
    "test": "NOVA is here and ready. ✅",

    # Greetings
    "hi": "Hi! 👋 What can I help you with?",
    "hello": "Hello! 👋 What are we working on?",
    "hey": "Hey! 😄 What's up?",
    "heya": "Hey! 😄 What can I do for you?",
    "hii": "Hii! 👋 What can I help with?",
    "yo": "Yo! 😄 What's up?",
    "good morning": "Good morning! ☀️ Ready when you are.",
    "morning": "Morning! ☀️ What are we doing today?",
    "good afternoon": "Good afternoon! 😊 What can I help you with?",
    "good evening": "Good evening! 🌙 What are we working on?",
    "good night": "Good night! 🌙 Rest well. I'll be here when you need me.",

    # Wellbeing / casual check-ins
    "how are you": "I'm doing well and ready to help. How are things with you? 😊",
    "how are you doing": "Doing well! All systems ready. What are we tackling today? 😄",
    "how is your day going": "Pretty good — especially now that we're building NOVA together. 😄 What can I help with?",
    "how's your day going": "Pretty good — especially now that we're building NOVA together. 😄 What can I help with?",
    "hi how's your day going": "I'm doing well, thanks for asking! 😄 What are we working on?",
    "hey how's your day going": "Doing well! 😄 What can I help you with today?",
    "hi how are you": "I'm doing well and ready to help. How are things with you? 😊",
    "how's it going": "Going smoothly over here! 😄 What's up?",
    "what's up": "Not much — I'm ready for whatever we're tackling next. 😄",
    "how's everything": "All systems are ready over here. How about you? 😊",
    "i'm back": "Welcome back! 😄 Where should we pick up?",
    "welcome back": "Good to have you back! What are we working on?",

    # Gratitude
    "thanks": "You're welcome! 😊",
    "thank you": "You're very welcome!",
    "thanks a lot": "Anytime! Happy to help. 😊",
    "thank you so much": "You're very welcome! Glad I could help. 😊",
    "thanks so much": "You're very welcome! 😊",
    "thx": "Anytime! 😊",
    "ty": "You're welcome!",
    "appreciate it": "Anytime — happy to help! 😊",

    # Acknowledgements (exact matches only)
    "ok": "Got it. 👍",
    "okay": "Alright! 👍",
    "got it": "Perfect — we're on the same page.",
    "understood": "Understood. I'll keep that in mind for this task.",
    "cool": "Nice! 😄",
    "great": "Great! What's next?",
    "alright": "Alright. 👍",
    "sounds good": "Sounds good! 👍",
    "perfect": "Perfect! 😄",
    "nice": "Nice! 😄",
    "no problem": "No problem at all! 😊",

    # Goodbye
    "bye": "See you! 👋",
    "goodbye": "Goodbye! Take care. 👋",
    "see you": "See you soon! 👋",
    "see ya": "See ya! 👋",
    "talk later": "Talk later! I'll be here when you need me.",
    "take care": "You too — take care! 👋",
}


def match_reaction(text: str) -> str | None:
    """Return an instant reply only for an exact, low-risk social phrase.

    Prefix/suffix wake-word forms are normalised, but extra meaningful words
    remain, so "Hey NOVA, open YouTube" and "Thanks, explain inflation" are
    intentionally passed to the AI Planner.
    """
    clean = _normalise(text)
    return _REPLIES.get(clean)

"""Single source of truth for specialists enabled in the current NOVA build."""
from __future__ import annotations

from typing import Any


_AGENT_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "id": "reaction",
        "name": "Reaction Agent",
        "description": "Handles exact, low-risk social phrases locally without a model call.",
        "category": "routing",
        "execution": "local",
        "enabled": True,
        "capabilities": ["social_reaction"],
    },
    {
        "id": "chat",
        "name": "Chat Agent",
        "description": "Answers questions, explains concepts and handles conversational tasks.",
        "category": "conversation",
        "execution": "local-model",
        "enabled": True,
        "capabilities": ["conversation", "explanation", "calculation", "writing", "synthesis"],
    },
    {
        "id": "browser",
        "name": "Browser Agent",
        "description": "Controls the dedicated Brave browser through the shared Playwright worker.",
        "category": "browser-automation",
        "execution": "playwright",
        "enabled": True,
        "capabilities": ["browser_navigation", "web_interaction", "page_inspection"],
    },
    {
        "id": "research",
        "name": "Research Agent",
        "description": "Investigates topics and returns source-aware research for synthesis.",
        "category": "research",
        "execution": "local-model-and-web",
        "enabled": True,
        "capabilities": ["web_search", "source_inspection", "evidence_synthesis"],
    },
)


def agent_ids(*, enabled_only: bool = True) -> tuple[str, ...]:
    """Return registered agent identifiers in stable display order."""
    return tuple(
        profile["id"]
        for profile in _AGENT_PROFILES
        if not enabled_only or profile["enabled"]
    )


def agent_catalog() -> list[dict[str, Any]]:
    """Return a JSON-safe copy of the active agent catalog."""
    return [
        {**profile, "capabilities": list(profile.get("capabilities", []))}
        for profile in _AGENT_PROFILES if profile["enabled"]
    ]


def agent_capabilities(agent_id: str) -> frozenset[str]:
    """Return the allow-listed capabilities for one enabled specialist."""
    for profile in _AGENT_PROFILES:
        if profile["id"] == agent_id and profile["enabled"]:
            return frozenset(str(item) for item in profile.get("capabilities", []))
    return frozenset()


def validate_agent_registry() -> None:
    """Fail fast if the registry contains duplicate or malformed identifiers."""
    ids = [profile.get("id") for profile in _AGENT_PROFILES]
    if any(not isinstance(value, str) or not value.strip() for value in ids):
        raise RuntimeError("NOVA agent registry contains an empty or invalid identifier.")
    if len(ids) != len(set(ids)):
        raise RuntimeError("NOVA agent registry contains duplicate identifiers.")
    required = {"id", "name", "description", "category", "execution", "enabled", "capabilities"}
    for profile in _AGENT_PROFILES:
        if not required.issubset(profile):
            raise RuntimeError(f"NOVA agent registry entry is missing fields: {profile!r}")
        if not isinstance(profile["enabled"], bool):
            raise RuntimeError(f"NOVA agent '{profile['id']}' has an invalid enabled flag.")


validate_agent_registry()

"""Deterministic, centrally enforced policy for browser-side effects.

Planner output is never trusted to lower a risk classification. Ambiguous or
negated language remains conservative: NOVA asks for approval rather than trying
to infer that an external action is safe to perform.
"""
from __future__ import annotations

import re
from typing import Any

_CRITICAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("funds_transfer", re.compile(r"\b(wire (?:the )?money|transfer (?:the )?(?:funds|money|cash)|send (?:the )?(?:money|funds)|withdraw (?:cash|funds)|cash advance)\b", re.I)),
    ("high_risk_security_change", re.compile(r"\b(disable|turn off|remove)\b.{0,50}\b(two.factor|2fa|multi.factor authentication|account protection)\b", re.I)),
    ("desktop_system_destruction", re.compile(r"(?:\bformat\s+[a-z]:|\b(?:shutdown(?:\.exe)?|restart(?:-computer)?(?:\.exe)?|taskkill\s+/f|rmdir\s+/s|del\s+/[fsq]|reg\s+(?:delete|add)|regedit|drop\s+database|truncate\s+table)\b)", re.I)),
    ("unrestricted_shell_exec", re.compile(r"\b(?:powershell(?:\.exe)?\s+-(?:e|enc|encodedcommand|c|command)|cmd(?:\.exe)?\s+/[ck]|bash(?:\.exe)?\s+-c)", re.I)),
)

_HIGH_IMPACT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("data_deletion", re.compile(r"\b(delete|remove|erase|wipe|destroy|deactivate|close account)\b", re.I)),
    ("financial", re.compile(r"\b(buy|purchase|checkout|payment|transfer|withdraw|donate|invest|place order)\b|\bpay\s+(?:for|to)\b", re.I)),
    ("external_communication", re.compile(
        r"\b(?:send|compose|dispatch)\s+(?:an?\s+|this\s+)?(?:email|mail|newsletter|message to email)\b|"
        r"\bemail\s+(?:to|send|reply|submit)\b|"
        r"\b(?:publish|post)\s+(?:a\s+|an?\s+)?(?:tweet|article|blog|video|announcement|review|campaign)\b|"
        r"\b(?:submit|send)\s+(?:application|tax|filing|payment|wire)\b",
        re.I
    )),
    ("booking_or_cancellation", re.compile(r"\b(book|reserve|cancel|unsubscribe)\b", re.I)),
    ("account_or_security_change", re.compile(r"\b(change|reset|disable|enable|update)\b.{0,70}\b(password|security|recovery|bank|billing|two.factor|2fa|permissions)\b", re.I)),
    ("sensitive_profile_change", re.compile(r"\b(change|update|modify)\b.{0,55}\b(profile|personal details|address|phone number|contact details)\b", re.I)),
)
_MEDIUM_IMPACT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("form_submission", re.compile(r"\b(continue|confirm|finish|complete)\b.{0,50}\b(form|application|registration)\b", re.I)),
    ("public_interaction", re.compile(r"\b(comment|review|rate|vote)\b", re.I)),
)


def classify_action_risk(command: str, objective: str) -> dict[str, Any]:
    """Return a stable risk classification derived from user text, not Qwen metadata."""
    text = f"{command or ''}\n{objective or ''}"
    for category, pattern in _CRITICAL_PATTERNS:
        match = pattern.search(text)
        if match:
            return {
                "risk_level": "critical",
                "category": category,
                "matched_text": match.group(0)[:120],
                "requires_approval": False,
                "blocked": True,
                "reason": (
                    "NOVA blocked this high-consequence action by default. "
                    "It cannot execute fund transfers, cash withdrawals or removal of account protections."
                ),
            }
    for category, pattern in _HIGH_IMPACT_PATTERNS:
        match = pattern.search(text)
        if match:
            return {
                "risk_level": "high",
                "category": category,
                "matched_text": match.group(0)[:120],
                "requires_approval": True,
                "blocked": False,
                "reason": (
                    f"The requested browser action includes '{match.group(0)}', which may have "
                    "an external, financial, account, publication, deletion or communication effect."
                ),
            }
    for category, pattern in _MEDIUM_IMPACT_PATTERNS:
        match = pattern.search(text)
        if match:
            return {
                "risk_level": "medium",
                "category": category,
                "matched_text": match.group(0)[:120],
                "requires_approval": True,
                "blocked": False,
                "reason": f"The action may submit or publicly change information ({match.group(0)}).",
            }
    return {
        "risk_level": "low",
        "category": "navigation_or_read_only",
        "matched_text": "",
        "requires_approval": False,
        "blocked": False,
        "reason": "No known high-impact browser action pattern was detected.",
    }


def approval_reason(command: str, objective: str) -> str | None:
    """Backward-compatible approval helper used by the Orchestrator and tests."""
    assessment = classify_action_risk(command, objective)
    return str(assessment["reason"]) if assessment["requires_approval"] else None


def generate_action_impact_preview(action: str, target: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Generate structured visual preview metadata for human approval cards.
    Provides affected targets, side-effect severity, and risk mitigations.
    """
    params = parameters or {}
    risk = classify_action_risk(action, target)

    files_affected = []
    if "file" in target.lower() or "path" in params:
        files_affected.append(str(params.get("path") or target))

    network_endpoints = []
    if "http" in target or "url" in params:
        network_endpoints.append(str(params.get("url") or target))

    return {
        "action": action,
        "target": target,
        "risk_level": risk["risk_level"],
        "category": risk.get("category", "general"),
        "requires_approval": risk.get("requires_approval", False),
        "blocked": risk.get("blocked", False),
        "reason": risk.get("reason", ""),
        "files_affected": files_affected,
        "network_endpoints": network_endpoints,
        "parameters": params,
        "reversible": risk["risk_level"] in {"low", "medium"},
    }

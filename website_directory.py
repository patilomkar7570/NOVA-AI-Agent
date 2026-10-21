"""Fast local website-name-to-URL resolver for NOVA.

Loads website_directory.json once at import time. No network requests are made.
"""
from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any

_DIRECTORY_PATH = Path(__file__).resolve().with_name("website_directory.json")
_ENTRIES: list[dict[str, Any]] = []
_ALIAS_INDEX: dict[str, list[int]] = {}
_LOAD_ERROR: str | None = None

_LEADING_COMMANDS = re.compile(r"^(?:(?:please\s+)?(?:open|visit|navigate to|go to|launch|browse to)\s+)", re.I)
_TRAILING_FILLER = re.compile(r"\s+(?:website|web site|site|domain|homepage|home page|official website|official site)$", re.I)
_COUNTRY_HINTS = {
    "india": ("india",),
    "uk": ("uk", "united kingdom", "britain", "british"),
    "usa": ("usa", "us", "united states", "america", "american"),
    "australia": ("australia", "australian", "au"),
}


def _normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = _LEADING_COMMANDS.sub("", text)
    text = _TRAILING_FILLER.sub("", text.strip())
    text = text.strip(" \t\r\n\"'`.,!?;:()[]{}")
    # An explicit URL/domain should be normalized the same way as its matching alias.
    return re.sub(r"[^a-z0-9]+", "", text)


def _load() -> None:
    global _ENTRIES, _ALIAS_INDEX, _LOAD_ERROR
    try:
        with _DIRECTORY_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        entries = payload.get("entries", []) if isinstance(payload, dict) else []
        if not isinstance(entries, list):
            raise ValueError("directory JSON has no entries list")

        alias_index: dict[str, list[int]] = {}
        valid_entries: list[dict[str, Any]] = []
        for raw_entry in entries:
            if not isinstance(raw_entry, dict):
                continue
            name = str(raw_entry.get("name", "")).strip()
            url = str(raw_entry.get("url", "")).strip()
            parsed = urlsplit(url)
            if not name or parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue
            entry = dict(raw_entry)
            entry["name"] = name
            entry["url"] = url
            entry["host"] = str(entry.get("host") or parsed.hostname).lower()
            entry["region"] = str(entry.get("region") or "global").lower()
            valid_entries.append(entry)
            idx = len(valid_entries) - 1
            aliases = [name, entry.get("host", ""), url, parsed.netloc, (parsed.hostname or "")]
            aliases.extend(entry.get("aliases", []) if isinstance(entry.get("aliases"), list) else [])
            for alias in aliases:
                key = _normalize_name(alias)
                if key:
                    bucket = alias_index.setdefault(key, [])
                    if idx not in bucket:
                        bucket.append(idx)

        _ENTRIES = valid_entries
        _ALIAS_INDEX = alias_index
        _LOAD_ERROR = None
    except Exception as exc:
        _ENTRIES = []
        _ALIAS_INDEX = {}
        if not _DIRECTORY_PATH.exists():
            _LOAD_ERROR = (
                f"{_DIRECTORY_PATH.name} is missing. Include this static data file "
                "in the repository/release; it is not personal runtime memory."
            )
        else:
            _LOAD_ERROR = str(exc)


_load()


def _preference_score(entry: dict[str, Any], query_key: str) -> float:
    score = 0.0
    region = str(entry.get("region", "global")).lower()
    path = urlsplit(str(entry.get("url", ""))).path or "/"
    host = str(entry.get("host", "")).lower()

    # Honor explicit geographic terms in a command.
    explicit_region = None
    for region_key, hints in _COUNTRY_HINTS.items():
        if any(_normalize_name(hint) in query_key for hint in hints):
            explicit_region = region_key
            break
    if explicit_region:
        if region == explicit_region:
            score += 100
        elif region == "global" and explicit_region == "usa":
            score += 20
        else:
            score -= 50
    else:
        # NOVA is being used in India. Prefer Indian-local sites when a brand
        # has regional variants, then global homepages, without hiding explicit aliases.
        if region == "india":
            score += 12
        elif region == "global":
            score += 7
        elif region == "uk":
            score += 2
        elif region == "australia":
            score += 1

    if path == "/":
        score += 5
    else:
        score -= min(len(path), 30) / 100
    if host.startswith("www."):
        score += 0.1
    return score


def _pick(indices: list[int], query_key: str) -> dict[str, Any] | None:
    unique = list(dict.fromkeys(indices))
    if not unique:
        return None
    if len(unique) == 1:
        return dict(_ENTRIES[unique[0]])
    ranked = sorted(unique, key=lambda i: _preference_score(_ENTRIES[i], query_key), reverse=True)
    first = _ENTRIES[ranked[0]]
    first_score = _preference_score(first, query_key)
    second_score = _preference_score(_ENTRIES[ranked[1]], query_key)
    # Only auto-resolve a collision when the preference is meaningful. A tie between
    # unrelated sites is returned as ambiguous rather than opening a random result.
    if first_score - second_score < 1.5:
        first_hosts = {str(_ENTRIES[i].get("host", "")) for i in ranked if _preference_score(_ENTRIES[i], query_key) == first_score}
        if len(first_hosts) > 1:
            return None
    return dict(first)


def resolve_website(name: str, *, fuzzy: bool = True) -> dict[str, Any] | None:
    """Return the best local directory entry for a site name/alias, or None.

    Exact alias lookup runs first and is fast. Fuzzy matching is conservative and
    only used when no exact alias exists.
    """
    query_key = _normalize_name(name)
    if not query_key:
        return None

    exact = _ALIAS_INDEX.get(query_key)
    if exact:
        found = _pick(exact, query_key)
        if found:
            found["matched_by"] = "exact_alias"
        return found

    if not fuzzy or len(query_key) < 5 or not _ALIAS_INDEX:
        return None

    # Do not try to fuzzily infer a destination from a full domain typo or a path.
    raw_text = str(name or "").strip()
    if "." in raw_text or "/" in raw_text:
        return None

    matches: list[tuple[float, str, list[int]]] = []
    for alias_key, indices in _ALIAS_INDEX.items():
        if len(alias_key) < 5:
            continue
        ratio = SequenceMatcher(None, query_key, alias_key).ratio()
        if ratio >= 0.90:
            matches.append((ratio, alias_key, indices))
    if not matches:
        return None
    matches.sort(key=lambda x: x[0], reverse=True)
    top_ratio = matches[0][0]
    top = [m for m in matches if top_ratio - m[0] <= 0.015]
    candidate_indices = list(dict.fromkeys(i for _, _, group in top for i in group))
    # Fuzzy matches must be clearly better than the next distinct candidate.
    distinct_urls = {str(_ENTRIES[i].get("url", "")) for i in candidate_indices}
    if len(distinct_urls) > 1 and len(matches) > len(top) and top_ratio - matches[len(top)][0] < 0.06:
        return None
    found = _pick(candidate_indices, query_key)
    if found:
        found["matched_by"] = "fuzzy_alias"
        found["match_score"] = round(top_ratio, 3)
    return found


def is_domain_like(value: str) -> bool:
    """True for an explicit hostname/domain request, not a natural-language site name."""
    text = str(value or "").strip()
    if not text or any(ch.isspace() for ch in text):
        return False
    candidate = text if text.lower().startswith(("http://", "https://")) else "https://" + text
    parsed = urlsplit(candidate)
    host = parsed.hostname or ""
    return bool(host and "." in host and re.fullmatch(r"[a-z0-9.-]+", host, flags=re.I))


def get_stats() -> dict[str, Any]:
    return {
        "entries": len(_ENTRIES),
        "aliases": len(_ALIAS_INDEX),
        "load_error": _LOAD_ERROR,
        "file": str(_DIRECTORY_PATH),
    }


def all_entries() -> list[dict[str, Any]]:
    """Return a shallow copy of the directory entries for diagnostics."""
    return [dict(entry) for entry in _ENTRIES]


# Section paths for websites whose URL structure is known. Unknown site sections
# remain keyword-scoped rather than inventing a path.
_KNOWN_SECTION_PATHS = {
    "timesofindia.indiatimes.com": {
        "tech": "technology",
        "technology": "technology",
        "business": "business",
        "sports": "sports",
        "entertainment": "entertainment",
        "india": "india",
        "national": "india",
        "world": "world",
        "international": "world",
        "education": "education",
        "health": "life-style/health-fitness",
        "lifestyle": "life-style",
        "life style": "life-style",
        "auto": "auto",
        "automobiles": "auto",
        "city": "city",
    }
}


def resolve_site_scoped_request(command: str) -> dict[str, Any] | None:
    """Parse requests such as 'open Sundar Pichai article in Times of India tech section'.

    Returns a safe, domain-scoped web-search plan. The caller should search with
    the generated site: query and then open the first organic result, rather than
    merely opening a Google results page and reporting the task complete.
    """
    raw = str(command or "").strip()
    if not raw:
        return None

    # Remove polite/conversational lead-ins, then require a goal-oriented verb.
    raw = re.sub(r"^(?:(?:now|please|can you|could you|would you)\s+)+", "", raw, flags=re.I)
    m = re.match(r"^(?:open|find|show|read|look up|search for|search|find me)\s+(.+?)\s*[.!?]*$", raw, flags=re.I)
    if not m:
        return None
    body = m.group(1).strip()

    section = None
    section_match = re.search(
        r"\b(?:inside|within|in the)\s+([a-z][a-z -]*?)\s+(?:section|category)\s*$",
        body,
        flags=re.I,
    )
    if section_match:
        section = re.sub(r"\s+", " ", section_match.group(1).strip().lower())
        body = body[:section_match.start()].strip()

    # A target site must be explicitly named with 'in/on/from' and must resolve
    # against the local directory. This prevents normal searches being hijacked.
    site_marker = None
    for match in re.finditer(r"\b(?:in|on|from)\s+(.+)$", body, flags=re.I):
        candidate = match.group(1).strip().strip(" .,!?:;\"'")
        resolved = resolve_website(candidate)
        if resolved:
            site_marker = (match, resolved, candidate)
            break
    if not site_marker:
        return None

    match, site_entry, site_name = site_marker
    subject = body[:match.start()].strip(" .,!?:;\"'")
    if not subject:
        return None

    host = str(site_entry.get("host") or urlsplit(site_entry["url"]).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return None

    section_path = None
    if section:
        for known_host, section_map in _KNOWN_SECTION_PATHS.items():
            if host == known_host or host.endswith("." + known_host):
                section_path = section_map.get(section)
                break

    if section_path:
        scoped_site = f"site:{host}/{section_path}"
    else:
        scoped_site = f"site:{host}"

    # Keep the subject intact. Add the requested section as a search term when
    # the site does not have a known, validated section path.
    query_parts = [scoped_site, subject]
    if section and not section_path:
        query_parts.append(section)
    search_query = " ".join(part for part in query_parts if part).strip()

    return {
        "site_name": str(site_entry.get("name") or site_name),
        "site_url": str(site_entry["url"]),
        "host": host,
        "subject": subject,
        "section": section,
        "section_path": section_path,
        "search_query": search_query,
    }

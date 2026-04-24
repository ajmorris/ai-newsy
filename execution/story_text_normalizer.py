"""
Utilities to keep story summary/opinion text safe for digest surfaces.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional


_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_LIST_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d+\.)\s+", re.MULTILINE)


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort parse for JSON object from raw model output."""
    raw = (text or "").strip()
    if not raw:
        return None

    candidates = [raw]
    fenced = _FENCE_RE.findall(raw)
    candidates.extend(chunk.strip() for chunk in fenced if chunk.strip())

    for candidate in candidates:
        parsed = _parse_json_object(candidate)
        if parsed is not None:
            return parsed
    return _parse_json_from_braces(raw)


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(text)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_json_from_braces(text: str) -> Optional[Dict[str, Any]]:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : idx + 1].strip()
                parsed = _parse_json_object(candidate)
                if parsed is not None:
                    return parsed
    return None


def is_markdown_heavy(text: str) -> bool:
    """Heuristic for markdown-like blobs that do not belong in summaries."""
    raw = (text or "").strip()
    if not raw:
        return False
    score = 0
    if _HEADER_RE.search(raw):
        score += 2
    if "```" in raw:
        score += 2
    if _LIST_RE.search(raw):
        score += 1
    if raw.count("**") >= 4:
        score += 1
    if raw.count("\n") >= 4:
        score += 1
    return score >= 2


def normalize_story_text(text: str, max_chars: int = 800) -> str:
    """Convert markdown-ish blobs into clean plain text paragraph output."""
    raw = (text or "").strip()
    if not raw:
        return ""

    # Remove fenced code blocks but keep their inner text.
    raw = _FENCE_RE.sub(lambda match: match.group(1).strip(), raw)
    # Convert markdown links to their visible text.
    raw = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"\1", raw)
    # Remove heading markers.
    raw = re.sub(r"^\s{0,3}#{1,6}\s*", "", raw, flags=re.MULTILINE)
    # Remove list markers.
    raw = re.sub(r"^\s{0,3}(?:[-*+]|\d+\.)\s+", "", raw, flags=re.MULTILINE)
    # Remove emphasis markers.
    raw = raw.replace("**", "").replace("__", "").replace("*", "")

    # Collapse to paragraph-ish output.
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\s*\n+\s*", " ", raw).strip()
    raw = re.sub(r"\s{2,}", " ", raw)

    if len(raw) > max_chars:
        return raw[: max_chars - 1].rstrip() + "…"
    return raw


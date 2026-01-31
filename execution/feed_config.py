"""
Load RSS feed config from directives/fetch_ai_news.md (primary) and feed_urls.md (fallback + additional).
Merge and de-dupe by logical source. Used by fetch_ai_news.py.
"""

import re
from pathlib import Path
from typing import Optional

# Repo root: parent of execution/
REPO_ROOT = Path(__file__).resolve().parent.parent
DIRECTIVE_PATH = REPO_ROOT / "directives" / "fetch_ai_news.md"
FEED_URLS_PATH = REPO_ROOT / "feed_urls.md"


def load_directive_feeds() -> list[dict]:
    """
    Read directives/fetch_ai_news.md and parse the "Current RSS feeds" section.
    Returns list of {"name": str, "source": str, "url": str}.
    """
    if not DIRECTIVE_PATH.exists():
        return []
    text = DIRECTIVE_PATH.read_text(encoding="utf-8")
    feeds = []
    in_sources = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Current RSS feeds:"):
            in_sources = True
            continue
        if in_sources:
            if not line or (line.startswith("##") and feeds):
                break
            # Format: "- Name: https://..."
            if line.startswith("- ") and ("http://" in line or "https://" in line):
                # Split on first ": " that precedes http
                idx = line.find(": http")
                if idx == -1:
                    idx = line.find(": https")
                if idx != -1:
                    name = line[2:idx].strip()  # drop "- " and take name
                    url = line[idx + 2 :].strip()  # ": " is 2 chars
                    if name and url:
                        feeds.append({
                            "name": name,
                            "source": name,
                            "url": url,
                        })
    return feeds


def load_feed_urls() -> list[dict]:
    """
    Read feed_urls.md and parse each [Label](url) link.
    Returns list of {"name": str, "url": str}.
    """
    if not FEED_URLS_PATH.exists():
        return []
    text = FEED_URLS_PATH.read_text(encoding="utf-8")
    # Match [text](url) - url can be http or https
    pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
    feeds = []
    for match in pattern.finditer(text):
        name, url = match.group(1).strip(), match.group(2).strip()
        if name and url:
            feeds.append({"name": name, "url": url})
    return feeds


def _normalize_for_match(s: str) -> str:
    """Normalize source name for matching (lowercase, strip common suffixes)."""
    s = s.lower().strip()
    for suffix in (" blog", " ai", " news", " research"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    return s


def _is_same_source(directive_name: str, feed_url_name: str) -> bool:
    """True if both refer to the same logical source (e.g. Google AI Blog vs Google AI)."""
    norm_d = _normalize_for_match(directive_name)
    norm_fu = _normalize_for_match(feed_url_name)
    if norm_d == norm_fu or norm_d in norm_fu or norm_fu in norm_d:
        return True
    if norm_d and norm_fu and norm_d.split()[0] == norm_fu.split()[0]:
        return True
    return False


def build_merged_feeds(
    directive_feeds: list[dict],
    feed_urls_list: list[dict],
) -> list[dict]:
    """
    Merge directive (primary) and feed_urls (fallback + additional). De-dupe by logical source.
    Returns list of {"name": str, "source": str, "primary_url": str, "fallback_url": str | None}.
    """
    merged = []
    used_feed_urls_indices = set()

    # 1. Each directive feed -> one entry; attach fallback from feed_urls if same source
    for d in directive_feeds:
        fallback_url = None
        for i, fu in enumerate(feed_urls_list):
            if _is_same_source(d["source"], fu["name"]):
                fallback_url = fu["url"]
                used_feed_urls_indices.add(i)
                break
        merged.append({
            "name": d["name"],
            "source": d["source"],
            "primary_url": d["url"],
            "fallback_url": fallback_url,
        })

    # 2. Feed_urls entries not matched to any directive -> additional sources
    for i, fu in enumerate(feed_urls_list):
        if i in used_feed_urls_indices:
            continue
        norm_fu = _normalize_for_match(fu["name"])
        already = any(_is_same_source(m["source"], fu["name"]) for m in merged)
        if already:
            continue
        merged.append({
            "name": fu["name"],
            "source": fu["name"],
            "primary_url": fu["url"],
            "fallback_url": None,
        })

    return merged


def get_merged_feeds() -> list[dict]:
    """Load directive + feed_urls, merge and de-dupe. Single entry point for fetch_ai_news.py."""
    directive = load_directive_feeds()
    feed_urls = load_feed_urls()
    return build_merged_feeds(directive, feed_urls)

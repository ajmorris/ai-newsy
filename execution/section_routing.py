"""Route developer tooling out of the main story list.

Rules decide first. An optional judge is only asked when the rules do not match,
so a changelog does not depend on a model call.
"""

from __future__ import annotations

import os
import re
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

DEV_HOSTS = ("github.com", "gitlab.com", "npmjs.com", "pypi.org")
DEV_SECTION_CAP = 8
TAG_RANK = {"Breaking change": 0, "Release": 1, "Gotcha": 2, "New tool": 3}

_VERSION_RE = re.compile(r"(?:^|[^a-z0-9])v\d+\.\d+", re.IGNORECASE)
_CHANGELOG_RE = re.compile(r"\b(changelog|release notes|releases)\b", re.IGNORECASE)
_BREAKING_RE = re.compile(r"\bbreaking change\b|\bgotcha\b", re.IGNORECASE)
_MAJOR_NEWS_RE = re.compile(r"\bopen weights\b", re.IGNORECASE)

Judge = Callable[[Dict], str]

DEV_TIEBREAKER_PROMPT = """You are routing one item for a daily AI newsletter.
Reply with exactly one label: developer tooling, or news.
developer tooling means a repo, library release, changelog, or developer tool.
news means a reported event, a company story, or research about the world.

Title: {title}
URL: {url}
Summary: {summary}
"""


def _host(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _path(url: str) -> str:
    return urlparse(url or "").path.lower()


def is_dev_url(url: str) -> bool:
    host = _host(url)
    if host in DEV_HOSTS or host.endswith(".github.com"):
        return True
    return host == "huggingface.co" and _path(url).startswith("/spaces")


def is_dev_text(title: str, url: str = "") -> bool:
    blob = f"{title or ''} {url or ''}"
    if _CHANGELOG_RE.search(blob) or _VERSION_RE.search(blob):
        return True
    return "release" in blob.lower()


def is_major_news(item: Dict) -> bool:
    if item.get("promote_to_main"):
        return True
    try:
        if float(item.get("significance_score") or 0) >= 0.85:
            return True
    except (TypeError, ValueError):
        pass
    return bool(_MAJOR_NEWS_RE.search(str(item.get("title", "") or "")))


def dev_tag(item: Dict) -> str:
    blob = f"{item.get('title', '')} {item.get('url', '')}".lower()
    if "breaking change" in blob:
        return "Breaking change"
    if "gotcha" in blob:
        return "Gotcha"
    if is_dev_text(str(item.get("title", "")), str(item.get("url", ""))):
        return "Release"
    return "New tool"


def _repo_key(url: str) -> str:
    host = _host(url)
    parts = [part for part in _path(url).split("/") if part]
    if host in {"github.com", "gitlab.com"} and len(parts) >= 2:
        return f"{host}/{parts[0]}/{parts[1]}"
    return ""


def route_item(item: Dict, judge: Optional[Judge] = None) -> str:
    """Return `dev` or `main`."""
    if is_major_news(item):
        return "main"
    title = str(item.get("title", "") or "")
    url = str(item.get("url", "") or "")
    if is_dev_url(url) or is_dev_text(title, url):
        return "dev"
    if judge is None:
        return "main"
    label = str(judge(item) or "").strip().lower()
    if "developer" in label or label == "dev":
        return "dev"
    return "main"


def _headline_for(item: Dict) -> Dict:
    title = str(item.get("title", "") or "Untitled").strip()
    return {
        "headline": f"__{title}__",
        "url": str(item.get("url", "") or "").strip(),
        "tag": dev_tag(item),
        "source": str(item.get("source", "") or "").strip(),
    }


def collapse_changelogs(items: Sequence[Dict]) -> List[Dict]:
    """Many changelog entries from one repo become a single dev item."""
    grouped: Dict[str, List[Dict]] = {}
    order: List[str] = []
    passthrough: List[Dict] = []
    for item in items:
        key = _repo_key(str(item.get("url", "") or ""))
        title = str(item.get("title", "") or "")
        if key and (_CHANGELOG_RE.search(title) or _CHANGELOG_RE.search(str(item.get("url", "")))):
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(item)
            continue
        passthrough.append(item)

    collapsed: List[Dict] = []
    for key in order:
        entries = grouped[key]
        if len(entries) == 1:
            collapsed.append(entries[0])
            continue
        lead = entries[0]
        repo = key.split("/", 1)[-1]
        collapsed.append(
            {
                **lead,
                "title": f"Notable changes in {repo}",
                "url": lead.get("url"),
            }
        )
    return passthrough + collapsed


def rank_dev_items(items: Iterable[Dict], limit: int = DEV_SECTION_CAP) -> List[Dict]:
    ranked = sorted(
        items,
        key=lambda item: (
            TAG_RANK.get(dev_tag(item), 9),
            str(item.get("published_at") or ""),
        ),
    )
    # Breaking changes first. Within a tag, newer published_at should win, so sort
    # tag ascending and time descending via a second pass.
    ranked.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
    ranked.sort(key=lambda item: TAG_RANK.get(dev_tag(item), 9))
    headlines = [_headline_for(item) for item in ranked]
    return headlines[: max(0, limit)]


def split_main_and_dev(
    items: Sequence[Dict],
    judge: Optional[Judge] = None,
    limit: int = DEV_SECTION_CAP,
) -> Tuple[List[Dict], List[Dict]]:
    main_items: List[Dict] = []
    dev_items: List[Dict] = []
    for item in items:
        if route_item(item, judge=judge) == "dev":
            dev_items.append(item)
        else:
            main_items.append(item)
    dev_items = collapse_changelogs(dev_items)
    return main_items, rank_dev_items(dev_items, limit=limit)


def llm_dev_judge(item: Dict) -> str:
    """Ask the configured model only when DEV_LLM_TIEBREAKER=1."""
    if os.getenv("DEV_LLM_TIEBREAKER", "").strip() not in {"1", "true", "yes"}:
        return "news"
    from execution.ai_client import generate_text_with_fallback

    prompt = DEV_TIEBREAKER_PROMPT.format(
        title=item.get("title", ""),
        url=item.get("url", ""),
        summary=item.get("summary", ""),
    )
    return generate_text_with_fallback(prompt=prompt, json_mode=False)

"""Feed ingestion that skips a bad source instead of aborting the run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import feedparser

from execution.url_dedup import dedupe_by_canonical_url


class FeedSkipped(Exception):
    """A single feed could not be parsed. The rest of the run should continue."""


@dataclass
class IngestResult:
    articles: List[Dict] = field(default_factory=list)
    skipped: List[Dict[str, str]] = field(default_factory=list)


def articles_from_parsed_feed(parsed, *, source: str, name: str, limit: int) -> List[Dict]:
    """Turn a feedparser result into article dicts. Raise FeedSkipped when unusable."""
    entries = getattr(parsed, "entries", None) or []
    articles: List[Dict] = []
    for entry in entries[:limit]:
        title = str(entry.get("title") or "").strip()
        url = str(entry.get("link") or "").strip()
        if not title or not url:
            continue
        summary = str(entry.get("summary") or entry.get("description") or "")
        articles.append(
            {
                "url": url,
                "title": title,
                "source": source,
                "content": summary,
            }
        )
    if getattr(parsed, "bozo", False) and not articles:
        reason = getattr(getattr(parsed, "bozo_exception", None), "message", "") or str(
            getattr(parsed, "bozo_exception", "malformed feed")
        )
        raise FeedSkipped(f"{name}: {reason}"[:200])
    return dedupe_by_canonical_url(articles)


def parse_feed_bytes(content: bytes):
    return feedparser.parse(
        content,
        response_headers={"content-type": "application/xml; charset=utf-8"},
    )


def gather_feed_articles(
    feeds: List[Dict],
    load_feed: Callable[[Dict], List[Dict]],
    log: Optional[Callable[[str], None]] = None,
) -> IngestResult:
    """Load every feed. A failure is logged and skipped; other feeds still return."""
    write = log or (lambda _message: None)
    result = IngestResult()
    for feed in feeds:
        name = str(feed.get("name") or feed.get("source") or "feed")
        try:
            articles = load_feed(feed) or []
        except Exception as exc:
            warning = f"skipping feed {name}: {exc}"
            write(f"    Warning: {warning}")
            result.skipped.append({"name": name, "warning": warning})
            continue
        result.articles.extend(dedupe_by_canonical_url(articles))
    result.articles = dedupe_by_canonical_url(result.articles)
    return result

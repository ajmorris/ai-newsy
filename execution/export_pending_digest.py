"""
Export pending digest inputs for Claude Desktop.

Writes articles (and optional tweet/community sources) as JSON. Claude reads
this file, writes analyses/intro/headlines, then apply_claude_digest.py persists
them. No Anthropic API key is required.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

import sys

sys.path.insert(0, ".")
from execution.analyze_articles_single_pass import TOPICS
from execution.database import get_articles_without_analysis

load_dotenv()

DEFAULT_OUTPUT = Path(".tmp/pending-digest.json")


def _article_row(article: Dict[str, Any]) -> Dict[str, Any]:
    content = str(article.get("content") or "")
    return {
        "id": article.get("id"),
        "title": article.get("title", ""),
        "url": article.get("url", ""),
        "source": article.get("source", ""),
        "published_at": article.get("published_at"),
        "content": content[:2500],
        "allowed_topics": TOPICS,
    }


def _safe_fetch(label: str, fn) -> List[Dict[str, Any]]:
    try:
        return list(fn() or [])
    except Exception as exc:
        print(f"Skipping {label} export: {exc}")
        return []


def export_pending(window_hours: int, output: Path) -> Path:
    digest_date = datetime.now(timezone.utc).date().isoformat()
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    articles = get_articles_without_analysis(since=since, unsent_only=True)

    tweets: List[Dict[str, Any]] = []
    community: List[Dict[str, Any]] = []
    try:
        from execution.generate_tweet_headlines import fetch_recent_tweets

        tweets = _safe_fetch("tweets", lambda: fetch_recent_tweets(limit=100, hours=24))
    except Exception as exc:
        print(f"Skipping tweet export: {exc}")
    try:
        from execution.generate_community_headlines import fetch_recent_community_items

        community = _safe_fetch(
            "community",
            lambda: fetch_recent_community_items(limit=120, hours=24),
        )
    except Exception as exc:
        print(f"Skipping community export: {exc}")

    payload = {
        "digest_date": digest_date,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "voice": (
            "First person, coffee-conversation, candid, no guru certainty. "
            "Center on what I am learning, watching, and seeing."
        ),
        "articles": [_article_row(row) for row in articles],
        "tweets": tweets,
        "community": community,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote pending digest inputs: {output}")
    print(
        f"articles={len(payload['articles'])} tweets={len(tweets)} community={len(community)}"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export pending digest inputs for Claude Desktop")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--window-hours",
        type=int,
        default=int(os.getenv("SINGLE_PASS_WINDOW_HOURS", "48")),
    )
    args = parser.parse_args()
    export_pending(window_hours=max(1, args.window_hours), output=Path(args.output))

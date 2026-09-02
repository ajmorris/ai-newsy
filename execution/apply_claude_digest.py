"""
Persist Claude Desktop digest output (no Anthropic API key).

Expected JSON shape (written by Claude after reading pending-digest.json):

{
  "digest_date": "YYYY-MM-DD",
  "intro": "2-3 sentence first-person intro",
  "analyses": [
    {"id": 123, "topic": "Models", "summary": "...", "opinion": "...", "confidence": 0.8}
  ],
  "tweet_headlines": [{"headline": "...", "url": "..."}],
  "community_headlines": [{"headline": "...", "url": "..."}]
}
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

import sys

sys.path.insert(0, ".")
from execution.analyze_articles_single_pass import (
    PROMPT_VERSION,
    parse_strict_analysis_json,
)
from execution.database import update_article_analysis_payload, upsert_digest_extra
from execution.generate_community_headlines import persist_headlines as persist_community
from execution.generate_tweet_headlines import persist_headlines as persist_tweets

load_dotenv()

DEFAULT_INPUT = Path(".tmp/claude-digest.json")
CLAUDE_DESKTOP_MODEL = "claude-desktop"


def _load_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing Claude digest file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must be a JSON object")
    return data


def apply_claude_digest(path: Path) -> None:
    data = _load_payload(path)
    digest_date = str(data.get("digest_date") or datetime.now(timezone.utc).date().isoformat())
    intro = str(data.get("intro") or "").strip()
    if not intro:
        raise SystemExit("Claude digest JSON is missing a non-empty intro.")

    analyses = list(data.get("analyses") or [])
    run_id = f"claude-desktop-{uuid.uuid4()}"
    applied = 0
    for row in analyses:
        if not isinstance(row, dict):
            continue
        article_id = row.get("id")
        parsed = parse_strict_analysis_json(json.dumps(row))
        if article_id is None or not parsed or not str(parsed.get("opinion") or "").strip():
            raise SystemExit(f"Invalid analysis row (need id, topic, summary, opinion): {row!r}")
        parsed["source_url"] = str(row.get("url") or "")
        parsed["prompt_version"] = PROMPT_VERSION
        parsed["opinion_source"] = "claude-desktop"
        update_article_analysis_payload(
            article_id=int(article_id),
            payload=parsed,
            model=CLAUDE_DESKTOP_MODEL,
            prompt_version=PROMPT_VERSION,
            run_id=run_id,
        )
        applied += 1

    upsert_digest_extra(
        digest_date=digest_date,
        key="digest_intro",
        payload={
            "text": intro,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": CLAUDE_DESKTOP_MODEL,
        },
    )

    tweets = _normalize_headlines(list(data.get("tweet_headlines") or []))
    community = _normalize_headlines(list(data.get("community_headlines") or []))
    persist_tweets(tweets, source_count=len(tweets), digest_date=digest_date)
    persist_community(community, source_count=len(community), digest_date=digest_date)

    print(f"Applied Claude digest for {digest_date}: analyses={applied} tweets={len(tweets)} community={len(community)}")


def _normalize_headlines(rows: List[Any]) -> List[Dict[str, Any]]:
    headlines: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        headline = str(row.get("headline") or "").strip()
        url = str(row.get("url") or "").strip()
        if not headline:
            continue
        item = dict(row)
        item["headline"] = headline
        item["url"] = url
        headlines.append(item)
    return headlines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Persist Claude Desktop digest JSON")
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT))
    args = parser.parse_args()
    apply_claude_digest(Path(args.input))

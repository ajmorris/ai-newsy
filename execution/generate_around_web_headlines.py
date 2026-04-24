"""
Build Around the Web bullets by combining existing tweet/community extras
with selected company/org RSS sources.
"""

import argparse
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

import feedparser
from dotenv import load_dotenv

import sys
sys.path.insert(0, ".")
from execution.database import get_digest_extra, upsert_digest_extra
from execution.feed_config import load_feed_urls

load_dotenv()

TARGET_SOURCES = {
    "anthropic", "openai", "google deepmind", "deepmind", "nvidia", "google ai",
    "xai", "elevenlabs", "tesla ai", "boston dynamics", "perplexity", "meta ai",
    "cursor", "runway", "deepseek", "microsoft research",
}


def _sanitize_date(value: Optional[str]) -> str:
    return value or datetime.now(timezone.utc).date().isoformat()


def _match_target(name: str) -> bool:
    lower = name.lower().strip()
    return any(target in lower for target in TARGET_SOURCES)


def _fetch_feed_entries(url: str, source_label: str, hours: int, limit: int) -> List[Dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    parsed = feedparser.parse(url)
    rows: List[Dict] = []
    for entry in parsed.entries:
        raw_time = entry.get("published_parsed") or entry.get("updated_parsed")
        if raw_time:
            created = datetime(*raw_time[:6], tzinfo=timezone.utc)
            if created < cutoff:
                continue
            created_iso = created.isoformat()
        else:
            created_iso = ""
        title = str(entry.get("title", "")).strip()
        link = str(entry.get("link", "")).strip()
        if not title or not link:
            continue
        rows.append(
            {
                "headline": f"__{title}__",
                "url": link,
                "source_label": source_label,
                "source_type": "org_feed",
                "created_time": created_iso,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def main(digest_date: Optional[str], hours: int, max_headlines: int, dry_run: bool) -> None:
    safe_date = _sanitize_date(digest_date)
    tweet_extra = get_digest_extra(digest_date=safe_date, key="tweet_headlines") or {}
    community_extra = get_digest_extra(digest_date=safe_date, key="community_headlines") or {}
    tweet_rows = list((tweet_extra.get("payload") or {}).get("headlines", []) or [])
    community_rows = list((community_extra.get("payload") or {}).get("headlines", []) or [])

    org_rows: List[Dict] = []
    for feed in load_feed_urls():
        name = str(feed.get("name", ""))
        if not _match_target(name):
            continue
        url = str(feed.get("url", ""))
        if not url:
            continue
        org_rows.extend(_fetch_feed_entries(url=url, source_label=name, hours=hours, limit=2))

    combined = []
    combined.extend(tweet_rows)
    combined.extend(community_rows)
    combined.extend(org_rows)
    combined.sort(key=lambda row: str(row.get("created_time", "")), reverse=True)

    dedup: List[Dict] = []
    seen: Set[str] = set()
    for row in combined:
        key = f"{row.get('headline','').strip().lower()}|{row.get('url','').strip().lower()}"
        if not row.get("headline") or key in seen:
            continue
        seen.add(key)
        dedup.append(
            {
                "headline": str(row.get("headline", "")).strip(),
                "url": str(row.get("url", "")).strip(),
                "source_label": str(row.get("source_label", row.get("source_type", "Around the Web"))),
                "source_type": str(row.get("source_type", "around_web")),
                "created_time": str(row.get("created_time", "")),
            }
        )
        if len(dedup) >= max_headlines:
            break

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "headline_count": len(dedup),
        "headlines": dedup,
    }
    if dry_run:
        print(out)
        return
    upsert_digest_extra(digest_date=safe_date, key="around_web_headlines", payload=out)
    print("Stored Around the Web headlines in digest_extras.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Around the Web headlines")
    parser.add_argument("--digest-date", type=str, default=None, help="YYYY-MM-DD (UTC)")
    parser.add_argument("--hours", type=int, default=int(os.getenv("AROUND_WEB_LOOKBACK_HOURS", "24")))
    parser.add_argument("--max-headlines", type=int, default=int(os.getenv("AROUND_WEB_MAX_HEADLINES", "18")))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(
        digest_date=args.digest_date,
        hours=args.hours,
        max_headlines=args.max_headlines,
        dry_run=args.dry_run,
    )

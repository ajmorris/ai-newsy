#!/usr/bin/env python3
"""
Check RSS feed URLs: fetch each and report status (OK + entry count, or error).
Run from repo root: python3 scripts/check_feeds.py
Uses same fetch-then-parse as fetch_ai_news so raw.githubusercontent.com (text/plain) works.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from execution.feed_config import get_merged_feeds
from execution.fetch_ai_news import _parse_feed_url


def main():
    feeds = get_merged_feeds()
    print(f"Checking {len(feeds)} feeds...\n")
    ok = 0
    fail = 0
    for cfg in feeds:
        name = cfg["name"]
        url = cfg["primary_url"]
        try:
            feed = _parse_feed_url(url)
            if feed.bozo and feed.bozo_exception:
                err = getattr(feed.bozo_exception, "message", str(feed.bozo_exception))[:60]
                print(f"  FAIL  {name}")
                print(f"        Parse error: {err}")
                print(f"        URL: {url[:70]}...")
                fail += 1
            else:
                entries = getattr(feed, "entries", None) or []
                n = len(entries)
                print(f"  OK    {name}: {n} entries")
                ok += 1
        except Exception as e:
            print(f"  FAIL  {name}")
            print(f"        Error: {e}")
            print(f"        URL: {url[:70]}...")
            fail += 1
    print(f"\nSummary: {ok} OK, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    exit(main())

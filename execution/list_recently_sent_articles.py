#!/usr/bin/env python3
"""
List articles that were marked as sent in the last 24 hours.
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def list_recently_sent(hours: int = 24) -> None:
    now = datetime.utcnow()
    since = now - timedelta(hours=hours)
    since_iso = since.isoformat()

    print(f"Listing articles sent in the last {hours} hour(s) (since {since_iso})\n")

    result = (
        supabase.table("articles")
        .select("id, title, source, url, sent_at, topic")
        .gte("sent_at", since_iso)
        .order("sent_at", desc=True)
        .execute()
    )

    rows = result.data or []
    if not rows:
        print("No articles marked as sent in this window.")
        return

    for row in rows:
        print(f"[{row.get('id')}] {row.get('title', '')}")
        print(f"  Source: {row.get('source')}")
        print(f"  Topic:  {row.get('topic')}")
        print(f"  URL:    {row.get('url')}")
        print(f"  SentAt: {row.get('sent_at')}")
        print("")

    print(f"Total: {len(rows)} article(s)")


if __name__ == "__main__":
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("SUPABASE_URL or SUPABASE_KEY not set in .env")
        raise SystemExit(1)

    list_recently_sent(hours=24)
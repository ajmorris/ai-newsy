"""
Generate "What I'm Watching" from Notion YouTube rows.
"""

import argparse
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from dotenv import load_dotenv
from notion_client import Client as NotionClient

import sys
sys.path.insert(0, ".")
from execution.ai_client import generate_text_with_fallback
from execution.database import upsert_digest_extra

load_dotenv()

DEFAULT_PROMPT = """Write commentary for my "What I'm Watching" newsletter section.
Use first-person AJ voice: practical, warm, no hype.
Return JSON with keys:
- why_this_matters
- why_im_sharing_it
- why_its_important

Video data:
TITLE: {title}
CHANNEL: {channel}
URL: {url}
NOTES: {notes}
"""


def _sanitize_date(value: Optional[str]) -> str:
    return value or datetime.now(timezone.utc).date().isoformat()


def _first_rich_text_plain(rich_text: list) -> str:
    parts = [chunk.get("plain_text", "") for chunk in rich_text if isinstance(chunk, dict)]
    return "".join(parts).strip()


def _extract_prop_text(properties: Dict, keys: List[str]) -> str:
    lower = [k.lower() for k in keys]
    for name, value in properties.items():
        if name.lower() not in lower:
            continue
        if not isinstance(value, dict):
            continue
        ptype = value.get("type")
        if ptype == "title":
            return _first_rich_text_plain(value.get("title", []))
        if ptype == "rich_text":
            return _first_rich_text_plain(value.get("rich_text", []))
        if ptype == "url":
            return str(value.get("url", "")).strip()
    return ""


def _extract_date(properties: Dict, keys: List[str]) -> str:
    lower = [k.lower() for k in keys]
    for name, value in properties.items():
        if name.lower() not in lower:
            continue
        if isinstance(value, dict) and value.get("type") == "date" and value.get("date"):
            return str(value["date"].get("start", "")).strip()
    return ""


def _fetch_recent_videos(limit: int, days: int) -> List[Dict]:
    notion_api_key = os.getenv("NOTION_API_KEY", "")
    notion_db_id = os.getenv("NOTION_YOUTUBE_DATABASE_ID", "")
    if not notion_api_key or not notion_db_id:
        raise RuntimeError("NOTION_API_KEY and NOTION_YOUTUBE_DATABASE_ID are required")

    notion = NotionClient(auth=notion_api_key)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    response = notion.databases.query(
        database_id=notion_db_id,
        page_size=min(100, max(limit, 20)),
        filter={"timestamp": "created_time", "created_time": {"on_or_after": since.isoformat()}},
        sorts=[{"timestamp": "created_time", "direction": "descending"}],
    )

    rows: List[Dict] = []
    for page in response.get("results", []):
        props = page.get("properties", {})
        title = _extract_prop_text(props, ["title", "video", "name"])
        url = _extract_prop_text(props, ["url", "link", "youtube", "video url"])
        channel = _extract_prop_text(props, ["channel", "creator", "author"])
        notes = _extract_prop_text(props, ["notes", "summary", "why", "thoughts"])
        liked_at = _extract_date(props, ["liked at", "liked", "saved at"]) or page.get("created_time", "")
        published_at = _extract_date(props, ["published at", "published"])
        if not title or not url:
            continue
        rows.append(
            {
                "title": title,
                "url": url,
                "channel": channel or "Unknown",
                "notes": notes,
                "liked_at": liked_at,
                "published_at": published_at,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _parse_json_text(raw: str) -> Dict:
    import json
    import re
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1).strip()
        text = re.sub(r"\s*```$", "", text, count=1).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def main(digest_date: Optional[str], days: int, dry_run: bool) -> None:
    safe_date = _sanitize_date(digest_date)
    videos = _fetch_recent_videos(limit=20, days=days)
    print(f"Fetched {len(videos)} recent YouTube rows from Notion.")
    if not videos:
        print("No recent videos found; storing empty payload.")
        if not dry_run:
            upsert_digest_extra(
                digest_date=safe_date,
                key="what_watching",
                payload={"title": "", "url": "", "channel": "", "generated_at": datetime.now(timezone.utc).isoformat()},
            )
        return

    selected = videos[0]
    prompt = os.getenv("PROMPT_WHAT_WATCHING", DEFAULT_PROMPT).format(**selected)
    text = generate_text_with_fallback(prompt=prompt, gemini_model="gemini-2.0-flash")
    parsed = _parse_json_text(text)
    out = {
        "title": selected["title"],
        "url": selected["url"],
        "channel": selected["channel"],
        "liked_at": selected["liked_at"],
        "published_at": selected["published_at"],
        "source_text": selected.get("notes", ""),
        "why_this_matters": str(parsed.get("why_this_matters", "") or "").strip(),
        "why_im_sharing_it": str(parsed.get("why_im_sharing_it", "") or "").strip(),
        "why_its_important": str(parsed.get("why_its_important", "") or "").strip(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if dry_run:
        print(out)
        return
    upsert_digest_extra(digest_date=safe_date, key="what_watching", payload=out)
    print("Stored What I'm Watching payload in digest_extras.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate What I'm Watching payload from Notion YouTube rows")
    parser.add_argument("--digest-date", type=str, default=None, help="YYYY-MM-DD (UTC)")
    parser.add_argument("--days", type=int, default=int(os.getenv("YOUTUBE_LOOKBACK_DAYS", "30")))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(digest_date=args.digest_date, days=args.days, dry_run=args.dry_run)

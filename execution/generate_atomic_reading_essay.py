"""
Generate "What I'm Reading" atomic essay from digest stories.
"""

import argparse
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from dotenv import load_dotenv

import sys
sys.path.insert(0, ".")
from execution.ai_client import generate_text_with_fallback
from execution.database import get_digest_extra, upsert_digest_extra
from execution.digest_payload import DigestBuildOptions, build_digest_payload

load_dotenv()

DEFAULT_PROMPT = """You are writing my "What I'm Reading" section for a daily AI email.
Write in first person as AJ Morris. Follow this voice:
- Conversational, honest, grounded, practical.
- Builder perspective: what I am learning and noticing.
- No hype, no guru claims, no corporate jargon.

Return JSON with keys:
- title: short title, 4-8 words
- essay: 150-250 words, 2-4 short paragraphs, one core idea from today's stories
- key_links: array of up to 3 objects with {title,url,why_it_matters}

Stories:
{stories_blob}
"""


def _sanitize_date(value: Optional[str]) -> str:
    return value or datetime.now(timezone.utc).date().isoformat()


def _build_stories_blob(stories: List[Dict]) -> str:
    rows = []
    for story in stories[:8]:
        rows.append(
            "\n".join(
                [
                    f"TITLE: {story.get('title', '')}",
                    f"SOURCE: {story.get('source', '')}",
                    f"URL: {story.get('url', '')}",
                    f"SUMMARY: {story.get('summary', '')}",
                    f"OPINION: {story.get('opinion', '')}",
                ]
            )
        )
    return "\n\n---\n\n".join(rows)


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


def main(digest_date: Optional[str], dry_run: bool) -> None:
    safe_date = _sanitize_date(digest_date)
    payload = build_digest_payload(DigestBuildOptions(digest_date=safe_date))
    stories = list(payload.get("stories", []))
    if not stories:
        print("No stories available; skipping What I'm Reading generation.")
        return

    existing = get_digest_extra(digest_date=safe_date, key="what_reading")
    if existing and isinstance(existing.get("payload"), dict) and existing["payload"].get("essay"):
        print("What I'm Reading already exists; keeping existing payload.")
        if dry_run:
            print(existing["payload"].get("essay", ""))
        return

    prompt = os.getenv("PROMPT_WHAT_READING", DEFAULT_PROMPT).format(
        stories_blob=_build_stories_blob(stories)
    )
    text = generate_text_with_fallback(prompt=prompt, gemini_model="gemini-2.0-flash")
    parsed = _parse_json_text(text)
    title = str(parsed.get("title", "") or "What I'm Reading").strip()
    essay = str(parsed.get("essay", "") or "").strip()
    key_links = list(parsed.get("key_links", []) or [])
    if not essay:
        essay = "Today feels like a reminder that distribution is no longer the bottleneck; judgment is."

    out = {
        "title": title,
        "essay": essay,
        "key_links": key_links[:3],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if dry_run:
        print(out)
        return
    upsert_digest_extra(digest_date=safe_date, key="what_reading", payload=out)
    print("Stored What I'm Reading payload in digest_extras.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate What I'm Reading atomic essay")
    parser.add_argument("--digest-date", type=str, default=None, help="YYYY-MM-DD (UTC)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(digest_date=args.digest_date, dry_run=args.dry_run)

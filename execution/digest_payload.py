"""
Canonical digest payload builder and loader.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

import sys

sys.path.insert(0, ".")
from execution.ai_client import generate_text_with_fallback
from execution.database import (
    get_digest_extra,
    get_sent_articles,
    get_unsent_articles,
    upsert_digest_extra,
)

load_dotenv()

CANONICAL_SCHEMA_VERSION = "digest-json-v1"
DIGEST_SNAPSHOT_SUFFIX = ".sent.json"

TOPIC_TO_CATEGORY: Dict[str, str] = {
    "Models": "Model Releases & Capabilities",
    "Agents & Tools": "Tools, Infrastructure & Open Source",
    "MCP & SKILLs": "Tools, Infrastructure & Open Source",
    "MCP & Skills": "Tools, Infrastructure & Open Source",
    "Safety": "Safety, Policy & Regulation",
    "Industry": "Business, Deals & Funding",
}
DEFAULT_CATEGORY = "Other AI News"

DEFAULT_MAX_STORIES = int(os.getenv("DIGEST_MAX_STORIES", "8"))
DEFAULT_MAX_HEADLINES = int(os.getenv("DIGEST_MAX_HEADLINES", "6"))

DEFAULT_INTRO_PROMPT = """You are writing the opening paragraph for my daily AI news digest email.
Write as me, in first person, like we are talking over coffee.

Voice rules:
- Human Element + Honesty: candid, grounded, emotionally real.
- No guru certainty. I do not pretend to have everything figured out.
- Emphasize what I am learning, what I am watching, and what I am seeing.
- Sound like a builder sharing process: false starts, pivots, and practical signal.
- Keep it warm and plainspoken, not polished or promotional.

Output requirements:
1. Exactly one short paragraph (2-3 sentences).
2. Lead with today's most important thread or tension.
3. Preview what readers will get from the digest.
4. No greeting, no sign-off, no hashtags.

Today's stories:
{article_summaries}"""


@dataclass
class DigestBuildOptions:
    digest_date: Optional[str] = None
    window_hours: int = 24
    use_sent: bool = False
    max_stories: int = DEFAULT_MAX_STORIES
    max_headlines: int = DEFAULT_MAX_HEADLINES


def _issue_id_from_digest_date(digest_date: str) -> str:
    return "".join(ch for ch in digest_date if ch.isdigit())


def _build_subject_line(issue_id: str, story_count: int) -> str:
    short = issue_id[-5:] if issue_id else "00137"
    return f"ISSUE {short} · {story_count} STORIES · 11 MIN READ"


def _normalize_article(article: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": article.get("id"),
        "source": str(article.get("source", "Unknown Source") or "Unknown Source").strip(),
        "title": str(article.get("title", "Untitled") or "Untitled").strip(),
        "url": str(article.get("url", "#") or "#").strip(),
        "topic": str(article.get("topic", "") or "").strip(),
        "category": "",
        "summary": str(article.get("summary", "") or "").strip(),
        "opinion": str(article.get("opinion", "") or "").strip(),
        "image_url": str(article.get("image_url", "") or "").strip(),
        "published_at": str(article.get("published_at", "") or ""),
        "fetched_at": str(article.get("fetched_at", "") or ""),
    }


def _assign_category(article: Dict[str, Any]) -> None:
    topic = article.get("topic", "")
    article["category"] = TOPIC_TO_CATEGORY.get(topic, DEFAULT_CATEGORY)


def _get_or_create_intro(digest_date: str, stories: List[Dict[str, Any]]) -> str:
    stored = get_digest_extra(digest_date=digest_date, key="digest_intro")
    if stored and isinstance(stored.get("payload"), dict):
        intro = str(stored["payload"].get("text", "")).strip()
        if intro:
            return intro

    summaries = "\n".join(
        f"- {story.get('title', '')}: {story.get('summary', '')}"
        for story in stories
        if story.get("summary")
    )
    prompt = os.getenv("PROMPT_INTRO", DEFAULT_INTRO_PROMPT).format(article_summaries=summaries)
    intro = generate_text_with_fallback(prompt=prompt, gemini_model="gemini-2.0-flash").strip()
    if not intro:
        intro = "Here's what's making waves in AI today."

    upsert_digest_extra(
        digest_date=digest_date,
        key="digest_intro",
        payload={"text": intro, "generated_at": datetime.now(timezone.utc).isoformat()},
    )
    return intro


def _content_hash(payload: Dict[str, Any]) -> str:
    canonical_subset = {
        "digest_date": payload.get("digest_date"),
        "subject_line": payload.get("subject_line"),
        "intro": payload.get("intro"),
        "stories": payload.get("stories", []),
        "tweet_headlines": payload.get("tweet_headlines", []),
        "community_headlines": payload.get("community_headlines", []),
    }
    blob = json.dumps(canonical_subset, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_digest_payload(options: DigestBuildOptions) -> Dict[str, Any]:
    if options.digest_date:
        target_date = datetime.strptime(options.digest_date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now(timezone.utc).date()
    digest_date = target_date.isoformat()

    if options.use_sent:
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        rows = get_sent_articles(require_summary=True, since=day_start, until=day_end)
    else:
        since = datetime.now(timezone.utc) - timedelta(hours=options.window_hours)
        rows = get_unsent_articles(topic=None, require_summary=True, since=since, until=None)

    normalized = [_normalize_article(row) for row in rows]
    for row in normalized:
        _assign_category(row)
    normalized.sort(key=lambda row: row.get("published_at") or row.get("fetched_at") or "", reverse=True)

    stories = normalized[: max(0, options.max_stories)]

    tweet_extra = get_digest_extra(digest_date=digest_date, key="tweet_headlines") or {}
    tweet_headlines = []
    tweet_payload = tweet_extra.get("payload")
    if isinstance(tweet_payload, dict):
        tweet_headlines = list(tweet_payload.get("headlines", []) or [])[: max(0, options.max_headlines)]

    community_extra = get_digest_extra(digest_date=digest_date, key="community_headlines") or {}
    community_headlines = []
    community_payload = community_extra.get("payload")
    if isinstance(community_payload, dict):
        community_headlines = list(community_payload.get("headlines", []) or [])[: max(0, options.max_headlines)]

    issue_id = _issue_id_from_digest_date(digest_date)
    subject_line = _build_subject_line(issue_id, len(stories))
    intro = _get_or_create_intro(digest_date=digest_date, stories=stories) if stories else "No stories selected."

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for story in stories:
        grouped.setdefault(story["category"], []).append(story)
    section_order = sorted(grouped.keys())
    sections = [{"name": name, "articles": grouped[name]} for name in section_order]

    payload: Dict[str, Any] = {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "digest_date": digest_date,
        "issue_id": issue_id,
        "subject_line": subject_line,
        "intro": intro,
        "article_count": len(stories),
        "stories": stories,
        "sections": sections,
        "tweet_headlines": tweet_headlines,
        "community_headlines": community_headlines,
        "build_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_window_hours": options.window_hours,
            "use_sent": options.use_sent,
            "source": "canonical",
        },
    }
    payload["content_hash"] = _content_hash(payload)
    return payload


def write_digest_payload(payload: Dict[str, Any], output_dir: Optional[Path] = None) -> Path:
    out_dir = output_dir or Path(os.getenv("DIGEST_MARKDOWN_DIR", "data/digests"))
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"{payload['digest_date']}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def _snapshot_dir(base_dir: Optional[Path] = None) -> Path:
    if base_dir is not None:
        return base_dir
    env_dir = os.getenv("DIGEST_SNAPSHOT_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return Path(os.getenv("DIGEST_MARKDOWN_DIR", "data/digests")) / "snapshots"


def snapshot_path_for_digest(digest_date: str, snapshot_dir: Optional[Path] = None) -> Path:
    return _snapshot_dir(snapshot_dir) / f"{digest_date}{DIGEST_SNAPSHOT_SUFFIX}"


def write_sent_snapshot(
    payload: Dict[str, Any],
    snapshot_dir: Optional[Path] = None,
    allow_overwrite: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> Path:
    snap_path = snapshot_path_for_digest(str(payload["digest_date"]), snapshot_dir=snapshot_dir)
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    if snap_path.exists() and not allow_overwrite:
        return snap_path
    snapshot_payload = dict(payload)
    build_meta = dict(snapshot_payload.get("build_meta") or {})
    build_meta["source"] = "sent_snapshot"
    if metadata:
        build_meta["snapshot_meta"] = metadata
    snapshot_payload["build_meta"] = build_meta
    snapshot_payload["content_hash"] = _content_hash(snapshot_payload)
    snap_path.write_text(json.dumps(snapshot_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return snap_path


def load_sent_snapshot(digest_date: str, snapshot_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    snap_path = snapshot_path_for_digest(digest_date=digest_date, snapshot_dir=snapshot_dir)
    if not snap_path.exists():
        return None
    return json.loads(snap_path.read_text(encoding="utf-8"))


def load_digest_payload(digest_date: str, output_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    out_dir = output_dir or Path(os.getenv("DIGEST_MARKDOWN_DIR", "data/digests"))
    path = out_dir / f"{digest_date}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_or_build_digest_payload(options: DigestBuildOptions) -> Dict[str, Any]:
    digest_date = options.digest_date or datetime.now(timezone.utc).date().isoformat()
    existing = load_digest_payload(digest_date=digest_date)
    if existing and existing.get("schema_version") == CANONICAL_SCHEMA_VERSION:
        return existing
    payload = build_digest_payload(options)
    write_digest_payload(payload)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build canonical digest JSON payload")
    parser.add_argument("--digest-date", type=str, default=None, help="YYYY-MM-DD (UTC)")
    parser.add_argument("--window-hours", type=int, default=int(os.getenv("DIGEST_WINDOW_HOURS", "24")))
    parser.add_argument("--use-sent", action="store_true")
    parser.add_argument("--max-stories", type=int, default=DEFAULT_MAX_STORIES)
    parser.add_argument("--max-headlines", type=int, default=DEFAULT_MAX_HEADLINES)
    args = parser.parse_args()

    payload = build_digest_payload(
        DigestBuildOptions(
            digest_date=args.digest_date,
            window_hours=args.window_hours,
            use_sent=args.use_sent,
            max_stories=args.max_stories,
            max_headlines=args.max_headlines,
        )
    )
    path = write_digest_payload(payload)
    print(f"Wrote canonical digest payload: {path}")

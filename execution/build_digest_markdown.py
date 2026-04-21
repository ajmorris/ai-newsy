"""
Build a daily digest markdown file with YAML frontmatter from persisted storage.
"""

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

import sys
sys.path.insert(0, ".")
from execution.ai_client import generate_text_with_fallback
from execution.database import get_digest_extra, get_unsent_articles, upsert_digest_extra

load_dotenv()

TOPIC_TO_CATEGORY: Dict[str, str] = {
    "Models": "Model Releases & Capabilities",
    "Agents & Tools": "Tools, Infrastructure & Open Source",
    "MCP & SKILLs": "Tools, Infrastructure & Open Source",
    "Safety": "Safety, Policy & Regulation",
    "Industry": "Business, Deals & Funding",
}
DEFAULT_CATEGORY = "Other AI News"

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


def _yaml_quote(value: str) -> str:
    safe = (value or "").replace("\\", "\\\\").replace('"', '\\"')
    return f"\"{safe}\""


def _extract_embedded_payload(text: str) -> Dict[str, object]:
    stripped = (text or "").strip()
    if stripped.startswith("```json") and stripped.endswith("```"):
        inner = stripped[len("```json") : -3].strip()
        try:
            payload = json.loads(inner)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            return {}
    return {}


def _group_articles_by_category(articles: List[dict]) -> List[dict]:
    grouped: Dict[str, List[dict]] = {}
    for article in articles:
        topic = (article.get("topic") or "").strip()
        category = TOPIC_TO_CATEGORY.get(topic, DEFAULT_CATEGORY)
        grouped.setdefault(category, []).append(article)

    sections: List[dict] = []
    for category in sorted(grouped.keys()):
        ordered = sorted(
            grouped[category],
            key=lambda row: row.get("published_at") or row.get("fetched_at") or "",
            reverse=True,
        )
        sections.append({"name": category, "articles": ordered})
    return sections


def _get_or_create_intro(digest_date: str, articles: List[dict]) -> str:
    stored = get_digest_extra(digest_date=digest_date, key="digest_intro")
    if stored and isinstance(stored.get("payload"), dict):
        intro = (stored["payload"].get("text") or "").strip()
        if intro:
            return intro

    summaries = "\n".join(
        f"- {row.get('title', '')}: {row.get('summary', '')}" for row in articles if row.get("summary")
    )
    prompt = os.getenv("PROMPT_INTRO", DEFAULT_INTRO_PROMPT).format(article_summaries=summaries)
    intro = generate_text_with_fallback(prompt=prompt, gemini_model="gemini-2.0-flash").strip()
    if not intro:
        intro = "Here's what's making waves in AI today."
    upsert_digest_extra(
        digest_date=digest_date,
        key="digest_intro",
        payload={
            "text": intro,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return intro


def _render_frontmatter(
    digest_date: str,
    subject: str,
    intro: str,
    sections: List[dict],
    tweet_count: int,
    community_count: int,
) -> str:
    lines = [
        "---",
        f"digest_date: {_yaml_quote(digest_date)}",
        f"subject: {_yaml_quote(subject)}",
        f"intro: {_yaml_quote(intro)}",
        f"article_count: {sum(len(s['articles']) for s in sections)}",
        f"tweet_headline_count: {tweet_count}",
        f"community_headline_count: {community_count}",
        "sections:",
    ]
    for section in sections:
        lines.append(f"  - name: {_yaml_quote(section['name'])}")
        lines.append(f"    article_count: {len(section['articles'])}")
    lines.extend(
        [
            "build_meta:",
            f"  generated_at: {_yaml_quote(datetime.now(timezone.utc).isoformat())}",
            "  source_window_hours: 24",
            "  version: \"digest-md-v1\"",
            "---",
            "",
        ]
    )
    return "\n".join(lines)


def _render_body(sections: List[dict], tweet_headlines: List[dict], community_headlines: List[dict]) -> str:
    parts: List[str] = []
    for section in sections:
        parts.append(f"## {section['name']}\n")
        for article in section["articles"]:
            embedded_payload = _extract_embedded_payload(str(article.get("summary", "")))
            normalized_summary = (
                str(embedded_payload.get("summary", "")).strip()
                if embedded_payload
                else str(article.get("summary", "No summary available.")).strip()
            )
            normalized_opinion = (
                str(article.get("opinion", "")).strip()
                or str(embedded_payload.get("opinion", "")).strip()
            )
            normalized_topic = (
                str(article.get("topic", "")).strip()
                or str(embedded_payload.get("topic", "")).strip()
            )

            parts.append(f"### [{article.get('title', 'Untitled')}]({article.get('url', '#')})")
            parts.append(f"*{article.get('source', 'Unknown Source')}*")
            article_payload = {
                "topic": normalized_topic,
                "summary": normalized_summary or "No summary available.",
                "opinion": normalized_opinion,
                "confidence": article.get("confidence"),
                "image_url": article.get("image_url") or "",
            }
            parts.append("```json")
            parts.append(json.dumps(article_payload, ensure_ascii=False, indent=2))
            parts.append("```")
            parts.append("")

    if tweet_headlines:
        parts.append("## From X/Twitter\n")
        for item in tweet_headlines:
            headline = item.get("headline", "")
            url = item.get("url", "")
            parts.append(f"- {headline} ([Source]({url}))")
        parts.append("")

    if community_headlines:
        parts.append("## From Reddit/HN/YC\n")
        for item in community_headlines:
            source = item.get("source_label", "Community")
            headline = item.get("headline", "")
            url = item.get("url", "")
            parts.append(f"- [{source}] {headline} ([Source]({url}))")
        parts.append("")

    return "\n".join(parts).strip() + "\n"


def build_digest_markdown(digest_date: Optional[str] = None, window_hours: int = 24) -> Tuple[Path, int]:
    if digest_date:
        target_date = datetime.strptime(digest_date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now(timezone.utc).date()
    safe_date = target_date.isoformat()

    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    articles = get_unsent_articles(topic=None, require_summary=True, since=since, until=None)
    sections = _group_articles_by_category(articles)

    subject = f"AI Newsy • {target_date.strftime('%b %d')} • {len(articles)} Stories"
    intro = _get_or_create_intro(digest_date=safe_date, articles=articles) if articles else "No stories selected."

    tweet_extra = get_digest_extra(digest_date=safe_date, key="tweet_headlines") or {}
    tweet_headlines = (tweet_extra.get("payload") or {}).get("headlines", []) if isinstance(tweet_extra.get("payload"), dict) else []
    community_extra = get_digest_extra(digest_date=safe_date, key="community_headlines") or {}
    community_headlines = (community_extra.get("payload") or {}).get("headlines", []) if isinstance(community_extra.get("payload"), dict) else []

    frontmatter = _render_frontmatter(
        digest_date=safe_date,
        subject=subject,
        intro=intro,
        sections=sections,
        tweet_count=len(tweet_headlines),
        community_count=len(community_headlines),
    )
    body = _render_body(sections, tweet_headlines=tweet_headlines, community_headlines=community_headlines)

    output_dir = Path(os.getenv("DIGEST_MARKDOWN_DIR", "data/digests"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{safe_date}.md"
    output_path.write_text(frontmatter + body, encoding="utf-8")
    print(f"Wrote digest markdown: {output_path}")
    return output_path, len(articles)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build daily digest markdown from storage")
    parser.add_argument("--digest-date", type=str, default=None, help="YYYY-MM-DD (UTC)")
    parser.add_argument("--window-hours", type=int, default=int(os.getenv("DIGEST_WINDOW_HOURS", "24")))
    args = parser.parse_args()
    path, count = build_digest_markdown(digest_date=args.digest_date, window_hours=args.window_hours)
    print(f"Done. articles={count} markdown={path}")

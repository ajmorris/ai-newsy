"""Shared digest-to-email renderer payload helpers."""

from __future__ import annotations

import os
import re
import json
from typing import Dict, List, Optional

from execution.story_text_normalizer import normalize_story_text

APP_URL = os.getenv("APP_URL", "https://your-app.vercel.app")
DEFAULT_CATEGORY = "Other AI News"


def _issue_number_from_digest_date(digest_date: str) -> str:
    """Build the short issue number from a YYYY-MM-DD digest date."""
    return "".join(ch for ch in digest_date if ch.isdigit())[-5:] or "00137"


def _parse_story_json_blob(raw_text: str) -> Optional[Dict[str, object]]:
    """Parse JSON story payloads that may be wrapped in markdown fences."""
    text = (raw_text or "").strip()
    if not text:
        return None

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*```$", "", text, count=1).strip()

    if not text.startswith("{"):
        match = re.search(r"(\{[\s\S]*\})", text)
        if not match:
            return None
        text = match.group(1).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    if not any(key in payload for key in ("summary", "opinion", "image_url", "topic")):
        return None
    return payload


def normalize_article_for_email(article: Dict[str, object]) -> Dict[str, object]:
    """Normalize article fields so renderers receive clean summary/opinion/image values."""
    normalized = dict(article)
    summary = str(normalized.get("summary", "") or "").strip()
    opinion = str(normalized.get("opinion", "") or "").strip()
    image_url = str(normalized.get("image_url", "") or "").strip()

    parsed = _parse_story_json_blob(summary) or _parse_story_json_blob(opinion)
    if parsed:
        parsed_summary = str(parsed.get("summary", "") or "").strip()
        parsed_opinion = str(parsed.get("opinion", "") or "").strip()
        parsed_image = str(parsed.get("image_url", "") or "").strip()
        parsed_topic = str(parsed.get("topic", "") or "").strip()

        if parsed_summary:
            summary = parsed_summary
        if parsed_opinion:
            opinion = parsed_opinion
        if parsed_image:
            image_url = parsed_image
        if parsed_topic and not str(normalized.get("topic", "") or "").strip():
            normalized["topic"] = parsed_topic

    normalized["summary"] = normalize_story_text(summary, max_chars=900)
    normalized["opinion"] = normalize_story_text(opinion, max_chars=500)
    normalized["image_url"] = image_url
    return normalized


def build_email_renderer_payload(
    sections: List[dict],
    intro: str,
    subject: str,
    unsubscribe_token: str,
    digest_date: str,
    tweet_headlines: Optional[List[dict]] = None,
    community_headlines: Optional[List[dict]] = None,
    what_reading: Optional[Dict[str, object]] = None,
    what_watching: Optional[Dict[str, object]] = None,
    around_web: Optional[List[dict]] = None,
) -> Dict[str, object]:
    stories: List[Dict[str, str]] = []
    for section in sections:
        section_name = section.get("name", DEFAULT_CATEGORY)
        for article in section.get("articles", []):
            normalized_article = normalize_article_for_email(article)
            stories.append(
                {
                    "tag": section_name,
                    "source": normalized_article.get("source", "Unknown Source"),
                    "read": normalized_article.get("reading_time", ""),
                    "headline": normalized_article.get("title", "Untitled"),
                    "summary": normalized_article.get("summary", ""),
                    "why": normalized_article.get("opinion", ""),
                    "url": normalized_article.get("url", "#"),
                    "imageUrl": normalized_article.get("image_url", ""),
                }
            )

    tweet_quick_hits: List[Dict[str, str]] = []
    for item in (tweet_headlines or [])[:6]:
        headline = str(item.get("headline", "") or "").strip()
        if headline:
            tweet_quick_hits.append(
                {
                    "headline": headline,
                    "url": str(item.get("url", "") or "").strip(),
                }
            )

    community_quick_hits: List[Dict[str, str]] = []
    for item in (community_headlines or [])[:6]:
        headline = str(item.get("headline", "") or "").strip()
        if headline:
            community_quick_hits.append(
                {
                    "headline": headline,
                    "url": str(item.get("url", "") or "").strip(),
                }
            )

    issue_number = _issue_number_from_digest_date(digest_date)
    archive_url = f"{APP_URL}/issues/"
    around_web_hits: List[Dict[str, str]] = []
    for item in (around_web or [])[:12]:
        headline = str(item.get("headline", "") or "").strip()
        if not headline:
            continue
        around_web_hits.append(
            {
                "headline": headline,
                "url": str(item.get("url", "") or "").strip(),
                "sourceLabel": str(item.get("source_label", "") or "").strip(),
            }
        )

    return {
        "subject": subject,
        "intro": intro,
        "heroHeadline": "What I am learning in AI today.",
        "dateLabel": digest_date,
        "issueNumber": issue_number,
        "stories": stories[:8],
        "tweetHeadlines": tweet_quick_hits,
        "communityHeadlines": community_quick_hits,
        "whatReading": what_reading or {},
        "whatWatching": what_watching or {},
        "aroundWebHeadlines": around_web_hits,
        "unsubscribeUrl": f"{APP_URL}/api/unsubscribe?token={unsubscribe_token}",
        "viewInBrowserUrl": f"{APP_URL}/issues/{digest_date}.html",
        "archiveUrl": archive_url,
        "forwardUrl": archive_url,
    }

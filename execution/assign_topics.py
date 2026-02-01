"""
Assign topic to articles at ingest (topic only; no summary or opinion).
Run after fetch_ai_news (or on a schedule) so new articles get a topic before digest selection.
"""

import os
import argparse
import time
from dotenv import load_dotenv
import google.generativeai as genai

import sys
sys.path.insert(0, '.')
from execution.database import get_articles_without_topic, update_article_topic

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

TOPICS = [
    "Models",
    "Agents & Tools",
    "MCP & SKILLs",
    "Safety",
    "Industry",
]

# Topic classification prompt (override via PROMPT_TOPIC env var)
DEFAULT_TOPIC_PROMPT = """You are classifying AI news articles into exactly one topic for a daily newsletter.

Topics (respond with ONLY one of these exact labels):
- Models
- Agents & Tools
- MCP & SKILLs
- Safety
- Industry

Given the article title and optionally a short snippet, respond with exactly one topic label from the list above. No explanation, just the topic."""

TOPIC_PROMPT = os.getenv("PROMPT_TOPIC", DEFAULT_TOPIC_PROMPT)


def assign_topic_for_article(title: str, content_snippet: str = "") -> str:
    """Call Gemini to assign one topic. Returns topic label or 'Industry' as fallback."""
    try:
        context = f"Title: {title}"
        if content_snippet:
            context += f"\nSnippet: {content_snippet[:500]}"
        response = model.generate_content(f"{TOPIC_PROMPT}\n\n{context}")
        text = (response.text or "").strip()
        for t in TOPICS:
            if t.lower() in text.lower() or text == t:
                return t
        return "Industry"
    except Exception:
        return "Industry"


def assign_all(dry_run: bool = False, limit: int = None) -> int:
    """Assign topic to all articles that don't have one. Returns count updated."""
    articles = get_articles_without_topic(limit=limit)
    if not articles:
        print("No articles without topic.")
        return 0
    print(f"\nAssigning topics to {len(articles)} article(s)...\n")
    updated = 0
    for article in articles:
        title = article.get("title", "")
        content = (article.get("content") or "")[:500]
        article_id = article.get("id")
        topic = assign_topic_for_article(title, content)
        print(f"  [{article_id}] {title[:50]}... -> {topic}")
        if not dry_run:
            update_article_topic(article_id, topic)
            updated += 1
        time.sleep(0.3)
    return updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assign topic to articles (ingest only)")
    parser.add_argument("--dry-run", action="store_true", help="Print only, do not update")
    parser.add_argument("--limit", type=int, default=None, help="Max articles to process")
    args = parser.parse_args()
    if not os.getenv("GEMINI_API_KEY"):
        print("GEMINI_API_KEY not set in .env")
        exit(1)
    n = assign_all(dry_run=args.dry_run, limit=args.limit)
    print(f"\nDone. Assigned topic to {n} article(s).")

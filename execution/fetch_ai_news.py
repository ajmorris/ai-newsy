"""
Fetch AI News from RSS Feeds
Aggregates AI-related news from RSS feeds and stores in Supabase.
Feeds are loaded from directives/fetch_ai_news.md (primary) and feed_urls.md (fallback + additional).
"""

import argparse
import time
from datetime import datetime
import feedparser
import requests
from bs4 import BeautifulSoup

# Import from our database module
import sys
sys.path.insert(0, '.')
from execution.database import add_article, get_article_count
from execution.feed_config import get_merged_feeds

# Keywords to filter AI-related content (for general feeds)
AI_KEYWORDS = [
    'ai', 'artificial intelligence', 'machine learning', 'deep learning',
    'neural network', 'gpt', 'llm', 'chatgpt', 'openai', 'anthropic',
    'claude', 'gemini', 'transformer', 'generative ai', 'diffusion',
    'stable diffusion', 'midjourney', 'copilot', 'automation'
]


def is_ai_related(title: str, summary: str = "") -> bool:
    """Check if content is AI-related based on keywords."""
    text = f"{title} {summary}".lower()
    return any(keyword in text for keyword in AI_KEYWORDS)


def _entry_link(entry) -> str:
    """Get entry URL; works for RSS (entry.link) and ATOM (entry.links)."""
    link = entry.get("link", "").strip()
    if link:
        return link
    links = entry.get("links") or []
    for lnk in links:
        href = lnk.get("href", "").strip() if isinstance(lnk, dict) else getattr(lnk, "href", "")
        if href:
            return href
    return ""


def _entry_summary(entry) -> str:
    """Get entry summary/content; works for RSS (summary/description) and ATOM (summary or content[].value)."""
    summary = entry.get("summary") or entry.get("description") or ""
    if summary:
        return summary
    content = entry.get("content") or []
    if content and len(content) > 0:
        first = content[0]
        if isinstance(first, dict):
            return first.get("value", "")
        return getattr(first, "value", "")
    return ""


def _parse_feed_url(url: str):
    """
    Fetch feed from URL and parse as RSS/ATOM. Uses requests so we can handle
    servers (e.g. raw.githubusercontent.com) that return Content-Type: text/plain
    for XML files, which feedparser rejects when it fetches the URL directly.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AI-Newsy/1.0; +https://github.com/ajmorris/ai-newsy)"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    # Pass content so feedparser doesn't see the server's Content-Type; treat as XML
    return feedparser.parse(
        response.content,
        response_headers={"content-type": "application/xml; charset=utf-8"},
    )


def fetch_feed(feed_config: dict, limit: int = 10) -> list:
    """
    Fetch articles from a single RSS feed.
    feed_config: {"name", "source", "primary_url", "fallback_url" (optional)}.
    Tries primary_url first; if that fails (exception, bozo, or no entries), tries fallback_url.
    Returns list of article dicts.
    """
    articles = []
    primary_url = feed_config["primary_url"]
    fallback_url = feed_config.get("fallback_url")
    source = feed_config["source"]
    name = feed_config["name"]

    for url_to_try, is_fallback in [(primary_url, False), (fallback_url, True)]:
        if url_to_try is None:
            continue
        try:
            print(f"  Fetching: {name}{' (fallback)' if is_fallback else ''}...")
            feed = _parse_feed_url(url_to_try)

            if feed.bozo and feed.bozo_exception:
                err = getattr(feed.bozo_exception, "message", str(feed.bozo_exception))[:80]
                if is_fallback:
                    print(f"    Warning: Fallback feed also failed - {err}")
                    break
                print(f"    Parse error (trying fallback): {err}")
                continue
            entries = getattr(feed, "entries", None) or []
            if len(entries) == 0:
                if is_fallback:
                    print(f"    Fallback returned 0 entries")
                    break
                print(f"    0 entries (trying fallback)" if fallback_url else f"    0 entries")
                continue

            for entry in entries[:limit]:
                title = (entry.get("title") or "").strip()
                url = _entry_link(entry)
                summary = _entry_summary(entry)

                if summary:
                    soup = BeautifulSoup(summary, "html.parser")
                    summary = soup.get_text()[:500]

                if not title or not url:
                    continue

                if 'ai' not in name.lower():
                    if not is_ai_related(title, summary):
                        continue

                articles.append({
                    'url': url,
                    'title': title,
                    'source': source,
                    'content': summary
                })

            print(f"    Found {len(articles)} articles")
            break
        except Exception as e:
            if is_fallback:
                print(f"    Error fetching {name} (fallback): {e}")
                break
            print(f"    Primary failed: {e}, trying fallback...")
    if not articles:
        print(f"    No articles from {name}")
    return articles


def fetch_all_feeds(limit_per_feed: int = 10, dry_run: bool = False) -> int:
    """
    Fetch from all configured RSS feeds.
    Feed list is loaded from directives/fetch_ai_news.md and feed_urls.md (merged, de-duped).
    Returns total count of new articles added.
    """
    print(f"\n{'='*50}")
    print(f"AI News Fetch - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    feeds = get_merged_feeds()
    print(f"Loaded {len(feeds)} feeds (directive + feed_urls, de-duped)\n")

    total_new = 0
    total_found = 0

    for feed_config in feeds:
        articles = fetch_feed(feed_config, limit=limit_per_feed)
        total_found += len(articles)
        
        for article in articles:
            if dry_run:
                print(f"    [DRY RUN] Would add: {article['title'][:60]}...")
                total_new += 1
            else:
                result = add_article(
                    url=article['url'],
                    title=article['title'],
                    source=article['source'],
                    content=article['content']
                )
                if result:
                    print(f"    ✓ Added: {article['title'][:60]}...")
                    total_new += 1
                # If result is None, article already exists (dedup)
        
        # Small delay between feeds to be polite
        time.sleep(0.5)
    
    print(f"\n{'='*50}")
    print(f"Summary: Found {total_found} articles, added {total_new} new")
    print(f"Total articles in database: {get_article_count()}")
    print(f"{'='*50}\n")
    
    return total_new


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI news from RSS feeds")
    parser.add_argument('--dry-run', action='store_true', 
                        help="Print articles without inserting")
    parser.add_argument('--limit', type=int, default=10,
                        help="Max articles per feed (default: 10)")
    args = parser.parse_args()
    
    new_count = fetch_all_feeds(
        limit_per_feed=args.limit,
        dry_run=args.dry_run
    )
    
    print(f"Done! Added {new_count} new articles.")

"""
Fetch AI News from RSS Feeds
Aggregates AI-related articles and stores in Supabase.
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

# AI-related RSS feeds
RSS_FEEDS = [
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "source": "TechCrunch"
    },
    {
        "name": "The Verge AI", 
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "source": "The Verge"
    },
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "source": "Ars Technica"
    },
    {
        "name": "MIT Tech Review AI",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
        "source": "MIT Tech Review"
    },
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
        "source": "VentureBeat"
    }
]

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


def fetch_feed(feed_config: dict, limit: int = 10) -> list:
    """
    Fetch articles from a single RSS feed.
    Returns list of article dicts.
    """
    articles = []
    try:
        print(f"  Fetching: {feed_config['name']}...")
        feed = feedparser.parse(feed_config['url'])
        
        if feed.bozo and feed.bozo_exception:
            print(f"    Warning: Feed parsing issue - {feed.bozo_exception}")
        
        for entry in feed.entries[:limit]:
            # Extract basic info
            title = entry.get('title', '').strip()
            url = entry.get('link', '').strip()
            summary = entry.get('summary', '') or entry.get('description', '')
            
            # Clean up summary (remove HTML)
            if summary:
                soup = BeautifulSoup(summary, 'html.parser')
                summary = soup.get_text()[:500]  # Limit length
            
            if not title or not url:
                continue
                
            # Filter for AI-related content (some feeds are general tech)
            if 'ai' not in feed_config['name'].lower():
                if not is_ai_related(title, summary):
                    continue
            
            articles.append({
                'url': url,
                'title': title,
                'source': feed_config['source'],
                'content': summary
            })
            
        print(f"    Found {len(articles)} articles")
        
    except Exception as e:
        print(f"    Error fetching {feed_config['name']}: {e}")
    
    return articles


def fetch_all_feeds(limit_per_feed: int = 10, dry_run: bool = False) -> int:
    """
    Fetch from all configured RSS feeds.
    Returns total count of new articles added.
    """
    print(f"\n{'='*50}")
    print(f"AI News Fetch - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")
    
    total_new = 0
    total_found = 0
    
    for feed_config in RSS_FEEDS:
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

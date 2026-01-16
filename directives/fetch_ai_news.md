# Fetch AI News Directive

## Purpose
Aggregate AI-related news from RSS feeds and store in Supabase for daily digest.

## Inputs
- RSS feed URLs (configured in .env or hardcoded)
- Supabase credentials

## Execution
Run: `python3 execution/fetch_ai_news.py`

Options:
- `--dry-run` - Print found articles without inserting
- `--limit N` - Limit to N articles per source

## Sources
Current RSS feeds:
- TechCrunch AI: https://techcrunch.com/category/artificial-intelligence/feed/
- The Verge AI: https://www.theverge.com/rss/ai-artificial-intelligence/index.xml
- Ars Technica AI: https://feeds.arstechnica.com/arstechnica/technology-lab
- MIT Tech Review AI: https://www.technologyreview.com/topic/artificial-intelligence/feed

## Output
- New articles inserted into `articles` table
- Returns count of new articles found
- Duplicates are automatically skipped (by URL)

## Edge Cases
- Feed unavailable: Log warning, continue with other feeds
- Malformed entry: Skip and log
- Rate limiting: Built-in delays between fetches

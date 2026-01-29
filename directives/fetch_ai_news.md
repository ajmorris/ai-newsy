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
- Science Daily: https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml
- TechCrunch AI: https://techcrunch.com/category/artificial-intelligence/feed/
- NY Times: https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/spotlight/artificial-intelligence/rss.xml
- Guardian AI: https://www.theguardian.com/technology/artificialintelligenceai/rss
- DeepMind Blog: https://deepmind.google/blog/rss.xml
- Google AI Blog: http://googleaiblog.blogspot.com/atom.xml
- The Rundown AI: https://rss.beehiiv.com/feeds/2R3C6Bt5wj.xml
- The Verge AI: https://www.theverge.com/rss/ai-artificial-intelligence/index.xml
- Ars Technica AI: https://feeds.arstechnica.com/arstechnica/technology-lab
- MIT Tech Review AI: https://www.technologyreview.com/topic/artificial-intelligence/feed
- OpenAI: https://openai.com/news/rss.xml

## Output
- New articles inserted into `articles` table
- Returns count of new articles found
- Duplicates are automatically skipped (by URL)

## Edge Cases
- Feed unavailable: Log warning, continue with other feeds
- Malformed entry: Skip and log
- Rate limiting: Built-in delays between fetches

# Feed troubleshooting

The fetcher supports **RSS and ATOM** feeds. For ATOM, it reads the entry URL from `entry.link` or `entry.links[].href`, and summary from `entry.summary`/`entry.description` or `entry.content[].value`.

If a feed shows **0 entries** or **No articles** when you run `fetch_ai_news.py`, use this to track it down.

## 1. See why each feed failed

After the recent change, the fetcher now logs:

- **Parse error (trying fallback)** – feed URL returned invalid or non-RSS XML
- **0 entries** – feed parsed but had no `<item>` entries
- **Primary failed: …** – request failed (timeout, 404, etc.)
- **No articles from &lt;name&gt;** – nothing usable after primary (and fallback if any)

Re-run fetch and look at the lines right under each "Fetching: …" to see which of these applies.

## 2. Check feed URLs directly

From repo root:

```bash
python3 scripts/check_feeds.py
```

This hits each primary URL and prints **OK** + entry count or **FAIL** + error. Use it to see which feeds are down, empty, or returning bad XML.

## 3. Feeds that come from feed_urls.md

These names are **only** in `feed_urls.md` (not in the directive). Their URLs point to your `rss-feeds` repo:

- Anthropic News  
- Claude Code Changelog  
- xAI News  
- Cursor Blog  
- Windsurf Blog  
- Ollama  
- Paul Graham  
- Dagster  
- Hamel Husain  
- Surge AI  
- Thinking Machines  
- Chander Ramesh  

URL pattern:  
`https://raw.githubusercontent.com/ajmorris/rss-feeds/main/feeds/feed_*.xml`

If a feed shows **0 entries** or a **parse error**:

1. Open that URL in a browser (or `curl -s "URL"`) and confirm the file exists and is valid RSS/Atom XML.
2. In the `rss-feeds` repo, check that the corresponding file exists, is committed, and has at least one `<item>` (or Atom equivalent).
3. If the file is empty or not yet populated, either fix the source or remove/comment that feed in `feed_urls.md` until it’s ready.

## 4. Directive feeds (directives/fetch_ai_news.md)

Feeds listed under "Current RSS feeds" in the directive use those URLs as primary. If a feed fails, check that the URL is still valid and returns RSS/Atom (e.g. in a browser or with `curl`).

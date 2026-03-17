# How Articles Are Picked for the Daily Digest

## Step-by-step logic

1. **Pool: recent, unsent, summarized articles only**
   - `get_unsent_articles()` returns every article where:
     - `summary` is not null (has been summarized), and
     - `sent_at` is null (has not been sent in any digest yet).
   - The daily digest caller now passes a **time window** (by default, the last 24 hours) using a `since` value on `fetched_at`. That means the pool is effectively “unsent articles fetched in the last N hours.”

2. **Cap per source**
   - `get_unsent_articles_for_digest(max_per_source=3, since=...)`:
     - Groups the time-windowed pool by `source` (e.g. "Guardian AI", "NY Times").
     - For each source, keeps only the **newest** `max_per_source` articles (by `fetched_at`).
     - So each source can contribute at most `max_per_source` articles (2 by default).

3. **Interleaving by source**
   - All capped articles are merged using **round-robin by source** so the same publication does not appear back-to-back (e.g. Guardian, NYT, Science Daily, DeepMind, Guardian, …).

4. **Grouping into sections**
   - The flat list from `get_unsent_articles_for_digest` is grouped in memory by topic/category before rendering:
     - Each article’s `topic` is mapped to a reader-facing category (for example, `"Models"` → `"Model Releases & Capabilities"`).
     - Articles without a recognized topic fall into an `"Other AI News"` bucket.
   - The email template renders one section per category, with a heading and that category’s articles beneath.

## Why one publication is less likely to dominate

- **“Recent and unsent” instead of “all unsent”**  
  Only unsent articles fetched within the configured time window (typically 24h) are considered. This keeps the digest focused on what’s new.

- **Per-source caps still apply**  
  High-volume feeds can still contribute multiple pieces, but the cap (default 2) prevents them from flooding the digest.

- **Round-robin ordering across sources**  
  Because the final list is interleaved by source, you won’t see long runs of the same publication even when it has many recent stories.

## Summary

| Factor | Behavior |
|--------|----------|
| Pool | Unsent, summarized articles fetched within the configured time window (default 24h) |
| Cap | Up to 2 per source by default; override with env `DIGEST_MAX_PER_SOURCE` |
| Order | **Round-robin by source** so the same publication does not appear consecutively |
| Time window | Applied via `since` on `fetched_at` (UTC) |
| Grouping | Articles are grouped into topic-based sections in the email based on their `topic` → category mapping |

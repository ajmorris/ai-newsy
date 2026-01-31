# How Articles Are Picked for the Daily Digest

## Step-by-step logic

1. **Pool: unsent, summarized articles only**
   - `get_unsent_articles()` returns every article where:
     - `summary` is not null (has been summarized), and
     - `sent_at` is null (has not been sent in any digest yet).
   - There is **no “today only” filter**. The pool is all unsent articles, which can span multiple days if the digest hasn’t run or if we’re backlogged.

2. **Cap per source**
   - `get_unsent_articles_for_digest(max_per_source=3)`:
     - Groups the pool by `source` (e.g. "Guardian AI", "NY Times").
     - For each source, keeps only the **newest** `max_per_source` articles (by `fetched_at`).
     - So each source can contribute at most 3 articles (with the current default).

3. **Final order**
   - All capped articles are merged and sorted by **`fetched_at` descending** (newest first).
   - There is **no interleaving by source**. So if NY Times had 3 articles fetched close together, all 3 can appear back-to-back in the email.

## Why one publication can dominate

- **Yes, it’s “articles that had not been sent yet”**  
  Only unsent, summarized articles are considered. So the mix you see is exactly “whatever was unsent at send time.”

- **High-volume feeds accumulate in the pool**  
  Feeds that publish a lot (e.g. NY Times, Guardian) tend to have more unsent articles. After capping at 3 per source, they can still contribute 3 each. With **global sort by `fetched_at`**, articles from the same source often sit next to each other, so the email can feel dominated by one or two publications.

- **No “latest today” filter**  
  We don’t restrict to “today’s” or “last 24h” articles. So the digest reflects “all unsent so far,” not “only what’s new today.” That can make high-output feeds look even more dominant.

## Summary (after fix)

| Factor | Behavior |
|--------|----------|
| Pool | All unsent, summarized articles (any age) |
| Cap | Up to 2 per source by default; override with env `DIGEST_MAX_PER_SOURCE` |
| Order | **Round-robin by source** so the same publication does not appear consecutively (e.g. Guardian, NYT, Science Daily, DeepMind, Guardian, …) |
| “Today only” | Not applied |

So no single source can contribute more than 2 articles (unless you raise `DIGEST_MAX_PER_SOURCE`), and the email order alternates across sources to avoid runs of the same publication.

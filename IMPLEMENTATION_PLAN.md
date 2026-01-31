# AI Newsy Implementation Plan

Phases 1–6 are **done**. Phase 7 (human-in-the-loop topic selection) is **future** and not in scope.

---

## Completed (reference only)

- **Phase 1**: RSS from directive + feed_urls, merge/de-dupe, fallback in fetch (`execution/feed_config.py`, `execution/fetch_ai_news.py`).
- **Phase 2**: `opinion` and `image_url` on `articles` (`supabase_schema.sql`).
- **Phase 3**: `get_unsent_articles_for_digest(max_per_source=2, interleave=True)`, used in send_daily_email; directive note.
- **Phase 4**: Split RSS vs X, "Latest from socials" section, link/takeaway styling in `send_daily_email.py`.
- **Phase 5**: `extract_og_image`, `update_article_image`, wired in summarization; images in email HTML.
- **Phase 6**: Topic-based newsletter: `topic` on articles, `digests` table, `execution/assign_topics.py`, `choose_topic_for_today()` + rotation, JIT summarization (`summarize_selected`), send_daily_email wired (choose topic → get articles → JIT summarize → send → record topic).

**Max per source**: 2 (default in code and env `DIGEST_MAX_PER_SOURCE`).

---

## AI call optimization (ingest vs newsletter)

- **At ingest**: Use the AI **only to set the topic**. One lightweight Gemini call per article. Do **not** summarize or form an opinion at ingest.
- **When building the newsletter**: Run summary + opinion (and image extraction if needed) **only for articles selected** for that day's digest (just-in-time).

---

## Phase 6: Topic-Based Newsletter (done)

**Goal**: Assign each article a topic at ingest (topic only); choose one topic per day for the digest; build the digest and run summary/opinion only for articles selected for that day.

**Implemented**: Schema (`topic` on articles, `digests` table); `execution/assign_topics.py`; `get_unsent_articles_for_digest(..., topic=...)`, digest log insert/query; `choose_topic_for_today()` in send_daily_email; `summarize_selected()` in summarize_articles for JIT; send_daily_email flow: choose topic → get articles for topic → JIT summarize if needed → send → record topic. Daily pipeline: fetch → assign_topics → (summarize optional) → send_daily_email.

---

## Phase 7: Human-in-the-loop topic selection (Future)

- **Goal**: After Phase 6 and stable enrichment/feeds, allow choosing the newsletter topic each day (e.g. Slack bot that asks for topic options and stores the choice for the next digest).
- **Not in current scope.**

---

## Remaining (optional / future)

- **Phase 7**: Slack bot or similar to choose tomorrow’s topic (human-in-the-loop). Add when you want to override automatic topic selection.
- **Daily workflow**: Ensure GitHub Actions runs `assign_topics` after fetch so new articles get a topic before send (see `.github/workflows/daily_digest.yml`).

# Implementation Tasks

Phases 1–6 are **done**. Phase 7 is **future** (not in scope).

---

## Completed (Phases 1–6)

- **Phase 1**: RSS source of truth (directive + feed_urls, merge, fallback), feed_config, fetch_ai_news.
- **Phase 2**: Schema `opinion`, `image_url` on articles; migration applied.
- **Phase 3**: `get_unsent_articles_for_digest(max_per_source=2, interleave=True)`, used in send_daily_email; directive note.
- **Phase 4**: Split RSS vs X, "Latest from socials" section, link/takeaway styling.
- **Phase 5**: `extract_og_image`, `update_article_image`, wired in summarization; images in email.
- **Phase 6**: Topic-based newsletter: `topic` on articles, `digests` table, `assign_topics.py`, `choose_topic_for_today()` + rotation, JIT summarization (`summarize_selected`), send_daily_email wired; daily workflow includes assign_topics after fetch.

---

## Remaining (optional / future)

- **Phase 7**: Human-in-the-loop topic selection (e.g. Slack bot to choose tomorrow’s topic). Implement after Phase 6 is stable and when you want manual topic override.
- **Ongoing**: Run migration for topic + digests if not applied; ensure `.env` has `DIGEST_TOPIC_COOLDOWN_DAYS` if you want to change topic rotation (default 5 days).

---

## Daily pipeline (local and GitHub)

1. `python execution/fetch_ai_news.py`
2. `python execution/assign_topics.py`
3. `python execution/fetch_x_posts.py` (optional)
4. `python execution/summarize_articles.py` (optional; JIT in send also summarizes selected articles)
5. `python execution/send_daily_email.py`

GitHub Actions (`.github/workflows/daily_digest.yml`) runs this sequence on schedule and on workflow_dispatch.

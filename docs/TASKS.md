# Implementation Tasks

Phases 1–6 are **done**. Phase 7 is **future** (not in scope).

---

## Completed (Phases 1–6)

- **Phase 1**: RSS source of truth (directive + feed_urls, merge, fallback), feed_config, fetch_ai_news.
- **Phase 2**: Schema `opinion`, `image_url` on articles; migration applied.
- **Phase 3**: `get_unsent_articles_for_digest(max_per_source=2, interleave=True)`, used in send_daily_email; directive note.
- **Phase 4**: Link/takeaway styling in email.
- **Phase 5**: `extract_og_image`, `update_article_image`, wired in summarization; images in email.
- **Phase 6**: Topic-based newsletter: `topic` on articles, `digests` table, `assign_topics.py`, `choose_topic_for_today()` + rotation, JIT summarization (`summarize_selected`), send_daily_email wired; daily workflow includes assign_topics after fetch.

---

## Remaining (optional / future)

- **Phase 7**: Human-in-the-loop topic selection (e.g. Slack bot to choose tomorrow’s topic). Implement after Phase 6 is stable and when you want manual topic override.
- **Ongoing**: Run migration for topic + digests if not applied; ensure `.env` has `DIGEST_TOPIC_COOLDOWN_DAYS` if you want to change topic rotation (default 5 days).

---

## Daily pipeline (local Claude Opus 5, then Vercel)

Preferred:

```bash
./scripts/run_local_digest.sh
./scripts/run_local_digest.sh --commit
git push origin main
```

Equivalent individual steps:

1. `python execution/fetch_ai_news.py`
2. `python execution/analyze_articles_single_pass.py` (Claude Opus 5)
3. `python execution/generate_tweet_headlines.py` (pulls last 24h saved tweets from Notion and stores digest extras)
4. `python execution/generate_community_headlines.py` (pulls Reddit/HN/YC posts and stores `community_headlines` extra)
5. `python execution/digest_payload.py`
6. `python execution/build_web_archive.py --use-canonical-fallback`
7. Optional: `python execution/send_daily_email.py --test-email you@example.com`

Remaining GitHub Actions:
- `.github/workflows/prepare_digest_content.yml` (fetch + Claude analysis + canonical JSON)
- `.github/workflows/prepare_twitter_headlines.yml` / `prepare_community_headlines.yml`
- `.github/workflows/publish_web_archive.yml`
- `.github/workflows/daily_digest.yml` (send from committed JSON; generate in CI if missing)
- `.github/workflows/cleanup_old_articles.yml` (weekly retention)

Extras are persisted in `digest_extras` under keys:
- `tweet_headlines`
- `community_headlines`

---

## Article cleanup (30-day retention)

Articles older than **30 days** (by `fetched_at`) are deleted to keep the database lean.

- **Script**: `python execution/cleanup_old_articles.py` (default 30 days; override with `--days N` or env `ARTICLE_RETENTION_DAYS`).
- **Dry run**: `python execution/cleanup_old_articles.py --dry-run` to see how many would be deleted.
- **Schedule**: GitHub Action `.github/workflows/cleanup_old_articles.yml` runs **weekly** (Sunday 1:00 UTC). Set `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in repo secrets; optional repo variable `ARTICLE_RETENTION_DAYS` (default 30).

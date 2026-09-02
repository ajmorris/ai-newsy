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

## Daily pipeline (Claude Desktop, then Vercel + Resend Action)

One-time: paste `prompts/setup-claude-desktop.md` into Claude Desktop.

Each scheduled morning:

1. `./scripts/run_local_digest.sh --fetch`
2. Claude Desktop writes `.tmp/claude-digest.json` (analyses, intro, headlines)
3. `./scripts/run_local_digest.sh --assemble --commit`
4. `git push origin main` (digest JSON **and** `frontend/issues/`; Vercel deploys first)
5. Scheduled `daily_digest.yml` at 09:00 UTC sends via Resend (`--no-llm`) and commits sent snapshots

Refresh the Desktop scheduled-task Instructions after this SOP changes on `main`.

Local QA (no Anthropic API; stand-ins for the deleted test/parity Actions):

```bash
./scripts/validate_digest_parity_local.sh
./scripts/test_email_local.sh you@example.com
```

Remaining GitHub Actions:
- `.github/workflows/daily_digest.yml` (send-only from committed JSON, then snapshot commit)
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

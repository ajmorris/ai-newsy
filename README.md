# AI Newsy

AI Newsy is an AI-news ingestion and digest system:

- Collects AI articles from RSS sources
- Enriches them with topic/summary/opinion analysis
- Adds curated social/community headline extras
- Builds a daily digest markdown artifact
- Sends the digest via email and publishes a web archive

## Repository Layout

- `execution/`: Python pipeline scripts (ingest, analysis, digest build/send, archive, cleanup)
- `scripts/`: local digest runner, RSS feed checks, and parity helpers
- `directives/`: operator SOPs (`setup_claude_desktop.md`, `run_daily_digest.md`; `publish_daily_digest.md` is superseded)
- `prompts/`: one-time Claude Desktop setup (`setup-claude-desktop.md`; `publish-daily-digest.md` is a pointer only)
- `frontend/`: static site + Vercel serverless API routes (`/api/subscribe`, `/api/confirm`, `/api/unsubscribe`)
- `data/digests/`: generated daily digest markdown files
- `.github/workflows/`: scheduled and manual automation workflows
- `docs/`: deeper operational docs and troubleshooting

## Prerequisites

- Python `3.10+` (CI uses `3.10`)
- Node.js `20+` and npm (for frontend local dev)
- Supabase project credentials
- Claude Desktop (daily scheduled task; no `ANTHROPIC_KEY`)
- Resend credentials in GitHub Actions secrets for the send-only email job

## Quickstart (End-to-End Local)

### 1) Clone and install Python dependencies

```bash
git clone <your-repo-url> ai-newsy
cd ai-newsy
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure environment

```bash
cp .env.example .env
```

Minimum vars for core pipeline:

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`

Do **not** put `ANTHROPIC_KEY` in `.env`. Claude Desktop is the model.

Resend vars stay in GitHub Actions (and Vercel for signup mail):

- `RESEND_API_KEY`
- `EMAIL_FROM`
- `APP_URL`

### 3) One-time Claude Desktop setup

Paste [`prompts/setup-claude-desktop.md`](prompts/setup-claude-desktop.md) into Claude Desktop once. That creates a daily local scheduled task from [`directives/run_daily_digest.md`](directives/run_daily_digest.md).

After setup, each morning Claude Desktop:

1. Fetches RSS (`./scripts/run_local_digest.sh --fetch`)
2. Writes analyses, intro, and headlines into `.tmp/claude-digest.json`
3. Assembles and commits (`./scripts/run_local_digest.sh --assemble --commit`)
4. Pushes `main` with today’s digest JSON **and** `frontend/issues/` (Vercel deploys the live issue first)

The scheduled **Daily AI Digest** Action at 09:00 UTC then sends email via Resend from that JSON and commits `data/digests/snapshots/*.sent.json`. Do not dispatch it from Desktop. Do not write sent snapshots locally.

After this repo change is on `main`, replace the Desktop scheduled-task Instructions with the current [`directives/run_daily_digest.md`](directives/run_daily_digest.md).

Manual stages:

```bash
./scripts/run_local_digest.sh --fetch
# write .tmp/claude-digest.json
./scripts/run_local_digest.sh --assemble --commit
git push origin main
```

Do not `gh workflow run` from Desktop. The 09:00 UTC Action sends from the pushed JSON.

## Running Scripts (Local Runbook)

### RSS health check

```bash
python3 scripts/check_feeds.py
```

### Ingest from feeds

```bash
python3 execution/fetch_ai_news.py --dry-run --limit 3
python3 execution/fetch_ai_news.py --limit 10
```

### Enrich articles

Preferred path (current prep workflow):

```bash
python3 execution/analyze_articles_single_pass.py --window-hours 48
```

Legacy/auxiliary path:

```bash
python3 execution/assign_topics.py
python3 execution/summarize_articles.py
```

### Generate digest extras

```bash
python3 execution/generate_tweet_headlines.py --dry-run
python3 execution/generate_tweet_headlines.py
python3 execution/generate_community_headlines.py --dry-run
python3 execution/generate_community_headlines.py
```

### Build and send digest

```bash
python3 execution/build_digest_markdown.py
python3 execution/send_daily_email.py --test-email you@example.com
```

### Build web archive

```bash
python3 execution/build_web_archive.py
```

### Local QA (no Anthropic API; stand-ins for the deleted test/parity Actions)

Compare the **repo** canonical JSON to `frontend/issues/`. A sent snapshot, if present, is the email source of truth.

```bash
./scripts/validate_digest_parity_local.sh
./scripts/validate_digest_parity_local.sh 2026-04-23
./scripts/validate_digest_parity_local.sh --test-email you@example.com
```

Send one test email from `.tmp/claude-digest.json` or today’s committed JSON (`--no-llm`). Does not mark `sent_at`.

```bash
./scripts/test_email_local.sh you@example.com
```

### Cleanup old articles

```bash
python3 execution/cleanup_old_articles.py --dry-run
python3 execution/cleanup_old_articles.py
```

## Frontend + Local API Development

Frontend is served through Vercel local dev with API routes in `frontend/api`.

```bash
cd frontend
npm install
npm run dev:env
```

This serves:

- `http://localhost:3000/`
- `http://localhost:3000/api/subscribe`
- `http://localhost:3000/api/confirm`
- `http://localhost:3000/api/unsubscribe`

Notes:

- Use `npm run dev:env` (not `npm run dev`) to load `../.env`.
- Restart local dev after changing `.env`.
- `SUPABASE_SECRET_KEY` is required for server routes and must stay server-side.

### Frontend/API verification checklist

1. Open `http://localhost:3000/`.
2. Submit the subscribe form with a real email.
3. Confirm you get a success or specific API error (not a generic network failure).
4. Confirm archive list loads from `/issues/index.json`.
5. Open confirmation/unsubscribe links from email to verify route behavior.

## Environment Variables

See `.env.example` for full reference. Common groups:

- Core DB: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`
- AI: Claude Desktop (no `ANTHROPIC_KEY` in `.env`)
- Email: `RESEND_API_KEY`, `EMAIL_FROM`, `APP_URL`
- Signup protections: `SUBSCRIBE_RATE_LIMIT_*`, `TURNSTILE_*` or `HCAPTCHA_*`
- Optional notifications: `SLACK_WEBHOOK_URL`
- Tweet extras: `NOTION_API_KEY`, `NOTION_TWEETS_DATABASE_ID`, `TWEET_*`
- Community extras: `COMMUNITY_*`, `REDDIT_USER_AGENT`, `YC_RSS_URL`
- Cleanup: `ARTICLE_RETENTION_DAYS`

## Development Workflow (How To Build Out Functionality)

### Pipeline/backend features

For new ingestion, scoring, or digest logic:

1. Add or update script/module in `execution/`.
2. Keep database writes centralized through existing DB helpers in `execution/database.py`.
3. Add safe dry-run or test mode when behavior changes external side effects.
4. Validate locally with a small-window run and then full runbook commands.

### Frontend/API features

For signup or web UX changes:

1. UI updates in `frontend/index.html`, `frontend/styles.css`, `frontend/script.js`.
2. API behavior in `frontend/api/*.js`.
3. Keep secrets server-side only and validate inputs defensively.
4. Test with `npm run dev:env` and real end-to-end form submission.

### Local generation, Vercel, and remaining Actions

Digest AI runs in Claude Desktop. GitHub Actions no longer generate content.

- One-time setup: [`prompts/setup-claude-desktop.md`](prompts/setup-claude-desktop.md)
- Daily Desktop task: fetch → Claude writes copy → assemble/commit/push JSON **and** `frontend/issues/`
- Vercel deploys the live issue from that push
- `daily_digest.yml`: send-only at `0 9 * * *` UTC from committed JSON (`--no-llm`), then commits sent snapshots
- `cleanup_old_articles.yml`: weekly retention cleanup

Repo secrets that can be removed from GitHub Actions: `ANTHROPIC_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, and `NOTION_*`. Keep Resend + Supabase + `APP_URL` for the send Action.

## Roadmap Guidance (Lightweight)

When adding new functionality, prioritize:

- Pipeline quality: stronger dedupe, source reliability, better summarization confidence handling
- API hardening: abuse controls, improved verification and observability
- Digest quality: more useful curation and clearer source diversity
- UX improvements: better issue browsing, confirmation states, and error messaging

### Definition of Done for new functionality

- Feature has a clear owner module/path (`execution/` or `frontend/`)
- Local runbook steps pass for the touched area
- Side effects have a safe test path (`--dry-run`, `--test-email`, or equivalent)
- Required env vars are documented in `.env.example` and this README section
- Workflow impact is considered (new/updated GitHub Action steps if needed)

## Troubleshooting and Security

- If local API changes are not reflected, restart `vercel dev`.
- If signup fails with server configuration errors, verify `SUPABASE_URL` and `SUPABASE_SECRET_KEY`.
- If digest send fails, verify `RESEND_API_KEY`, `EMAIL_FROM`, and `APP_URL`.
- Manual digest dispatches require `force_send=true`; this intentionally bypasses duplicate-send protection.
- Scheduled send fails if today's `data/digests/YYYY-MM-DD.json` is missing intro or opinions; generate locally first.
- A JSON-only push (no `frontend/issues/`) leaves the live site behind the email. `--assemble` / `--commit` now refuse that.
- If `git push origin main` is rejected, stop. The daily digest must land on `main` before 09:00 UTC; do not open a PR unless a human asks.
- If confirm/unsubscribe links open the wrong host, verify `APP_URL` matches your canonical deployed frontend origin in both Vercel env vars and GitHub Actions secrets.
- Keep `SUPABASE_SECRET_KEY` and provider API keys out of frontend/client code.
- Prefer dry-run/test modes before running production-impacting commands.

## Additional References

- `LOCAL_SETUP.md` for machine bootstrap details
- `docs/ENVIRONMENT.md` for full environment/configuration notes
- `docs/FEEDS_TROUBLESHOOTING.md` for feed-specific debugging

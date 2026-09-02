# Development environment

Local setup should match GitHub Actions so the same Python version and dependencies run everywhere.

## Quick fix: get `python3` to 3.10 now

If `python3 --version` still shows 3.9.x, run these in your terminal **in order**:

```bash
# 1. Install Python 3.10 (one-time)
brew install python@3.10

# 2. Use it in this terminal (Apple Silicon Mac)
export PATH="/opt/homebrew/opt/python@3.10/bin:$PATH"

# On Intel Mac, use this instead of the line above:
# export PATH="/usr/local/opt/python@3.10/bin:$PATH"

# 3. Confirm
python3 --version
# Should print: Python 3.10.x
```

To make the change permanent, add the `export PATH=...` line to your shell config, then reopen the terminal or run `source ~/.zshrc` (or `source ~/.bash_profile`):

```bash
echo 'export PATH="/opt/homebrew/opt/python@3.10/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

(Use `~/.bash_profile` instead of `~/.zshrc` if you use bash.)

## Python 3.10 required

This project uses **Python 3.10**. The repo is pinned via `.python-version` (for pyenv) and GitHub Actions use `3.10`.

Check your version:

```bash
python3 --version
# Should show: Python 3.10.x
```

## Install Python 3.10 (macOS with Homebrew)

### Option A: Homebrew Python

1. Install Python 3.10:

   ```bash
   brew install python@3.10
   ```

2. Use it for this project (pick one):

   **Prefer `python3` to be 3.10 everywhere (replace system/python.org):**

   ```bash
   brew link python@3.10 --force
   # Then reopen your terminal; python3 --version should be 3.10.x
   ```

   **Or use the full path for this repo only (no link):**

   ```bash
   # Add to PATH for this session, or add to your shell profile:
   export PATH="/opt/homebrew/opt/python@3.10/bin:$PATH"
   # Then:
   python3 --version  # should be 3.10.x
   ```

   On Intel Macs the path is often `/usr/local/opt/python@3.10/bin`.

### Option B: pyenv (recommended if you use multiple Python versions)

1. Install pyenv (if needed):

   ```bash
   brew install pyenv
   ```

2. Install Python 3.10 and use it in this repo:

   ```bash
   pyenv install 3.10
   cd /path/to/ai-newsy
   pyenv local 3.10
   ```

   The repo’s `.python-version` file will make `python` and `python3` resolve to 3.10 in this directory.

3. Ensure your shell runs pyenv (add to `~/.zshrc` or `~/.bash_profile` if not already there):

   ```bash
   eval "$(pyenv init -)"
   ```

## Create a virtual environment (recommended)

After Python 3.10 is active:

```bash
cd /path/to/ai-newsy
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then run scripts with the venv active:

```bash
./scripts/run_local_digest.sh
python execution/fetch_ai_news.py --limit 5
python execution/analyze_articles_single_pass.py
python execution/generate_tweet_headlines.py --dry-run
python execution/generate_community_headlines.py --dry-run
python execution/send_daily_email.py --test-email you@example.com
```

## Claude Desktop (no API key)

Daily analysis, intro, and headlines are written by Claude Desktop. Local
`.env` does **not** need `ANTHROPIC_KEY`.

Required locally:

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`

One-time setup: paste `prompts/setup-claude-desktop.md` into Claude Desktop.
The scheduled task follows `directives/run_daily_digest.md`. After that file
changes on `main`, replace the Desktop task Instructions (or recreate
`ai-newsy-daily-digest`).

Order of operations:

1. Desktop pushes `data/digests/YYYY-MM-DD.json` **and** `frontend/issues/`
2. Vercel deploys the live issue
3. 09:00 UTC Action emails from the committed JSON (`--no-llm`)
4. The same Action commits `data/digests/snapshots/*.sent.json` and `*.status.json`

Desktop never sends production email and never writes sent snapshots. Archive
HTML is built pre-send from canonical JSON. Snapshots are post-send history.

`execution/ai_client.py` remains only for optional off-Desktop API experiments.
Do not use it in the daily Desktop path.

Local QA (no Anthropic API):

```bash
./scripts/validate_digest_parity_local.sh
./scripts/test_email_local.sh you@example.com
```

### Prompt voice contract (`PROMPT_INTRO`, `PROMPT_SUMMARIZE`)

Digest writing prompts should maintain the same editorial voice:

- First-person and personal, like a coffee conversation.
- Human Element + Honesty: candid, practical, and emotionally real.
- Center on lived interpretation: what I'm learning, what I'm watching, what I'm seeing.
- Avoid detached analyst phrasing, hype language, and fake certainty.

If you override `PROMPT_INTRO` or `PROMPT_SUMMARIZE`, keep these constraints so
newsletter tone stays consistent across runs and environments.

## Tweet headline pipeline environment

For Notion tweet ingestion + headline generation, configure:

- `NOTION_API_KEY`: Notion integration token with read access to `Tweets` DB
- `NOTION_TWEETS_DATABASE_ID`: the Notion database id for `Tweets`
- `TWEET_LOOKBACK_HOURS` (optional, default `24`)
- `TWEET_FETCH_LIMIT` (optional, default `100`)
- `TWEET_MAX_HEADLINES` (optional, default `36`) — max headlines after curation; digest builder caps further
- `TWEET_HEADLINES_MODEL` (optional, default `claude-opus-5`)

Local only (not used by GitHub Actions):

- Set `NOTION_API_KEY` and `NOTION_TWEETS_DATABASE_ID` in `.env`
- Optional tweet settings can stay in `.env` as well

Database:

- Apply migration `supabase/migrations/20260414120000_add_digest_extras.sql`
- This creates `digest_extras` used to persist per-day extras (key `tweet_headlines`)

## Community headline pipeline environment

For Reddit/HN/YC ingestion + headline generation, configure:

- `COMMUNITY_LOOKBACK_HOURS` (optional, default `24`)
- `COMMUNITY_FETCH_LIMIT` (optional, default `120`)
- `COMMUNITY_MAX_HEADLINES` (optional, default `24`) — max headlines after curation; digest builder caps further
- `COMMUNITY_HEADLINES_MODEL` (optional, default `claude-opus-5`)
- `COMMUNITY_SUBREDDITS` (optional, comma-separated allowlist)
- `REDDIT_USER_AGENT` (optional but recommended)
- `YC_RSS_URL` (optional, default `https://www.ycombinator.com/blog/feed`)

Community headline generation runs in `./scripts/run_local_digest.sh` and persists to `digest_extras` key `community_headlines`.

## Digest payload configuration

Controls how the final digest is assembled from articles and headline extras.

### Article limits and source diversity

- `DIGEST_MAX_STORIES` (optional, default `16`) — max RSS articles in the digest
- `DIGEST_MAX_PER_SOURCE` (optional, default `3`) — max articles from any single RSS source; prevents one prolific feed from dominating. Articles are interleaved round-robin across sources.

### Headline limits

- `DIGEST_MAX_TWEET_HEADLINES` (optional, default `18`) — max Twitter/X headlines in the digest
- `DIGEST_MAX_COMMUNITY_HEADLINES` (optional, default `12`) — max Reddit/HN/YC headlines in the digest
- `DIGEST_MAX_HEADLINES` (optional, default `6`) — legacy fallback; prefer the specific limits above

### Generation vs digest limits

The headline generation pipelines (`TWEET_MAX_HEADLINES`, `COMMUNITY_MAX_HEADLINES`) control how many headlines are curated and stored. The digest payload builder then caps to `DIGEST_MAX_TWEET_HEADLINES` / `DIGEST_MAX_COMMUNITY_HEADLINES`. Set generation limits higher than digest limits to allow curation flexibility:

| Stage | Tweet | Community |
|-------|-------|-----------|
| Generation/curation | `TWEET_MAX_HEADLINES=36` | `COMMUNITY_MAX_HEADLINES=24` |
| Final digest | `DIGEST_MAX_TWEET_HEADLINES=18` | `DIGEST_MAX_COMMUNITY_HEADLINES=12` |

## Signup API protection environment

Subscriber endpoints (`frontend/api/subscribe.js`, `frontend/api/unsubscribe.js`) now use server-side Supabase access.

- **Required in Vercel project envs**: `APP_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `RESEND_API_KEY`, `EMAIL_FROM`
- **Optional rate limit tuning**:
  - `SUBSCRIBE_RATE_LIMIT_WINDOW_MS` (default `600000`)
  - `SUBSCRIBE_RATE_LIMIT_MAX_REQUESTS` (default `5`)
- **Optional captcha** (enable one provider; set both site and secret keys):
  - Cloudflare Turnstile: `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`
  - hCaptcha: `HCAPTCHA_SITE_KEY`, `HCAPTCHA_SECRET_KEY`

`/api/subscribe` verification behavior:
- If captcha is configured and a token is provided, the token must verify successfully.
- If captcha is configured but token is missing (for example widget load/init failure), signup continues with fail-open behavior and logs a warning.
- Without captcha secrets, the endpoint still applies honeypot and rate limiting.

Vercel configuration:

- Add required values in **Project Settings → Environment Variables** for Production/Preview as needed.
- Redeploy after changing env vars so serverless functions pick them up.
- Set `APP_URL` to the canonical deployed frontend origin (for example `https://ai-newsy.vercel.app`) so confirmation and unsubscribe links resolve correctly.

Local Vercel dev with repo `.env`:

- From `frontend/`, run `npm run dev:env`.
- This command loads `../.env` before starting `vercel dev`, so local API routes receive `SUPABASE_URL` and `SUPABASE_SECRET_KEY`.
- Restart local dev after editing `.env`.

GitHub Actions configuration:

- `daily_digest.yml` is send-only, then commits sent snapshots. It needs `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `RESEND_API_KEY`, `EMAIL_FROM`, and `APP_URL`. Use the same canonical origin as Vercel `APP_URL`.
- The send job uses `permissions: contents: write` so `github-actions[bot]` can push `data/digests/snapshots/` only. It does **not** rebuild `frontend/issues/`.
- It does **not** need `ANTHROPIC_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `NOTION_*`. Those can be removed from repository secrets in the GitHub UI.
- `cleanup_old_articles.yml` still needs `SUPABASE_URL` and `SUPABASE_SECRET_KEY`.
- No new captcha secrets are required for current scheduled jobs (they do not call `/api/subscribe`).
- If you add API integration tests in GitHub Actions later, mirror captcha and rate-limit vars in repository secrets/vars.

After a local digest run, push `frontend/issues/` on `main` **before** 09:00 UTC. Vercel deploys the static site from the `frontend/` directory. Optional CLI: `cd frontend && npx vercel --prod` if the project is already linked.

## Protected `main` (Desktop + Actions push)

Checked 2026-09-02 from this agent:

- Repository rulesets: none (`GET /repos/ajmorris/ai-newsy/rulesets` → `[]`; `GET .../rules/branches/main` → `[]`).
- Classic branch protection API returned **403** (`Resource not accessible by integration`). This token cannot read whether required reviews or status checks are configured.
- Recent `main` history shows `github-actions[bot]` already pushing digest artifacts directly (`chore: persist canonical digest payload`, `chore: publish web issue archive`). The snapshot commit should work with `contents: write` on the same pattern.
- This environment is not the Desktop machine, so Desktop credentials were not used to push a probe commit to `main`. Confirm `git push origin main` during Claude Desktop setup.

If `main` later requires a PR, the daily loop breaks. Fallback (do not change protection from an agent unless a human confirms):

- Allow the Desktop git user and `github-actions[bot]` to push `data/digests/**` and `frontend/issues/**`, or
- Add a deploy key / `GH_PUSH_TOKEN` secret with permission to push those paths.

A `workflow_dispatch` with `force_send=false` will **not** exercise the snapshot push (the guard skips). The first successful scheduled send is the live snapshot-push test.

## Confirmation and unsubscribe verification checklist

1. Submit a signup via `POST /api/subscribe` with a test email and confirm response status is `pending`.
2. Open the confirmation link from the received email and confirm it resolves to your `APP_URL` host and returns "Subscription Confirmed".
3. Verify subscriber state in Supabase `subscribers` table: `confirmed = true` for that email/token row.
4. Send a test digest (`python execution/send_daily_email.py --test-email you@example.com`) and click the unsubscribe link from the email.
5. Verify unsubscribe state in Supabase `subscribers` table: `unsubscribed_at` is set for that token row.
6. Re-open both links to confirm idempotent behavior ("Already Confirmed" / "Already Unsubscribed").

## Matching GitHub

- **CI send-only**: `.github/workflows/daily_digest.yml` uses `actions/setup-python@v5` with `python-version: '3.10'`.
- **Local generation**: Use Python 3.10 (Homebrew or pyenv) and the same `requirements.txt`. All Claude calls happen locally.

## Troubleshooting

- **`python3 --version` is still 3.9**  
  Use one of the PATH or pyenv steps above so `python3` points at 3.10.

- **`brew link python@3.10` fails**  
  Use the `export PATH=...` method or pyenv instead of linking.

- **OpenSSL / urllib3 warnings**  
  Python 3.10+ with Homebrew typically uses a newer OpenSSL; upgrading to 3.10 and using a venv usually clears those.

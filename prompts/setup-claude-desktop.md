# Prompt: one-time Claude Desktop scheduled-task setup

Open this repo as the working folder in Claude Desktop (Code tab). Paste **everything below the line** once. After setup, do not paste a daily publish prompt — the scheduled task runs it.

If `ai-newsy-daily-digest` already exists, delete it or replace its Instructions with the full current `directives/run_daily_digest.md`. Pasting this setup again is not enough if the old task still has yesterday’s text.

Create **one** local scheduled task only. Do not create a second task that sends email.

---

This repo is AI Newsy. Do a **single setup** of Claude Desktop scheduled tasks on this machine, then stop. Do not invent extra workflows.

You (Claude Desktop) are the model. There is **no `ANTHROPIC_KEY`** in `.env`. GitHub Actions only send email via Resend at 09:00 UTC, then commit sent snapshots.

## Order of operations every morning (do not change this)

1. Desktop assembles and pushes today’s `data/digests/YYYY-MM-DD.json` **and** `frontend/issues/`
2. Vercel deploys the site from `frontend/`
3. The 09:00 UTC **Daily AI Digest** Action emails subscribers from that JSON (`--no-llm`)
4. The same Action commits `data/digests/snapshots/*.sent.json` and `*.status.json` back to `main`

Desktop never sends production email, never runs `--send`, never runs `gh workflow run`, and never writes sent snapshots.

## Setup steps

1. Read `directives/setup_claude_desktop.md` and `directives/run_daily_digest.md`.
2. Confirm `.env` has `SUPABASE_URL` and `SUPABASE_SECRET_KEY` only for local work. If `ANTHROPIC_KEY` is present, tell me I can delete it. Do not require it.
3. Confirm GitHub Actions secrets still have `RESEND_API_KEY`, `EMAIL_FROM`, `APP_URL`, and Supabase keys for `.github/workflows/daily_digest.yml`. That workflow already runs daily at 09:00 UTC. Do **not** dispatch it during setup unless I ask.
4. Confirm Python venv + `pip install -r requirements.txt` work from repo root. Confirm `./scripts/run_local_digest.sh --help` runs.
5. Confirm `git push origin main` works from this machine (a no-op or already-up-to-date push is enough). If the push is rejected (protected branch / required PR), stop and report the error. The daily loop cannot use a pull request unless I change branch protection.
6. Create **exactly one** Claude Desktop **local** scheduled task (Routines / Schedule / recurring task — use whatever the UI calls a local recurring job on this computer):

   - **Name:** `ai-newsy-daily-digest`
   - **Schedule:** Daily, at a local time that finishes **before 09:00 UTC** so Vercel has the new issue **live** before the send Action (not only the JSON on `main`)
   - **Working folder:** this repo root. Do not use an isolated worktree.
   - **Permission mode:** bypass / always-allow after one `Run now` so later runs are unattended
   - **Model:** Opus (Desktop’s own model — not an API key)
   - **Instructions:** the **full verbatim text** of `directives/run_daily_digest.md` (the daily job). Do not summarize it. Do not point at the file path instead of pasting the text.

7. Click **Run now** once. Approve tools (`Bash`, `git`, etc.) with **always allow**. Keep Claude Desktop open and the machine awake (`Keep computer awake` in Desktop settings if available).
8. Do **not** create any other scheduled tasks (no send task, no cleanup task, no snapshot task). Leave `.github/workflows/cleanup_old_articles.yml` on GitHub.

## Report back

- Task name and scheduled local time vs 09:00 UTC
- Whether `.env` is key-free
- Whether `git push origin main` worked
- Confirmation that email stays on the GitHub Action
- Confirmation that only one Desktop task exists

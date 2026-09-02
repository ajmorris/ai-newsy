# Prompt: one-time Claude Desktop setup

Paste this **once** into Claude Desktop (Code tab) with this repo as the working folder. After setup, do not paste a daily publish prompt — the scheduled task runs it.

After this repo change is on `main`, **edit the existing Desktop task** and replace its Instructions with the full new `directives/run_daily_digest.md` (or delete and recreate `ai-newsy-daily-digest`). Pasting setup again is not enough if the scheduled task still has yesterday’s text.

---

Read `directives/setup_claude_desktop.md` and do a **single setup** of AI Newsy on this machine.

Goal: Claude Desktop becomes the daily runner. There is **no `ANTHROPIC_KEY`** in `.env`. You (Claude Desktop) are the model. GitHub Actions only send email via Resend, then commit sent snapshots.

Order of operations every morning:

1. Desktop assembles and pushes today’s digest JSON **and** `frontend/issues/`
2. Vercel deploys the site from `frontend/`
3. The 09:00 UTC Daily AI Digest Action emails subscribers from that JSON
4. The Action commits `data/digests/snapshots/*.sent.json` (and `*.status.json`) back to `main`

Desktop never sends production email and never writes sent snapshots.

Do this setup, then stop. Do not invent extra workflows.

1. Confirm `.env` has `SUPABASE_URL` and `SUPABASE_SECRET_KEY` only for local work. If `ANTHROPIC_KEY` is present, tell me I can delete it. Do not require it.
2. Confirm GitHub Actions secrets still have `RESEND_API_KEY`, `EMAIL_FROM`, `APP_URL`, and Supabase keys for `.github/workflows/daily_digest.yml`. That workflow already runs daily at 09:00 UTC and sends from committed JSON (`--no-llm`). Do **not** create a second send path and do **not** dispatch it during setup unless I ask.
3. Confirm Python venv + `pip install -r requirements.txt` work from repo root.
4. Confirm `git push origin main` works from this machine (a no-op or harmless docs-only probe is enough). If the push is rejected (protected branch / required PR), stop and report the error. The daily loop cannot use a pull request unless a human changes branch protection.
5. Create **one** Claude Desktop local scheduled task:

   - Name: `ai-newsy-daily-digest`
   - Schedule: **Daily**, at a local time that finishes **before 09:00 UTC** so Vercel has the new issue live before the send Action (not only the JSON on `main`).
   - Working folder: this repo root. Do not use an isolated worktree.
   - Permission mode: bypass / always-allow after one `Run now` so later runs are unattended.
   - Model: Opus (Desktop’s own model — not an API key).
   - Instructions: the full text of `directives/run_daily_digest.md` (the daily job).

6. Click **Run now** once, approve tools (`Bash`, `git`, etc.) with always allow, and keep Claude Desktop open + the machine awake for scheduled runs (`Keep computer awake` in Desktop settings if available).
7. Report: scheduled time vs 09:00 UTC, task name, whether `.env` is key-free, whether `git push origin main` worked, and that email stays on the GitHub Action.

If Desktop UI labels differ (Routines vs Schedule), use whatever creates a **local** recurring task on this computer.

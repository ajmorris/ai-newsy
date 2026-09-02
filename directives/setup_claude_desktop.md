# One-time Claude Desktop setup

## Purpose

Set up AI Newsy so Claude Desktop runs the daily digest on a schedule. You are the model. `.env` does not need `ANTHROPIC_KEY`. After this setup, the only remaining GitHub Action that must keep running is **Daily AI Digest** (Resend send at 09:00 UTC, then a snapshot commit).

This directive is **setup only**. The recurring job lives in [`run_daily_digest.md`](run_daily_digest.md).

After this repo change lands on `main`, edit the existing Desktop task and replace its Instructions with the full new [`run_daily_digest.md`](run_daily_digest.md) (or delete and recreate `ai-newsy-daily-digest`). Pasting setup again is not enough if the scheduled task still has yesterday’s text.

## What runs where

| Work | Who |
|---|---|
| Fetch RSS, export pending items | Local scripts (`--fetch`) |
| Topic, summary, opinion, intro, headline copy | Claude Desktop (you) |
| Persist Claude JSON, build archive, commit, push `main` | Local scripts + git (JSON **and** `frontend/issues/`) |
| Deploy live issue pages | Vercel, from the Desktop push |
| Email subscribers via Resend | Scheduled Action `daily_digest.yml` at 09:00 UTC |
| Persist `*.sent.json` / `*.status.json` | Same send Action, after Resend (Desktop never writes these) |
| Weekly article cleanup | `cleanup_old_articles.yml` (leave it) |

Deleted Actions (RSS prep, tweet prep, community prep, archive publish, test/parity) stay gone.

## Local `.env` (no Anthropic key)

Required:

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`

Optional for tweet extras: `NOTION_API_KEY`, `NOTION_TWEETS_DATABASE_ID`.

Do **not** put `ANTHROPIC_KEY`, `GEMINI_API_KEY`, or `OPENAI_API_KEY` in `.env`. Claude Desktop provides the model.

Resend keys stay in **GitHub Actions secrets** (and Vercel for signup mail), not in the Desktop task.

## Scheduled task to create

In Claude Desktop → Code → Routines / Schedule → New **local** task:

- Name: `ai-newsy-daily-digest`
- Daily, early enough that Vercel has the new issue **live** before **09:00 UTC** (not only JSON on `main`)
- Working folder: repo root
- Instructions: copy [`run_daily_digest.md`](run_daily_digest.md)
- After create: **Run now** and always-allow tools so unattended runs do not stall
- Keep the Desktop app open and the machine awake

Do not schedule a second task that sends email. The Action already does that. Desktop never writes sent snapshots.

## Verify once

```bash
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); assert os.getenv('SUPABASE_URL'); assert os.getenv('SUPABASE_SECRET_KEY'); print('supabase ok')"
./scripts/run_local_digest.sh --help
git push origin main
```

Confirm `git push origin main` works from this machine during setup, not on the first production morning. If the push is rejected (protected branch / required PR), stop and report it.

Do not require a successful full assemble during setup unless pending Claude JSON already exists.

## Related

- Paste-ready setup prompt: [`prompts/setup-claude-desktop.md`](../prompts/setup-claude-desktop.md)
- Daily job: [`run_daily_digest.md`](run_daily_digest.md)

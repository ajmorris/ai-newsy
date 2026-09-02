# Publish Daily Digest (local Claude → GitHub → Resend)

## Purpose

The scheduled GitHub Actions that used to fetch RSS, call Gemini/OpenAI/Claude, write headlines, and publish the archive no longer run. You replace those jobs locally with Claude Opus 5, push the artifacts, then fire the one remaining Action so Resend emails subscribers.

You are Layer 2 (orchestrator). Do not write summaries, intros, or headlines yourself. Call the scripts.

## What moved off GitHub Actions

| Old Action | What it did | What you run now |
|---|---|---|
| `prepare_digest_content.yml` | Fetch RSS, single-pass analysis, extras, commit JSON | `./scripts/run_local_digest.sh` |
| `prepare_twitter_headlines.yml` | Notion tweets → LLM headlines | included in the local script |
| `prepare_community_headlines.yml` | Reddit/HN/YC → LLM headlines | included in the local script |
| `publish_web_archive.yml` | Build `frontend/issues/` and commit | included in the local script; Vercel deploys on push |
| `daily_digest.yml` | Build + send email | **keep this Action only** — send-only via Resend, no LLM |
| `cleanup_old_articles.yml` | Weekly DB retention | leave on its Sunday schedule; do not run daily |

## Inputs

Required in `.env`:

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `ANTHROPIC_KEY` (Claude Opus 5)

Required in **GitHub Actions secrets** for the send workflow (not needed locally if you are not sending from this machine):

- `RESEND_API_KEY`
- `EMAIL_FROM`
- `APP_URL`
- `SUPABASE_URL` / `SUPABASE_SECRET_KEY`

Optional locally for tweet extras: `NOTION_API_KEY`, `NOTION_TWEETS_DATABASE_ID`.

Also need `gh` authenticated (`gh auth status`) so you can dispatch the workflow.

## Execution

### 1) Generate locally (replaces the deleted Actions)

From repo root, on a clean `main` checkout unless the operator asked for a branch:

```bash
./scripts/run_local_digest.sh --commit
```

Equivalent individual steps, in this order:

1. `python3 execution/fetch_ai_news.py --limit 10`
2. `python3 execution/analyze_articles_single_pass.py`
3. `python3 execution/generate_tweet_headlines.py`
4. `python3 execution/generate_community_headlines.py`
5. `python3 execution/digest_payload.py`
6. `python3 execution/build_digest_markdown.py`
7. `python3 execution/build_web_archive.py --use-canonical-fallback`

`--commit` stages `data/digests/*.json` and `frontend/issues` only. It does not push and it does not send email.

All LLM calls go through `execution/ai_client.py` to `claude-opus-5`. There is no Gemini or OpenAI fallback.

### 2) Validate before push

Today means **UTC date**. Confirm `data/digests/YYYY-MM-DD.json` exists and has:

- a non-empty `intro`
- every story has a non-empty `opinion`

If either check fails, stop. Do not push. Do not dispatch the send workflow.

### 3) Submit to GitHub (Vercel)

```bash
git push origin HEAD
```

If you generated on `main`, that push is the production site: Vercel deploys `frontend/` (archive HTML + `issues/index.json`). If you are on a feature branch, say so and do not treat it as the production send path unless the operator asked to dispatch against that ref.

### 4) Send email through Resend (the one remaining Action)

Do **not** run `./scripts/run_local_digest.sh --send` or `python3 execution/send_daily_email.py` for production. Production send is the GitHub Action so Resend keys stay in repo secrets.

Manual dispatch **must** set `force_send=true` or the workflow guard skips the send.

```bash
gh workflow run "Daily AI Digest" --ref main \
  -f force_send=true \
  -f send_reason="Published from local Claude pipeline"

gh run list --workflow="Daily AI Digest" --limit 1
gh run watch --workflow="Daily AI Digest"
```

That job:

- checks out the ref you passed
- requires today's UTC `data/digests/YYYY-MM-DD.json` on that ref
- fails if intro or opinions are missing
- runs `python execution/send_daily_email.py --no-llm` and sends via Resend

Wait until the run finishes. If it fails, read the log (`gh run view --log-failed`) and fix; do not invent a second send path unless the operator asks.

## Output to report

- UTC digest date and path to the JSON
- Story count and whether intro/opinions passed
- Commit SHA and remote branch
- Reminder that Vercel will pick up `frontend/` from `main`
- Actions run URL and success/failure for Daily AI Digest

## Edge cases

- Missing `ANTHROPIC_KEY`: stop and ask the operator to set it.
- Tweet extras fail without Notion secrets: report it; continue if RSS + community still produce a valid digest.
- `gh` not authenticated: stop before claiming the email went out.
- Push rejected / today's JSON not on the remote: do not dispatch the send workflow.
- Already-sent digest: `force_send=true` is an intentional resend; include that in `send_reason`.
- Do not call GitHub Actions to generate content. Generation is local only.
- Leave `cleanup_old_articles.yml` alone.

## Related

- Copy-paste prompt: [`prompts/publish-daily-digest.md`](../prompts/publish-daily-digest.md)
- Generate-only (no push / no send): [`directives/run_daily_digest.md`](run_daily_digest.md)

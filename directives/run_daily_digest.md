# Daily digest (Claude Desktop scheduled task)

## Purpose

Build today’s digest on this machine. You are the model — write the summaries, opinions, intro, and headlines yourself. Deterministic scripts fetch, persist, and publish files. Do not call the Anthropic API and do not read `ANTHROPIC_KEY`.

You are Layer 2. Use the scripts. Do not scrape sites by hand when a script exists.

## Inputs

- `.env` with `SUPABASE_URL` and `SUPABASE_SECRET_KEY` only
- Optional Notion vars for tweet extras
- Working directory: repo root, branch `main`

## Execution

1. `git checkout main` and `git pull origin main`. This picks up yesterday’s sent snapshots from the Daily AI Digest Action. Do not write or invent `data/digests/snapshots/*.sent.json`.
2. Fetch sources and export what you must write:

   ```bash
   ./scripts/run_local_digest.sh --fetch
   ```

   Read `.tmp/pending-digest.json`.
3. Write `.tmp/claude-digest.json` yourself. Follow the voice in that file (first person, coffee conversation, no guru certainty).

   ```json
   {
     "digest_date": "UTC-TODAY",
     "intro": "2-3 sentences",
     "analyses": [
       {"id": 123, "topic": "Models", "summary": "...", "opinion": "...", "confidence": 0.8}
     ],
     "tweet_headlines": [{"headline": "...", "url": "..."}],
     "community_headlines": [{"headline": "...", "url": "..."}]
   }
   ```

   Every analysis needs a non-empty `summary` and `opinion`. Topic must be one of the `allowed_topics` on each article. Intro is required.
4. Assemble, then check the site files before commit:

   ```bash
   ./scripts/run_local_digest.sh --assemble
   ```

   Confirm all of the following. If any fail, fix `.tmp/claude-digest.json` and `--assemble` again. Do not push.

   - `data/digests/YYYY-MM-DD.json` has a non-empty `intro` and every story a non-empty `opinion`
   - `frontend/issues/index.json` `latestIssue.digestDate` is UTC today
   - today’s `frontend/issues/<slug>.html` exists
5. Commit and push so Vercel deploys **before** the 09:00 UTC send Action:

   ```bash
   ./scripts/run_local_digest.sh --assemble --commit
   git push origin main
   ```

   The commit must include `data/digests/YYYY-MM-DD.json` **and** `frontend/issues/` (HTML + `index.json`). A JSON-only push is a hard failure — the live site would lag the email.
6. Do not send email. Do not run `--send`. Do not `gh workflow run`. Do not write or invent `data/digests/snapshots/*.sent.json`. Snapshots are written by the Daily AI Digest Action after Resend and committed back to `main`. The next morning’s `git pull` will pick them up.

Optional QA (never required for a green daily run):

```bash
./scripts/validate_digest_parity_local.sh
./scripts/test_email_local.sh you@example.com
```

If `git push origin main` is rejected (protected branch), stop and report the error. Do not open a PR for the daily digest unless a human asks.

## Validate before push

UTC date. `data/digests/YYYY-MM-DD.json` must have a non-empty `intro` and every story a non-empty `opinion`. If not, stop and fix `.tmp/claude-digest.json`, then `--assemble` again.

## Output to leave in the session

- UTC digest date, story count
- Commit SHA
- Confirmation that `frontend/issues/` was pushed so Vercel can deploy before email
- Confirmation that email is left to the 09:00 UTC Action

## Edge cases

- Missing Supabase env: stop.
- Tweet export fails without Notion: continue with RSS + community.
- Assemble fails: do not push a partial digest.
- Leave `cleanup_old_articles.yml` alone.
- If the send Action already ran today and you are late, still push the archive; do not force-send unless a human asks.

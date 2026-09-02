# Daily digest (Claude Desktop scheduled task)

## Purpose

Build today’s digest on this machine. You are the model — write the summaries, opinions, intro, and headlines yourself. Deterministic scripts fetch, persist, and publish files. Do not call the Anthropic API and do not read `ANTHROPIC_KEY`.

You are Layer 2. Use the scripts. Do not scrape sites by hand when a script exists.

## Inputs

- `.env` with `SUPABASE_URL` and `SUPABASE_SECRET_KEY` only
- Optional Notion vars for tweet extras
- Working directory: repo root, branch `main`

## Execution

1. `git checkout main` and `git pull origin main`.
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
4. Assemble, commit, and push (this is what used to be the prep/archive Actions):

   ```bash
   ./scripts/run_local_digest.sh --assemble --commit
   git push origin main
   ```

   Vercel deploys `frontend/` from `main`.
5. **Do not send email.** Do not run `--send`. Do not `gh workflow run`. The scheduled **Daily AI Digest** Action at 09:00 UTC sends via Resend from the JSON you just pushed. It fails if intro or opinions are missing.

## Validate before push

UTC date. `data/digests/YYYY-MM-DD.json` must have a non-empty `intro` and every story a non-empty `opinion`. If not, stop and fix `.tmp/claude-digest.json`, then `--assemble` again.

## Output to leave in the session

- UTC digest date, story count
- Commit SHA
- Confirmation that email is left to the 09:00 UTC Action

## Edge cases

- Missing Supabase env: stop.
- Tweet export fails without Notion: continue with RSS + community.
- Assemble fails: do not push a partial digest.
- Leave `cleanup_old_articles.yml` alone.
- If the send Action already ran today and you are late, still push the archive; do not force-send unless a human asks.

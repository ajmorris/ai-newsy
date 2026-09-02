# Prompt: publish today's digest

Paste this into Claude Code / Cursor when you want today's newsletter built, pushed, and emailed.

---

Read `directives/publish_daily_digest.md` and run today's AI Newsy publish. You are the orchestrator only. Do not write summaries, intros, or headlines yourself.

1. Confirm `.env` has `ANTHROPIC_KEY`, `SUPABASE_URL`, and `SUPABASE_SECRET_KEY`. Stop if any are missing.
2. From repo root, on `main` (or create a dated branch only if I ask), run the old GitHub Action work locally:

   ```bash
   ./scripts/run_local_digest.sh --commit
   ```

   That replaces prepare-RSS, tweet headlines, community headlines, digest JSON, and web-archive publish. All LLM calls must go through Claude Opus 5 in `execution/ai_client.py`.
3. Review `data/digests/YYYY-MM-DD.json` (UTC today). Abort if intro is empty or any story is missing `opinion`.
4. Push the commit to GitHub (`git push origin HEAD`). Vercel deploys `frontend/` from `main`.
5. After the push is on the remote, trigger the one remaining Action so Resend sends the newsletter. Do **not** send email from this machine (`--send` / `send_daily_email.py` without `--no-llm`).

   ```bash
   gh workflow run "Daily AI Digest" --ref main \
     -f force_send=true \
     -f send_reason="Published from local Claude pipeline"
   gh run watch --workflow="Daily AI Digest"
   ```

   Manual dispatch requires `force_send=true` or the workflow skips the send. It emails from the committed JSON only (`--no-llm`).
6. Report: digest date, story count, commit SHA, Vercel note, and the Actions run URL / result.

Stop on the first hard failure (missing key, empty digest, push rejected, or send workflow failed). Tweet extras may fail without Notion secrets; continue with RSS + community if the canonical JSON still has a valid intro and opinions.

# Run Daily Digest Locally

## Purpose

Build today's AI Newsy digest on this machine using Claude Opus 5, then commit the generated artifacts so Vercel can publish the web archive.

You are the orchestrator. Do not write summaries yourself. Call the execution scripts in order.

## Inputs

- `.env` with `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, and `ANTHROPIC_KEY`
- Optional: `RESEND_API_KEY`, `EMAIL_FROM`, `APP_URL` if sending email
- Optional: `NOTION_API_KEY` and `NOTION_TWEETS_DATABASE_ID` for tweet extras

## Execution

Preferred: one command from repo root.

```bash
./scripts/run_local_digest.sh
```

Options:

- `--test-email you@example.com` — send a one-recipient test (does not mark articles sent)
- `--send` — production subscriber send
- `--commit` — commit `data/digests/*.json` and `frontend/issues` locally (does not push)

Equivalent individual steps, in this order:

1. `python3 execution/fetch_ai_news.py --limit 10`
2. `python3 execution/analyze_articles_single_pass.py`
3. `python3 execution/generate_tweet_headlines.py`
4. `python3 execution/generate_community_headlines.py`
5. `python3 execution/digest_payload.py`
6. `python3 execution/build_digest_markdown.py`
7. `python3 execution/build_web_archive.py --use-canonical-fallback`
8. Optional: `python3 execution/send_daily_email.py --test-email you@example.com`

All LLM calls go through `execution/ai_client.py` to Claude Opus 5 (`claude-opus-5`). There is no Gemini or OpenAI fallback.

## Output

- Canonical JSON: `data/digests/YYYY-MM-DD.json`
- Markdown: `data/digests/YYYY-MM-DD.md`
- Web archive: `frontend/issues/*.html` and `frontend/issues/index.json`

## After a successful run

1. Review the generated digest JSON and archive HTML.
2. Commit with `--commit` or a manual commit of those paths.
3. Push `main`. Vercel deploys `frontend/`.
4. Scheduled `daily_digest.yml` sends from the committed JSON (`--no-llm`) when it is complete. If today's JSON is missing, GitHub Actions generates it with Claude Opus 5 and still sends.
5. Keep `ANTHROPIC_KEY` in GitHub Actions secrets so that fallback generation can run.

## Edge cases

- Missing `ANTHROPIC_KEY`: stop and ask the operator to set it.
- Tweet extras fail without Notion secrets: report the error; community + RSS digest can still proceed if you rerun remaining steps.
- Do not push without the operator reviewing generated content.

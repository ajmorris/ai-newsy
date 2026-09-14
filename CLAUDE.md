# AI Newsy

AI-news ingestion and daily digest: RSS ingest, LLM enrichment, social/community extras, email send, and a static web archive.

## Stack

- Python 3.10 pipeline in `execution/` (CI uses `3.10`)
- Node 20 frontend + Vercel API routes in `frontend/`
- GitHub Actions in `.github/workflows/`
- Supabase for article/subscriber storage; Resend for email

Env vars live in `.env.example` and `docs/ENVIRONMENT.md`. Never commit secrets.

## Conventions

- Keep database writes in `execution/database.py`.
- Prefer `--dry-run` and `--test-email` for side-effecting scripts.
- Document new env vars in `.env.example`.
- If a change affects scheduled jobs, match the existing workflow env (do not add API keys or OAuth tokens to files).

Digest LLM calls go through `execution/ai_client.py`. GitHub Actions digest jobs use the Claude CLI (`LLM_PROVIDER_CHAIN=claude_code`) with `CLAUDE_CODE_OAUTH_TOKEN`. Local runs can still use Anthropic / Gemini / OpenAI HTTP APIs. `@claude` comments use `.github/workflows/claude.yml`, which is separate from digest generation.

## Tests

```bash
python -m unittest discover -s execution -p 'test_*.py'
```

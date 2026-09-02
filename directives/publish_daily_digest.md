# Publish Daily Digest

Superseded by the Claude Desktop one-time setup.

- Setup (paste once): [`prompts/setup-claude-desktop.md`](../prompts/setup-claude-desktop.md) and [`setup_claude_desktop.md`](setup_claude_desktop.md)
- Daily scheduled job: [`run_daily_digest.md`](run_daily_digest.md)

Claude Desktop writes the digest and pushes `main`. The remaining Action, **Daily AI Digest**, sends email via Resend at 09:00 UTC. There is no `ANTHROPIC_KEY` in `.env`.

# Prompt: publish today's digest

Do not use this as a daily paste. Setup is one-time.

Use [`setup-claude-desktop.md`](setup-claude-desktop.md) once. After that, Claude Desktop’s scheduled task follows [`directives/run_daily_digest.md`](../directives/run_daily_digest.md): fetch → you write the copy → assemble/commit/push `data/digests/YYYY-MM-DD.json` **and** `frontend/issues/` so Vercel deploys first. The **Daily AI Digest** Action emails via Resend at 09:00 UTC and commits sent snapshots; Desktop never writes `*.sent.json`.

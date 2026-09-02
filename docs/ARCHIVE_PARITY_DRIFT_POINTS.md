# Archive Parity Drift Points

This document captures the code paths that previously allowed `0 stories` regressions in web archive output.

## Root cause

Rebuild flows used mutable DB state (`unsent` selection) instead of immutable payloads.

## Drift paths

1. `execution/digest_payload.py`
- Default build path uses `get_unsent_articles(...)`.
- Re-running this after send can produce different article sets (including empty sets).
- Daily Desktop assemble uses `--no-llm` and must not call the API.

2. `execution/send_daily_email.py`
- `write_sent_snapshot` is the immutable “what was emailed” record. It only exists **after** Resend.
- The send Action commits `data/digests/snapshots/*.sent.json` and `*.status.json` to `main`. Desktop must not invent these files.

3. `execution/build_web_archive.py`
- Prefers canonical `data/digests/YYYY-MM-DD.json`.
- Uses `*.sent.json` only for dates that lack canonical JSON.
- Publishing the archive from canonical JSON on Desktop (pre-send) is the correct Vercel path.

4. Local archive publish (`./scripts/run_local_digest.sh` → `execution/build_web_archive.py`)
- `--assemble` / `--commit` now fail unless today’s UTC `frontend/issues/<slug>.html` exists and `index.json` `latestIssue.digestDate` is UTC today.
- A JSON-only push would leave the live site behind the 09:00 UTC email.

## Guardrail now expected

- **Pre-send / Vercel:** archive HTML is built from canonical `data/digests/YYYY-MM-DD.json` on Desktop, then pushed with `frontend/issues/` before 09:00 UTC.
- **Post-send history:** the send Action writes and commits `data/digests/snapshots/YYYY-MM-DD.sent.json`. Snapshots are not used to rebuild live pages on send.
- **Parity:** `./scripts/validate_digest_parity_local.sh` compares repo canonical JSON to `frontend/issues/`. If a sent snapshot exists, `execution/validate_digest_parity.py` prefers it as the email source of truth.
- Snapshot hash and manifest hash/count/subject must match in parity validation when a snapshot is present.

## Local QA

```bash
./scripts/validate_digest_parity_local.sh
./scripts/test_email_local.sh you@example.com
```

Neither script calls the Anthropic API. Test email does not mark `sent_at`.

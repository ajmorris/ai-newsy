# Archive Parity Drift Points

This document captures the code paths that previously allowed `0 stories` regressions in web archive output.

## Root cause

Rebuild flows used mutable DB state (`unsent` selection) instead of immutable sent payload snapshots.

## Drift paths

1. `execution/digest_payload.py`
- Default build path uses `get_unsent_articles(...)`.
- Re-running this after send can produce different article sets (including empty sets).

2. `execution/send_daily_email.py`
- If no immutable snapshot is preserved, later rebuilds are free to regenerate date payload from current DB state.

3. `execution/build_web_archive.py`
- If web build consumes mutable payload files, stale/overwritten date payloads can publish incorrect story counts.

4. Local archive publish (`./scripts/run_local_digest.sh` → `execution/build_web_archive.py`)
- If the archive is built from generic digest files rather than sent snapshots, it may drift from what was emailed.

## Guardrail now expected

- Archive must be built from `data/digests/snapshots/YYYY-MM-DD.sent.json`.
- Snapshot hash and manifest hash/count/subject must match in parity validation.

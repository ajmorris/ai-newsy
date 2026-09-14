#!/usr/bin/env bash
# Local digest stages for Claude Desktop (no Anthropic API key required).
#
#   ./scripts/run_local_digest.sh --fetch      # RSS + export pending inputs
#   # Claude writes .tmp/claude-digest.json
#   ./scripts/run_local_digest.sh --assemble   # apply Claude JSON + archive
#   ./scripts/run_local_digest.sh --commit     # commit artifacts (does not push)
#
# Running with no stage flags does fetch + assemble.

set -euo pipefail

cd "$(dirname "$0")/.."

usage() {
  cat <<'EOF'
Usage: ./scripts/run_local_digest.sh [options]

  --fetch              Fetch RSS and export .tmp/pending-digest.json
  --assemble           Apply .tmp/claude-digest.json, build JSON/markdown/archive
  --commit             Commit data/digests/*.json and frontend/issues (does not push)
  --test-email EMAIL   After assemble, send a single-recipient test (no sent_at)
  --send               After assemble, send production email from this machine
  -h, --help           Show this help

Claude Desktop is the model. .env needs SUPABASE_URL and SUPABASE_SECRET_KEY only.
Do not set ANTHROPIC_KEY. Production email is the scheduled Daily AI Digest Action.
EOF
}

FETCH=0
ASSEMBLE=0
COMMIT=0
TEST_EMAIL=""
SEND=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fetch) FETCH=1; shift ;;
    --assemble) ASSEMBLE=1; shift ;;
    --commit) COMMIT=1; shift ;;
    --test-email)
      TEST_EMAIL="${2:-}"
      if [[ -z "${TEST_EMAIL}" ]]; then
        echo "--test-email requires an address."
        exit 1
      fi
      shift 2
      ;;
    --send) SEND=1; shift ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "${SEND}" -eq 1 && -n "${TEST_EMAIL}" ]]; then
  echo "Use either --send or --test-email, not both."
  exit 1
fi

if [[ "${FETCH}" -eq 0 && "${ASSEMBLE}" -eq 0 && "${COMMIT}" -eq 0 ]]; then
  FETCH=1
  ASSEMBLE=1
fi

if [[ ! -f ".env" ]]; then
  echo "Missing .env file. Copy .env.example and set SUPABASE_URL and SUPABASE_SECRET_KEY."
  exit 1
fi

if ! python3 - <<'PY'
import os
from dotenv import load_dotenv
load_dotenv(".env")
url = (os.getenv("SUPABASE_URL") or "").strip()
key = (os.getenv("SUPABASE_SECRET_KEY") or "").strip()
if not url or url.startswith("https://your-project") or not key or key == "your-secret-key":
    raise SystemExit(1)
PY
then
  echo "SUPABASE_URL or SUPABASE_SECRET_KEY is missing or still a placeholder. Set them in .env."
  exit 1
fi

if [[ "${FETCH}" -eq 1 ]]; then
  echo "=== Fetch RSS ==="
  python3 execution/fetch_ai_news.py --limit 10
  echo "=== Export pending inputs for Claude Desktop ==="
  python3 execution/export_pending_digest.py
fi

if [[ "${ASSEMBLE}" -eq 1 ]]; then
  if [[ ! -f ".tmp/claude-digest.json" ]]; then
    echo "Missing .tmp/claude-digest.json. Claude Desktop must write analyses, intro, and headlines first."
    echo "See directives/run_daily_digest.md"
    exit 1
  fi
  echo "=== Apply Claude Desktop digest ==="
  python3 execution/apply_claude_digest.py
  echo "=== Canonical digest payload (no API) ==="
  python3 execution/digest_payload.py --no-llm
  echo "=== Digest markdown ==="
  python3 execution/build_digest_markdown.py
  echo "=== Web archive ==="
  python3 execution/build_web_archive.py --use-canonical-fallback
  echo "=== Confirm today's archive is ready for Vercel ==="
  python3 execution/assert_today_archive.py
fi

if [[ -n "${TEST_EMAIL}" ]]; then
  echo "=== Test email to ${TEST_EMAIL} ==="
  python3 execution/send_daily_email.py --no-llm --test-email "${TEST_EMAIL}"
elif [[ "${SEND}" -eq 1 ]]; then
  echo "=== Production email send ==="
  python3 execution/send_daily_email.py --no-llm
fi

if [[ "${COMMIT}" -eq 1 ]]; then
  echo "=== Confirm today's archive is ready for Vercel ==="
  python3 execution/assert_today_archive.py
  echo "=== Commit generated artifacts ==="
  # Snapshots are written after Resend by the send Action. Do not add them here.
  git add data/digests/*.json frontend/issues
  python3 execution/assert_today_archive.py --require-staged
  if git diff --staged --quiet; then
    echo "No digest or archive changes to commit."
  else
    git commit -m "chore: persist local Claude digest and web archive"
    echo "Committed locally. git push origin main so Vercel deploys frontend/issues before the 09:00 UTC send."
  fi
fi

echo "Done."

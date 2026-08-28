#!/usr/bin/env bash
# Local Claude Opus 5 digest pipeline:
# fetch → analyze → extras → canonical JSON → web archive → optional email/commit.
#
# Usage:
#   ./scripts/run_local_digest.sh
#   ./scripts/run_local_digest.sh --test-email you@example.com
#   ./scripts/run_local_digest.sh --send
#   ./scripts/run_local_digest.sh --commit
#
# --commit stages generated artifacts and creates a local commit. It does not push.

set -euo pipefail

cd "$(dirname "$0")/.."

usage() {
  cat <<'EOF'
Usage: ./scripts/run_local_digest.sh [options]

  --test-email EMAIL   Send a single-recipient test digest (does not mark articles sent)
  --send               Send the production digest to subscribers
  --commit             Commit data/digests/*.json and frontend/issues (does not push)
  -h, --help           Show this help

Requires ANTHROPIC_KEY in .env. All LLM calls use Claude Opus 5.
EOF
}

TEST_EMAIL=""
SEND=0
COMMIT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --test-email)
      TEST_EMAIL="${2:-}"
      if [[ -z "${TEST_EMAIL}" ]]; then
        echo "--test-email requires an address."
        exit 1
      fi
      shift 2
      ;;
    --send)
      SEND=1
      shift
      ;;
    --commit)
      COMMIT=1
      shift
      ;;
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

if [[ ! -f ".env" ]]; then
  echo "Missing .env file. Copy .env.example and set ANTHROPIC_KEY."
  exit 1
fi

if ! python3 - <<'PY'
import os
from dotenv import load_dotenv
load_dotenv()
key = (os.getenv("ANTHROPIC_KEY") or "").strip()
if not key or key == "your-anthropic-api-key":
    raise SystemExit(1)
PY
then
  echo "ANTHROPIC_KEY is missing or still a placeholder. Set it in .env."
  exit 1
fi

echo "=== Fetch RSS ==="
python3 execution/fetch_ai_news.py --limit 10

echo "=== Single-pass analysis (Claude Opus 5) ==="
python3 execution/analyze_articles_single_pass.py

echo "=== Tweet headlines ==="
python3 execution/generate_tweet_headlines.py

echo "=== Community headlines ==="
python3 execution/generate_community_headlines.py

echo "=== Canonical digest payload ==="
python3 execution/digest_payload.py

echo "=== Digest markdown ==="
python3 execution/build_digest_markdown.py

echo "=== Web archive ==="
python3 execution/build_web_archive.py --use-canonical-fallback

if [[ -n "${TEST_EMAIL}" ]]; then
  echo "=== Test email to ${TEST_EMAIL} ==="
  python3 execution/send_daily_email.py --test-email "${TEST_EMAIL}"
elif [[ "${SEND}" -eq 1 ]]; then
  echo "=== Production email send ==="
  python3 execution/send_daily_email.py
fi

if [[ "${COMMIT}" -eq 1 ]]; then
  echo "=== Commit generated artifacts ==="
  git add data/digests/*.json frontend/issues
  if git diff --staged --quiet; then
    echo "No digest or archive changes to commit."
  else
    git commit -m "chore: persist local Claude digest and web archive"
    echo "Committed locally. Review, then push to deploy on Vercel."
  fi
fi

echo "Done. Push main to publish the site on Vercel."

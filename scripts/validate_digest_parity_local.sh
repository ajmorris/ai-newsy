#!/usr/bin/env bash
# Compare repo canonical digest JSON vs frontend/issues (pre-send / Vercel inputs).
# If data/digests/snapshots/YYYY-MM-DD.sent.json exists, it is the email source of truth.
# Does not call the Anthropic API. Test email is optional and does not mark sent_at.
#
#   ./scripts/validate_digest_parity_local.sh
#   ./scripts/validate_digest_parity_local.sh 2026-04-23
#   ./scripts/validate_digest_parity_local.sh --test-email you@example.com
#   ./scripts/validate_digest_parity_local.sh --test-email you@example.com 2026-04-23

set -euo pipefail
cd "$(dirname "$0")/.."

usage() {
  cat <<'EOF'
Usage: ./scripts/validate_digest_parity_local.sh [--test-email EMAIL] [YYYY-MM-DD]

Compares repo data/digests/YYYY-MM-DD.json to frontend/issues/.
A sent snapshot, if present, is preferred as the email source of truth.
EOF
}

TEST_EMAIL=""
DIGEST_DATE=""

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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ "$1" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        DIGEST_DATE="$1"
      elif [[ "$1" == *@* && -z "${TEST_EMAIL}" ]]; then
        TEST_EMAIL="$1"
      else
        echo "Unknown argument: $1"
        usage
        exit 1
      fi
      shift
      ;;
  esac
done

if [[ -z "${DIGEST_DATE}" ]]; then
  DIGEST_DATE="$(date -u +%F)"
fi

if [[ ! -f "data/digests/${DIGEST_DATE}.json" ]]; then
  echo "Missing data/digests/${DIGEST_DATE}.json. Assemble the Desktop digest first."
  exit 1
fi

if [[ ! -f "frontend/issues/index.json" ]]; then
  echo "Missing frontend/issues/index.json. Assemble so Vercel has today's issue."
  exit 1
fi

mkdir -p .tmp
REPORT_PATH=".tmp/parity-report.json"

echo "=== Parity: repo canonical JSON vs frontend/issues (${DIGEST_DATE}) ==="
if [[ -f "data/digests/snapshots/${DIGEST_DATE}.sent.json" ]]; then
  echo "Using sent snapshot as email source of truth."
else
  echo "No sent snapshot yet; comparing canonical JSON to the archive (pre-send)."
fi

python3 execution/validate_digest_parity.py \
  --digest-date "${DIGEST_DATE}" \
  --digest-dir data/digests \
  --snapshot-dir data/digests/snapshots \
  --issues-dir frontend/issues \
  --report "${REPORT_PATH}"

if [[ -n "${TEST_EMAIL}" ]]; then
  echo ""
  echo "=== Optional test email to ${TEST_EMAIL} (no sent_at) ==="
  python3 execution/send_daily_email.py --no-llm --test-email "${TEST_EMAIL}" --digest-date "${DIGEST_DATE}"
fi

echo ""
echo "Parity validation passed."
echo "  Canonical digest: data/digests/${DIGEST_DATE}.json"
echo "  Web issue:        frontend/issues/${DIGEST_DATE}.html"
echo "  Report:           ${REPORT_PATH}"

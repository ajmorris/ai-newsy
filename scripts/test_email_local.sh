#!/usr/bin/env bash
# Send one test email from the Desktop/canonical digest path.
# Does not mark articles sent_at and does not call the Anthropic API.
#
#   ./scripts/test_email_local.sh [you@example.com]
#
# Uses .tmp/claude-digest.json when present (assemble first).
# Otherwise sends from today's committed data/digests/YYYY-MM-DD.json (--no-llm).
# Requires Resend vars in .env for the send itself.

set -euo pipefail
cd "$(dirname "$0")/.."

TEST_EMAIL="${1:-aj+supabase@ajmorris.me}"
DIGEST_DATE="$(date -u +%F)"

if [[ ! -f .env ]]; then
  echo "Create .env from .env.example. Local generate needs SUPABASE_URL and SUPABASE_SECRET_KEY."
  echo "A test send also needs RESEND_API_KEY, EMAIL_FROM, and APP_URL."
  exit 1
fi

if [[ -f .tmp/claude-digest.json ]]; then
  echo "=== Assemble Claude Desktop digest, then test-email ${TEST_EMAIL} ==="
  ./scripts/run_local_digest.sh --assemble --test-email "${TEST_EMAIL}"
elif [[ -f "data/digests/${DIGEST_DATE}.json" ]]; then
  echo "=== Test email from committed canonical JSON (${DIGEST_DATE}) to ${TEST_EMAIL} ==="
  python3 execution/send_daily_email.py --no-llm --test-email "${TEST_EMAIL}" --digest-date "${DIGEST_DATE}"
else
  echo "Need .tmp/claude-digest.json or data/digests/${DIGEST_DATE}.json."
  echo "Write the Desktop digest first, then assemble, or wait until today's JSON is in the repo."
  exit 1
fi

echo ""
echo "Done. Check inbox for ${TEST_EMAIL}. sent_at was not marked."

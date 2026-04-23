#!/usr/bin/env bash
# Local-only parity validation:
# - builds canonical digest in temp dir
# - sends a test email only (no sent_at writes)
# - builds web issue files in temp dir
# - validates parity and outputs a local report
#
# Usage:
#   ./scripts/validate_digest_parity_local.sh you@example.com [YYYY-MM-DD]

set -euo pipefail

cd "$(dirname "$0")/.."

TEST_EMAIL="${1:-}"
DIGEST_DATE="${2:-}"

if [[ -z "${TEST_EMAIL}" ]]; then
  echo "Usage: ./scripts/validate_digest_parity_local.sh you@example.com [YYYY-MM-DD]"
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo "Missing .env file. Create it from .env.example first."
  exit 1
fi

TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ai-newsy-parity.XXXXXX")"
export DIGEST_MARKDOWN_DIR="${TEMP_ROOT}/digests"
export DIGEST_SNAPSHOT_DIR="${TEMP_ROOT}/digests/snapshots"
export WEB_ARCHIVE_OUTPUT_DIR="${TEMP_ROOT}/issues"
REPORT_PATH="${TEMP_ROOT}/parity-report.json"

mkdir -p "${DIGEST_MARKDOWN_DIR}" "${DIGEST_SNAPSHOT_DIR}" "${WEB_ARCHIVE_OUTPUT_DIR}"

echo "Using temporary workspace:"
echo "  DIGEST_MARKDOWN_DIR=${DIGEST_MARKDOWN_DIR}"
echo "  DIGEST_SNAPSHOT_DIR=${DIGEST_SNAPSHOT_DIR}"
echo "  WEB_ARCHIVE_OUTPUT_DIR=${WEB_ARCHIVE_OUTPUT_DIR}"

DIGEST_DATE_ARGS=()
if [[ -n "${DIGEST_DATE}" ]]; then
  DIGEST_DATE_ARGS+=(--digest-date "${DIGEST_DATE}")
fi

echo ""
echo "=== 1) Build canonical payload + markdown (temp) ==="
python3 execution/digest_payload.py "${DIGEST_DATE_ARGS[@]}"
python3 execution/build_digest_markdown.py "${DIGEST_DATE_ARGS[@]}"

if [[ -z "${DIGEST_DATE}" ]]; then
  DIGEST_DATE="$(ls -1 "${DIGEST_MARKDOWN_DIR}"/*.json | sed -E 's|.*/||' | sed -E 's|\.json$||' | sort | tail -n 1)"
fi

echo ""
echo "=== 2) Send test email only (no production sent_at writes) ==="
python3 execution/send_daily_email.py --test-email "${TEST_EMAIL}" --digest-date "${DIGEST_DATE}"

echo ""
echo "=== 3) Build local web archive (temp) ==="
python3 execution/build_web_archive.py

echo ""
echo "=== 4) Validate parity ==="
python3 execution/validate_digest_parity.py \
  --digest-date "${DIGEST_DATE}" \
  --digest-dir "${DIGEST_MARKDOWN_DIR}" \
  --snapshot-dir "${DIGEST_SNAPSHOT_DIR}" \
  --issues-dir "${WEB_ARCHIVE_OUTPUT_DIR}" \
  --report "${REPORT_PATH}"

echo ""
echo "Parity validation passed."
echo "Artifacts:"
echo "  Canonical digest: ${DIGEST_MARKDOWN_DIR}/${DIGEST_DATE}.json"
echo "  Markdown digest:  ${DIGEST_MARKDOWN_DIR}/${DIGEST_DATE}.md"
echo "  Sent snapshot:   ${DIGEST_SNAPSHOT_DIR}/${DIGEST_DATE}.sent.json"
echo "  Web issue:        ${WEB_ARCHIVE_OUTPUT_DIR}/${DIGEST_DATE}.html"
echo "  Report:           ${REPORT_PATH}"

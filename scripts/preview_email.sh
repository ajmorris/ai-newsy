#!/usr/bin/env bash
# Render the daily email to emails/preview/index.html and, when Mailpit is up,
# inject the same message into the local inbox.
# Run from anywhere: ./scripts/preview_email.sh [--date YYYY-MM-DD | --payload path]

set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d emails/node_modules/mjml ]; then
  npm ci --prefix emails
fi

exec python3 execution/preview_email.py "$@"

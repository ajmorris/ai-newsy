#!/usr/bin/env bash
# Run the full pipeline locally and send one test email to aj+supabase@ajmorris.me
# Requires: .env with SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY, SENDGRID_API_KEY, EMAIL_FROM, APP_URL
# Run from repo root: ./scripts/test_email_local.sh

set -e
cd "$(dirname "$0")/.."
TEST_EMAIL="${1:-aj+supabase@ajmorris.me}"

if [ ! -f .env ]; then
  echo "Create .env from .env.example and set SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY, SENDGRID_API_KEY, EMAIL_FROM, APP_URL"
  exit 1
fi

echo "=== 1. Fetch AI news (limit 3 per feed) ==="
python3 execution/fetch_ai_news.py --limit 3

echo ""
echo "=== 2. Fetch X posts (limit 2 per account) ==="
python3 execution/fetch_x_posts.py --limit 2 || true

echo ""
echo "=== 3. Summarize articles (limit 5) ==="
python3 execution/summarize_articles.py --limit 5

echo ""
echo "=== 4. Send test email to $TEST_EMAIL ==="
python3 execution/send_daily_email.py --test-email "$TEST_EMAIL"

echo ""
echo "Done. Check inbox for $TEST_EMAIL"

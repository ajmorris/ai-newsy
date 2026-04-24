# Safe Test Email Runbook (No Production Marking)

This runbook lets you test and tweak the daily email repeatedly without marking articles as sent in production.

## What keeps this safe

- Use `--test-email` when sending.  
  This sends to one inbox and **does not** mark `articles.sent_at`.
- Optional `--dry-run` modes generate payload/content without sending.
- Do **not** run `send_daily_email.py` without `--test-email`.

## Prerequisites

1. From repo root:
   ```bash
   cd /Users/ajmorris/code/ai-newsy
   ```
2. Ensure env is loaded (`.env` present) with at least:
   - `SUPABASE_URL`
   - `SUPABASE_SECRET_KEY`
   - `RESEND_API_KEY`
   - `EMAIL_FROM`
   - `APP_URL`
   - AI keys (`GEMINI_API_KEY` and/or `ANTHROPIC_KEY` and/or `OPENAI_API_KEY`)
3. Install deps (once per environment):
   ```bash
   pip install -r requirements.txt
   npm ci --prefix emails
   ```

## Step-by-step safe test flow

### 1) Pick a test date (recommended)

Use a fixed digest date while iterating so results are stable:

```bash
export DIGEST_DATE=2026-04-23
```

If you want "today", skip this variable and omit `--digest-date` in commands below.

### 2) (Optional) Refresh content inputs

If you want latest data in staging-like flow:

```bash
python execution/fetch_ai_news.py --limit 10
python execution/analyze_articles_single_pass.py
python execution/generate_tweet_headlines.py --digest-date "$DIGEST_DATE"
python execution/generate_community_headlines.py --digest-date "$DIGEST_DATE"
python execution/generate_atomic_reading_essay.py --digest-date "$DIGEST_DATE"
python execution/generate_youtube_watching.py --digest-date "$DIGEST_DATE"
python execution/generate_around_web_headlines.py --digest-date "$DIGEST_DATE"
```

If you only want to test template tweaks, you can skip this and reuse existing stored extras/payload.

### 3) Build digest artifacts only (no send)

```bash
python execution/digest_payload.py --digest-date "$DIGEST_DATE"
python execution/build_digest_markdown.py --digest-date "$DIGEST_DATE"
```

### 4) Dry-run email send logic (no send)

```bash
python execution/send_daily_email.py --digest-date "$DIGEST_DATE" --dry-run
```

This validates payload + rendering path without contacting recipients.

### 5) Send one safe test email to yourself

```bash
python execution/send_daily_email.py --digest-date "$DIGEST_DATE" --test-email "you@yourdomain.com"
```

This is the key safe command: it sends only to that address and does not mark production articles as sent.

### 6) Iterate quickly after template/content changes

After each change:

```bash
python execution/build_digest_markdown.py --digest-date "$DIGEST_DATE"
python execution/send_daily_email.py --digest-date "$DIGEST_DATE" --test-email "you@yourdomain.com"
```

Repeat until the email looks right.

## Verification checks (recommended each run)

1. Confirm subject + branding text are correct.
2. Confirm sections render in order:
   - What I'm Reading
   - What I'm Watching
   - Around the Web
3. Confirm all links click through.
4. Confirm fallback behavior when a section is empty.
5. Confirm no production marking:
   - You should always be using `--test-email`.

## Commands to avoid during testing

Do **not** use this while iterating:

```bash
python execution/send_daily_email.py
```

Without `--test-email`, successful sends can mark articles as sent in production mode.

## Optional: one-command safe loop

Use this when doing repeated visual tweaks:

```bash
python execution/build_digest_markdown.py --digest-date "$DIGEST_DATE" && \
python execution/send_daily_email.py --digest-date "$DIGEST_DATE" --test-email "you@yourdomain.com"
```


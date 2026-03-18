# Running AI Newsy locally (new computer)

## 1. Python

Use **Python 3.10+** (3.11 or 3.12 recommended).

```bash
python3 --version
```

## 2. Clone and enter the repo

If you haven’t already:

```bash
git clone <your-repo-url> ai-newsy
cd ai-newsy
```

## 3. Virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Environment variables

Copy the example env file and edit it:

```bash
cp .env.example .env
```

Edit `.env` and set at least:

| Variable        | Required for                         | Where to get it |
|----------------|--------------------------------------|------------------|
| `SUPABASE_URL` | Fetch, DB, digest, cleanup            | [Supabase](https://supabase.com/dashboard) → Project → Settings → API |
| `SUPABASE_KEY` | Same as above                        | Same (anon/public key) |
| `GEMINI_API_KEY` | Topic assignment, summarization, email | [Google AI Studio](https://aistudio.google.com/apikey) |
| `RESEND_API_KEY` | Sending the daily email            | [Resend](https://resend.com/api-keys) |
| `EMAIL_FROM`   | Sending email                        | Your sending address (e.g. `newsletter@yourdomain.com`) |
| `APP_URL`      | Links in the email                   | Your app URL (e.g. Vercel URL or `http://localhost:3000`) |

- **RSS-only (no DB):** You can run `scripts/check_feeds.py` without any env vars (it only needs `feedparser` and `requests`).
- **Fetch + DB:** You need `SUPABASE_URL` and `SUPABASE_KEY`.
- **Full digest (assign topics, summarize, send email):** You need all of the above.

## 5. Run from repo root

All commands assume you’re in the project root (`ai-newsy/`).

**Check that feeds load (no Supabase needed):**

```bash
python3 scripts/check_feeds.py
```

**Fetch RSS and insert into Supabase (dry-run, no DB writes):**

```bash
python3 execution/fetch_ai_news.py --dry-run --limit 3
```

**Fetch and insert for real:**

```bash
python3 execution/fetch_ai_news.py --limit 10
```

**Assign topics (needs `GEMINI_API_KEY` and Supabase):**

```bash
python3 execution/assign_topics.py
```

**Summarize and send daily email:** see `execution/summarize_articles.py` and `execution/send_daily_email.py` (need Gemini + Resend + Supabase).

## 6. Frontend (optional)

If the project has a web frontend:

```bash
cd frontend
npm install
npm run dev
```

Check `frontend/package.json` for the exact dev command.

## Quick checklist

- [ ] Python 3.10+ installed  
- [ ] Repo cloned, `cd ai-newsy`  
- [ ] `python3 -m venv .venv` and `source .venv/bin/activate`  
- [ ] `pip install -r requirements.txt`  
- [ ] `cp .env.example .env` and set `SUPABASE_URL`, `SUPABASE_KEY` (and others as needed)  
- [ ] `python3 scripts/check_feeds.py` runs and shows feed status  

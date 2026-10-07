-- D1 schema for the digest worker.
-- Integer primary keys replace Postgres serial ids.
-- JSON documents are stored as text.
-- Timestamps are ISO-8601 strings.
-- D1 has no table policies. The Worker enforces access itself.
-- The current Supabase database has no stored procedures to port.

CREATE TABLE subscribers (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    confirm_token TEXT UNIQUE NOT NULL,
    confirmed INTEGER NOT NULL DEFAULT 0,
    subscribed_at TEXT NOT NULL,
    unsubscribed_at TEXT,
    suppressed_at TEXT
);

CREATE INDEX idx_subscribers_email ON subscribers(email);
CREATE INDEX idx_subscribers_active ON subscribers(confirmed, unsubscribed_at);

CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT,
    summary TEXT,
    opinion TEXT,
    image_url TEXT,
    topic TEXT,
    analysis TEXT,
    analyzed_at TEXT,
    analysis_model TEXT,
    analysis_prompt_version TEXT,
    analysis_run_id TEXT,
    fetched_at TEXT,
    published_at TEXT,
    sent_at TEXT
);

CREATE INDEX idx_articles_url ON articles(url);
CREATE INDEX idx_articles_unsent ON articles(sent_at);

CREATE TABLE digests (
    id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL,
    sent_at TEXT NOT NULL
);

CREATE TABLE digest_extras (
    id INTEGER PRIMARY KEY,
    digest_date TEXT NOT NULL,
    key TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (digest_date, key)
);

CREATE TABLE digest_sends (
    id INTEGER PRIMARY KEY,
    digest_date TEXT NOT NULL,
    send_mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'claimed',
    github_run_id TEXT,
    github_run_attempt TEXT,
    event_name TEXT,
    sent_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    claimed_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE (digest_date, send_mode)
);

CREATE TABLE issues (
    issue_id TEXT PRIMARY KEY,
    digest_date TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    published_at TEXT NOT NULL
);

CREATE TABLE email_sends (
    id INTEGER PRIMARY KEY,
    issue_id TEXT NOT NULL,
    subscriber_id INTEGER NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    sent_at TEXT,
    UNIQUE (issue_id, subscriber_id)
);

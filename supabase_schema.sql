-- AI Newsy Database Schema for Supabase
-- Run this in your Supabase SQL Editor (Dashboard → SQL Editor → New Query)

-- ===========================================
-- SUBSCRIBERS TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS subscribers (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    confirm_token TEXT UNIQUE NOT NULL,
    confirmed BOOLEAN DEFAULT FALSE,
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    unsubscribed_at TIMESTAMPTZ
);

-- Index for quick email lookups
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);

-- Index for active subscriber queries
CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers(confirmed, unsubscribed_at) 
    WHERE confirmed = TRUE AND unsubscribed_at IS NULL;


-- ===========================================
-- ARTICLES TABLE
-- ===========================================
CREATE TABLE IF NOT EXISTS articles (
    id BIGSERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT,
    summary TEXT,
    opinion TEXT,
    image_url TEXT,
    topic TEXT,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ
);

-- For existing deployments: add columns if missing (run in SQL Editor or migration)
-- ALTER TABLE articles ADD COLUMN IF NOT EXISTS opinion TEXT;
-- ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_url TEXT;
-- ALTER TABLE articles ADD COLUMN IF NOT EXISTS topic TEXT;

-- Index for URL deduplication
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);

-- Index for unsent articles query
CREATE INDEX IF NOT EXISTS idx_articles_unsent ON articles(sent_at) 
    WHERE sent_at IS NULL;

-- Index for topic-based digest
CREATE INDEX IF NOT EXISTS idx_articles_topic ON articles(topic) 
    WHERE topic IS NOT NULL;


-- ===========================================
-- DIGESTS TABLE (topic rotation)
-- ===========================================
CREATE TABLE IF NOT EXISTS digests (
    id BIGSERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_digests_sent_at ON digests(sent_at);


-- ===========================================
-- DIGEST EXTRAS TABLE (supplemental content)
-- ===========================================
CREATE TABLE IF NOT EXISTS digest_extras (
    id BIGSERIAL PRIMARY KEY,
    digest_date DATE NOT NULL,
    key TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (digest_date, key)
);

CREATE INDEX IF NOT EXISTS idx_digest_extras_date ON digest_extras(digest_date);
CREATE INDEX IF NOT EXISTS idx_digest_extras_key ON digest_extras(key);


-- ===========================================
-- ROW LEVEL SECURITY
-- ===========================================
-- Server-side scripts and API routes use SUPABASE_SECRET_KEY from server-only
-- environments (GitHub Actions runners and Vercel Functions). Keys are never
-- embedded in the browser bundle.
-- See supabase/migrations/20260415000000_fix_rls_policies_for_anon_role.sql
-- and supabase/migrations/20260420100000_lock_down_subscribers_rls.sql for
-- migrations that apply this change to existing deployments.
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE digests ENABLE ROW LEVEL SECURITY;
ALTER TABLE digest_extras ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to digest_extras" ON digest_extras
    FOR ALL USING (auth.role() = 'service_role');

-- Subscribers are managed only by server-side API routes using SUPABASE_SECRET_KEY.
-- Keep RLS enabled with no anon policies to avoid direct public-table writes.

CREATE POLICY "Allow all operations on articles" ON articles
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all operations on digests" ON digests
    FOR ALL USING (true) WITH CHECK (true);

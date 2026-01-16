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
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ
);

-- Index for URL deduplication
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);

-- Index for unsent articles query
CREATE INDEX IF NOT EXISTS idx_articles_unsent ON articles(sent_at) 
    WHERE sent_at IS NULL;


-- ===========================================
-- ROW LEVEL SECURITY (Optional but recommended)
-- ===========================================
-- Enable RLS on tables
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (for backend scripts)
CREATE POLICY "Service role has full access to subscribers" ON subscribers
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to articles" ON articles
    FOR ALL USING (auth.role() = 'service_role');

-- Allow anon role to insert subscribers (for public subscription form)
CREATE POLICY "Anyone can subscribe" ON subscribers
    FOR INSERT WITH CHECK (true);

-- Allow anon role to read their own subscription (for confirm/unsubscribe)
CREATE POLICY "Users can confirm/unsubscribe" ON subscribers
    FOR UPDATE USING (true);

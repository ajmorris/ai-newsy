-- Add topic to articles and create digests table for topic rotation.
-- Run in Supabase SQL Editor or via: npx supabase db push

ALTER TABLE articles ADD COLUMN IF NOT EXISTS topic TEXT;

CREATE TABLE IF NOT EXISTS digests (
    id BIGSERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_digests_sent_at ON digests(sent_at);
CREATE INDEX IF NOT EXISTS idx_articles_topic ON articles(topic) WHERE topic IS NOT NULL;

ALTER TABLE digests ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role has full access to digests" ON digests
    FOR ALL USING (auth.role() = 'service_role');

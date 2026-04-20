-- Add semantic-deduplication columns to articles.
-- Losing duplicates are preserved in the DB and flagged via is_duplicate_of,
-- so the digest can skip them while remaining auditable.

ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS is_duplicate_of BIGINT REFERENCES articles(id),
    ADD COLUMN IF NOT EXISTS dedup_checked_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dedup_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_articles_not_duplicate ON articles(sent_at)
    WHERE is_duplicate_of IS NULL;

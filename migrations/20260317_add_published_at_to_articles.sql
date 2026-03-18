-- Add published_at column to articles and backfill from fetched_at
ALTER TABLE articles
ADD COLUMN IF NOT EXISTS published_at timestamptz NULL;

UPDATE articles
SET published_at = fetched_at
WHERE published_at IS NULL;


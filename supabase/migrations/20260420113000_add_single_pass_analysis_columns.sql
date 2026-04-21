-- Add columns for single-pass article analysis persistence.
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS analysis JSONB,
    ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS analysis_model TEXT,
    ADD COLUMN IF NOT EXISTS analysis_prompt_version TEXT,
    ADD COLUMN IF NOT EXISTS analysis_run_id TEXT,
    ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_articles_analysis_run_id ON articles(analysis_run_id)
    WHERE analysis_run_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_articles_analyzed_at ON articles(analyzed_at)
    WHERE analyzed_at IS NOT NULL;

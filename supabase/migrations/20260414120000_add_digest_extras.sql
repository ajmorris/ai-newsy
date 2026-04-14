-- Store per-digest supplemental content (e.g. tweet headlines).

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

ALTER TABLE digest_extras ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to digest_extras" ON digest_extras
    FOR ALL USING (auth.role() = 'service_role');

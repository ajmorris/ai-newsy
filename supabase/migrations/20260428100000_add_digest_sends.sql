-- Track production digest sends with a database-backed atomic claim, so we send
-- exactly one production digest per (digest_date, send_mode) even when multiple
-- workflow runs (cron, manual, retries) execute concurrently.
--
-- Background: the daily digest workflow has two cron candidates (DST-safe) and
-- the previous in-job guard used `exit 0`, which only ends a single step.
-- Snapshot files on the runner are not durable across separate workflow runs,
-- so two GitHub Actions runs sent the same digest twice in one day.
--
-- Usage:
--   1. Caller attempts INSERT (digest_date, send_mode). UNIQUE constraint
--      ensures only one row wins. Winner proceeds to send.
--   2. After the loop, winner UPDATEs the row with completed_at + counts.
--   3. On hard failure before any email goes out, caller may set status='failed'
--      so the day can be retried with a fresh claim.

CREATE TABLE IF NOT EXISTS digest_sends (
    id BIGSERIAL PRIMARY KEY,
    digest_date DATE NOT NULL,
    send_mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'claimed',
    github_run_id TEXT,
    github_run_attempt TEXT,
    event_name TEXT,
    sent_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE (digest_date, send_mode)
);

CREATE INDEX IF NOT EXISTS idx_digest_sends_date ON digest_sends(digest_date);
CREATE INDEX IF NOT EXISTS idx_digest_sends_status ON digest_sends(status);

ALTER TABLE digest_sends ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all operations on digest_sends" ON digest_sends;
CREATE POLICY "Allow all operations on digest_sends" ON digest_sends
    FOR ALL USING (true) WITH CHECK (true);

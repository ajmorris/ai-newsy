-- Allow server-side anon key workflows to read/write digest_extras.
-- This mirrors the current project policy model used for other backend tables.

DROP POLICY IF EXISTS "Service role has full access to digest_extras" ON digest_extras;
DROP POLICY IF EXISTS "Allow all operations on digest_extras" ON digest_extras;

CREATE POLICY "Allow all operations on digest_extras" ON digest_extras
    FOR ALL USING (true) WITH CHECK (true);

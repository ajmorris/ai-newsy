-- RLS Policy Fix for AI Newsy
--
-- Canonical RLS migrations now live in:
--   supabase/migrations/20260415000000_fix_rls_policies_for_anon_role.sql
--   supabase/migrations/20260420100000_lock_down_subscribers_rls.sql
-- and is also reflected in supabase_schema.sql for fresh installs.
--
-- Apply it with either:
--   1. `npx supabase db push` (if your project is linked), or
--   2. Copying the migration file's contents into the Supabase SQL Editor.
--
-- Why: server-side scripts now use SUPABASE_SECRET_KEY and API routes use
-- SUPABASE_SECRET_KEY for subscriber writes. The original schema only granted service_role access, which
-- caused inserts from the "Prepare Digest Content" workflow to fail with:
--     new row violates row-level security policy for table "articles"

DROP POLICY IF EXISTS "Service role has full access to articles" ON articles;
DROP POLICY IF EXISTS "Service role has full access to digests" ON digests;
DROP POLICY IF EXISTS "Service role has full access to subscribers" ON subscribers;
DROP POLICY IF EXISTS "Allow all operations on articles" ON articles;
DROP POLICY IF EXISTS "Allow all operations on digests" ON digests;
DROP POLICY IF EXISTS "Allow all operations on subscribers" ON subscribers;

CREATE POLICY "Allow all operations on articles" ON articles
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all operations on digests" ON digests
    FOR ALL USING (true) WITH CHECK (true);

-- Subscribers are now API-only (service role), so do not recreate anon policies.

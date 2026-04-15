-- Fix RLS on digest_extras so the anon role can read/write it.
--
-- Background: digest_extras was introduced in 20260414120000_add_digest_extras.sql
-- with a service-role-only policy, but the Prepare Digest Content workflow only
-- passes SUPABASE_KEY (the anon key) to execution/generate_tweet_headlines.py.
-- That script calls upsert_digest_extra(), which then fails with:
--     new row violates row-level security policy for table "digest_extras"
-- and tomorrow's email loads an empty tweet_headlines payload.
--
-- This migration matches the permissive pattern already applied to articles,
-- digests, and subscribers in 20260415000000_fix_rls_policies_for_anon_role.sql.
-- The anon key is only used from server-side contexts (GitHub Actions runners
-- and Vercel Functions) and is never embedded in the browser bundle, so broad
-- access to the anon role is safe.

DROP POLICY IF EXISTS "Service role has full access to digest_extras" ON digest_extras;
DROP POLICY IF EXISTS "Allow all operations on digest_extras" ON digest_extras;

CREATE POLICY "Allow all operations on digest_extras" ON digest_extras
    FOR ALL USING (true) WITH CHECK (true);

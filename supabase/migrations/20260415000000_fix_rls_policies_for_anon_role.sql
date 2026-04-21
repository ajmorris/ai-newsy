-- Fix RLS policies so the anon role can access articles and digests.
-- NOTE: subscriber anon access from this migration is later removed by
-- 20260420100000_lock_down_subscribers_rls.sql.
--
-- Background: every Python script (fetch_ai_news, assign_topics, summarize_articles,
-- send_daily_email) and every Vercel API route (api/subscribe.js, api/unsubscribe.js)
-- connects to Supabase using SUPABASE_SECRET_KEY for backend operations. The
-- original schema in supabase_schema.sql only created policies
-- for auth.role() = 'service_role', so INSERTs failed with:
--     new row violates row-level security policy for table "articles"
-- when the "Prepare Digest Content" GitHub Action ran fetch_ai_news.py.
--
-- These keys are only used from server-side contexts (GitHub Actions runners and
-- Vercel Functions) and are never embedded in the browser bundle, so granting
-- broad access to the anon role matched the original schema intent.

-- ARTICLES --
DROP POLICY IF EXISTS "Service role has full access to articles" ON articles;
DROP POLICY IF EXISTS "Allow all operations on articles" ON articles;
CREATE POLICY "Allow all operations on articles" ON articles
    FOR ALL USING (true) WITH CHECK (true);

-- DIGESTS --
DROP POLICY IF EXISTS "Service role has full access to digests" ON digests;
DROP POLICY IF EXISTS "Allow all operations on digests" ON digests;
CREATE POLICY "Allow all operations on digests" ON digests
    FOR ALL USING (true) WITH CHECK (true);

-- SUBSCRIBERS --
-- The existing "Anyone can subscribe" (INSERT) and "Users can confirm/unsubscribe"
-- (UPDATE) policies remain; we additionally replace the service-role-only FOR ALL
-- policy so SELECTs from get_active_subscribers() work under the anon role.
DROP POLICY IF EXISTS "Service role has full access to subscribers" ON subscribers;
DROP POLICY IF EXISTS "Allow all operations on subscribers" ON subscribers;
CREATE POLICY "Allow all operations on subscribers" ON subscribers
    FOR ALL USING (true) WITH CHECK (true);

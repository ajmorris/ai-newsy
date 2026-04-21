-- Lock down subscribers table access behind server-side API routes.
--
-- Context:
-- - Public signup/unsubscribe requests flow through Vercel API routes.
-- - Those routes now use SUPABASE_SECRET_KEY (service role), so table-level anon
--   policies are no longer required for subscribers.
-- - Service-role access bypasses RLS; removing anon policies reduces abuse risk.

DO $$
DECLARE
    policy_record RECORD;
BEGIN
    FOR policy_record IN
        SELECT policyname
        FROM pg_policies
        WHERE schemaname = 'public'
            AND tablename = 'subscribers'
    LOOP
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON subscribers',
            policy_record.policyname
        );
    END LOOP;
END $$;

-- RLS Policy Fix for AI Newsy
-- Run this in Supabase SQL Editor to allow the anon key to insert/read articles
-- This is needed because our Python scripts use the anon key

-- ==========================================
-- Option 1: Disable RLS entirely (simpler, fine for this use case)
-- ==========================================
ALTER TABLE articles DISABLE ROW LEVEL SECURITY;
ALTER TABLE subscribers DISABLE ROW LEVEL SECURITY;

-- ==========================================
-- Option 2: Keep RLS but allow all operations (uncomment if you prefer RLS)
-- ==========================================
-- DROP POLICY IF EXISTS "Service role has full access to articles" ON articles;
-- DROP POLICY IF EXISTS "Service role has full access to subscribers" ON subscribers;
-- DROP POLICY IF EXISTS "Anyone can subscribe" ON subscribers;
-- DROP POLICY IF EXISTS "Users can confirm/unsubscribe" ON subscribers;

-- CREATE POLICY "Allow all operations on articles" ON articles FOR ALL USING (true) WITH CHECK (true);
-- CREATE POLICY "Allow all operations on subscribers" ON subscribers FOR ALL USING (true) WITH CHECK (true);

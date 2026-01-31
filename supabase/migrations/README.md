# Migrations

`db push` does **not** use your `.env` file. It needs either a linked project or a database URL.

---

**Option A – Link then push (recommended if you use CLI)**

1. Get your **project ref** from the Supabase URL in `.env`:  
   `SUPABASE_URL=https://XXXXXXXX.supabase.co` → ref is `XXXXXXXX`.

2. Link (you’ll be prompted for your database password or access token):
   ```bash
   npx supabase link --project-ref XXXXXXXX
   ```

3. Push migrations:
   ```bash
   npx supabase db push
   ```

---

**Option B – Run SQL in the Dashboard (no link needed)**

1. Open [Supabase Dashboard](https://supabase.com/dashboard) → your project → **SQL Editor**.
2. New query → paste and run the migration you need.

**Opinion + image_url (if not already applied):**
```sql
ALTER TABLE articles ADD COLUMN IF NOT EXISTS opinion TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_url TEXT;
```

**Topic + digests (Phase 6):**  
(Copy the full block; ensure the first line starts with **ALTER**, not LTER.)
```sql
-- Add topic column and digests table
ALTER TABLE articles ADD COLUMN IF NOT EXISTS topic TEXT;

CREATE TABLE IF NOT EXISTS digests (
    id BIGSERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_digests_sent_at ON digests(sent_at);
CREATE INDEX IF NOT EXISTS idx_articles_topic ON articles(topic) WHERE topic IS NOT NULL;

ALTER TABLE digests ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role has full access to digests" ON digests
    FOR ALL USING (auth.role() = 'service_role');
```

---

**Option C – Push with database URL**

From Dashboard → Settings → Database → Connection string (URI):
```bash
npx supabase db push --db-url "postgresql://postgres.[ref]:[PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres"
```

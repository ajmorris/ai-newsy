-- Add opinion and image_url columns to articles (for AI takeaway and og:image)
ALTER TABLE articles ADD COLUMN IF NOT EXISTS opinion TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_url TEXT;

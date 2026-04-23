# Canonical Digest Schema

AI Newsy uses one canonical issue artifact per date at `data/digests/YYYY-MM-DD.json`.

## Schema version

- `schema_version`: `digest-json-v1`

## Top-level fields

- `digest_date` (`YYYY-MM-DD`)
- `issue_id` (date-derived identifier, `YYYYMMDD`)
- `subject_line` (single source for email/web issue subject text)
- `intro` (single source intro paragraph)
- `article_count` (count of included stories)
- `stories` (flat ordered list used for parity checks)
- `sections` (grouped stories for rendering)
- `tweet_headlines` (ordered quick hits list)
- `community_headlines` (ordered quick hits list)
- `build_meta` (generation metadata, provenance)
- `content_hash` (sha256 hash over canonical content fields)

## Story shape

Each `stories[]` item includes:

- `id`
- `source`
- `title`
- `url`
- `topic`
- `category`
- `summary`
- `opinion`
- `image_url`
- `published_at`
- `fetched_at`

## Determinism contract

For a given `digest_date`, parity-sensitive renderers must use only:

- `subject_line`
- `intro`
- `stories`
- `tweet_headlines`
- `community_headlines`

Any recomputation of these fields outside canonical payload generation is disallowed.

## Example (truncated)

```json
{
  "schema_version": "digest-json-v1",
  "digest_date": "2026-04-23",
  "issue_id": "20260423",
  "subject_line": "ISSUE 60423 · 8 STORIES · 11 MIN READ",
  "intro": "It's a Google kind of day...",
  "article_count": 8,
  "stories": [],
  "sections": [],
  "tweet_headlines": [],
  "community_headlines": [],
  "build_meta": {
    "source": "canonical"
  },
  "content_hash": "..."
}
```

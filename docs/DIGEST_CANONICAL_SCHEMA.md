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
- `dev_headlines` (optional; headline-style developer items, empty or absent on older issues)
- `human_items` (optional; human-side items, empty or absent on older issues)
- `quick_hit_sections` (optional render list of `{title, items}` used by the archive)

Story objects may include an optional `cluster` object (`sources`, `badge_count`, `conflicts`, `is_update`). Renderers treat a missing `cluster`, `dev_headlines`, or `human_items` as empty so older issues still build.

`human_items` entries, when present, include `headline`, `url`, `summary`, `tag`, and `meaning` (the line shown as “What this means for people leading change”). A `cluster` is copied onto the item when the story was grouped. The list is omitted or empty when fewer than two items qualify, and it never holds more than four.
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

`dev_headlines`, `human_items`, `quick_hit_sections`, and `cluster` are not part of the hash. Any recomputation of the parity fields outside canonical payload generation is disallowed.

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

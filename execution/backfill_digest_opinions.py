#!/usr/bin/env python3
"""
Backfill empty opinion fields in canonical digest JSON files.

Uses the same heal + assert + refresh path as the daily pipeline.
Requires LLM keys in the environment (derive_opinion_from_summary).

Usage:
  python execution/backfill_digest_opinions.py --digest-date 2026-05-05
  python execution/backfill_digest_opinions.py --digest-date 2026-04-23 --dry-run
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from execution.digest_payload import (
    assert_digest_stories_have_opinions,
    heal_digest_story_opinions,
    load_digest_payload,
    refresh_digest_payload_after_story_edit,
    write_digest_payload,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill empty digest opinions in JSON")
    parser.add_argument("--digest-date", type=str, required=True, help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Print changes only, do not write")
    args = parser.parse_args()

    payload = load_digest_payload(digest_date=args.digest_date)
    if not payload:
        raise SystemExit(f"No digest JSON found for {args.digest_date}")

    stories = list(payload.get("stories") or [])
    before = sum(1 for s in stories if not str(s.get("opinion", "") or "").strip())
    if before == 0:
        print(f"No empty opinions in {args.digest_date}; nothing to do.")
        return

    print(f"Found {before} story/stories with empty opinion; healing...")
    heal_digest_story_opinions(stories)
    assert_digest_stories_have_opinions(stories)
    refresh_digest_payload_after_story_edit(payload, stories)

    after = sum(1 for s in stories if not str(s.get("opinion", "") or "").strip())
    print(f"Empty opinions after heal: {after}")

    if args.dry_run:
        print("Dry run: not writing file.")
        return

    path = write_digest_payload(payload)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()

"""
Delete articles older than N days (by fetched_at) to keep the database lean.
Run on a schedule (e.g. weekly via GitHub Actions) or manually.

Usage:
  python execution/cleanup_old_articles.py
  python execution/cleanup_old_articles.py --days 30
  python execution/cleanup_old_articles.py --dry-run
"""

import os
import argparse
from datetime import datetime, timedelta

import sys
sys.path.insert(0, '.')
from execution.database import supabase, delete_articles_older_than


def main():
    parser = argparse.ArgumentParser(description="Delete articles older than N days")
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.getenv("ARTICLE_RETENTION_DAYS", "30")),
        help="Delete articles older than this many days (default: 30 or ARTICLE_RETENTION_DAYS)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report how many would be deleted, do not delete",
    )
    args = parser.parse_args()

    if args.days < 1:
        print("--days must be at least 1")
        return 1

    cutoff = (datetime.utcnow() - timedelta(days=args.days)).isoformat()
    if args.dry_run:
        result = supabase.table("articles").select("id", count="exact").lt("fetched_at", cutoff).execute()
        count = result.count or 0
        print(f"[DRY RUN] Would delete {count} article(s) with fetched_at before {cutoff[:10]}")
        return 0

    deleted = delete_articles_older_than(args.days)
    print(f"Deleted {deleted} article(s) older than {args.days} days")
    return 0


if __name__ == "__main__":
    exit(main())

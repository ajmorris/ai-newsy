"""Fail when today's production send snapshot is missing.

The daily pipeline commits data/digests/snapshots/YYYY-MM-DD.sent.json after a
real send. This check looks for that file for the America/New_York date.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def digest_date_for_heartbeat(now: datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(NY).date().isoformat()


def production_snapshot_recorded(snapshot_dir: Path, digest_date: str) -> bool:
    path = snapshot_dir / f"{digest_date}.sent.json"
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    meta = ((payload.get("build_meta") or {}).get("snapshot_meta") or {})
    if not isinstance(meta, dict):
        return False
    send_mode = str(meta.get("send_mode", "")).strip().lower()
    completed = str(meta.get("send_completed_at", "")).strip()
    return send_mode == "production" and bool(completed)


def check_heartbeat(snapshot_dir: Path, now: datetime) -> str:
    digest_date = digest_date_for_heartbeat(now)
    if production_snapshot_recorded(snapshot_dir, digest_date):
        return f"OK: production send recorded for {digest_date}"
    return f"ALERT: no production send recorded for {digest_date}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that today's digest send snapshot exists")
    parser.add_argument(
        "--snapshot-dir",
        default="data/digests/snapshots",
        help="Directory of YYYY-MM-DD.sent.json files",
    )
    args = parser.parse_args(argv)
    message = check_heartbeat(Path(args.snapshot_dir), datetime.now(timezone.utc))
    print(message)
    return 0 if message.startswith("OK:") else 1


if __name__ == "__main__":
    sys.exit(main())

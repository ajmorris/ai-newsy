"""Normalize summary/opinion text in canonical digest JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys

sys.path.insert(0, ".")

from execution.story_text_normalizer import normalize_story_text


def _normalize_story(story: Dict[str, Any]) -> bool:
    changed = False
    summary = str(story.get("summary", "") or "")
    opinion = str(story.get("opinion", "") or "")
    normalized_summary = normalize_story_text(summary, max_chars=900)
    normalized_opinion = normalize_story_text(opinion, max_chars=500)
    if summary != normalized_summary:
        story["summary"] = normalized_summary
        changed = True
    if opinion != normalized_opinion:
        story["opinion"] = normalized_opinion
        changed = True
    return changed


def _normalize_payload(payload: Dict[str, Any]) -> Tuple[bool, int]:
    changed = False
    updates = 0

    for story in payload.get("stories", []) or []:
        if isinstance(story, dict) and _normalize_story(story):
            changed = True
            updates += 1

    for section in payload.get("sections", []) or []:
        if not isinstance(section, dict):
            continue
        for story in section.get("articles", []) or []:
            if isinstance(story, dict) and _normalize_story(story):
                changed = True
                updates += 1

    return changed, updates


def _target_files(data_dir: Path, snapshot_dir: Path) -> List[Path]:
    files = sorted(data_dir.glob("*.json"))
    files.extend(sorted(snapshot_dir.glob("*.sent.json")))
    return files


def run_backfill(data_dir: Path, snapshot_dir: Path, write: bool) -> Dict[str, int]:
    files = _target_files(data_dir=data_dir, snapshot_dir=snapshot_dir)
    scanned = 0
    changed_files = 0
    updated_entries = 0

    for path in files:
        scanned += 1
        payload = json.loads(path.read_text(encoding="utf-8"))
        changed, updates = _normalize_payload(payload)
        if not changed:
            continue
        changed_files += 1
        updated_entries += updates
        if write:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "scanned_files": scanned,
        "changed_files": changed_files,
        "updated_entries": updated_entries,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill digest JSON summary/opinion normalization.")
    parser.add_argument("--data-dir", default="data/digests")
    parser.add_argument("--snapshot-dir", default="data/digests/snapshots")
    parser.add_argument("--write", action="store_true", help="Write normalized content back to disk.")
    args = parser.parse_args()

    report = run_backfill(
        data_dir=Path(args.data_dir),
        snapshot_dir=Path(args.snapshot_dir),
        write=args.write,
    )
    print(json.dumps(report, indent=2))

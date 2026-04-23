"""Backfill canonical digest JSON files from legacy markdown digests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys

sys.path.insert(0, ".")

from execution.digest_payload import CANONICAL_SCHEMA_VERSION
from execution.markdown_utils import parse_frontmatter


def _issue_id_from_digest_date(digest_date: str) -> str:
    return "".join(ch for ch in digest_date if ch.isdigit())


def _parse_markdown_body(body: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], List[Dict[str, str]]]:
    sections: List[Dict[str, Any]] = []
    tweet_headlines: List[Dict[str, str]] = []
    community_headlines: List[Dict[str, str]] = []
    current_section: Dict[str, Any] | None = None
    current_story: Dict[str, Any] | None = None
    in_json = False
    json_lines: List[str] = []

    def flush_story() -> None:
        nonlocal current_story
        if current_story and current_section and current_section.get("name") not in ("From X/Twitter", "From Reddit/HN/YC"):
            current_section.setdefault("articles", []).append(current_story)
        current_story = None

    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if in_json:
            if line == "```":
                in_json = False
                if current_story:
                    try:
                        payload = json.loads("\n".join(json_lines))
                        current_story["summary"] = str(payload.get("summary", "")).strip()
                        current_story["opinion"] = str(payload.get("opinion", "")).strip()
                        current_story["image_url"] = str(payload.get("image_url", "")).strip()
                    except json.JSONDecodeError:
                        pass
                json_lines = []
            else:
                json_lines.append(raw)
            continue

        if line.startswith("## "):
            flush_story()
            current_section = {"name": line[3:].strip(), "articles": []}
            sections.append(current_section)
            continue

        if line.startswith("### "):
            flush_story()
            m = re.match(r"### \[(.+?)\]\((https?://[^\)]+)\)", line)
            if m:
                current_story = {
                    "id": None,
                    "source": "",
                    "title": m.group(1),
                    "url": m.group(2),
                    "topic": "",
                    "category": current_section["name"] if current_section else "",
                    "summary": "",
                    "opinion": "",
                    "image_url": "",
                    "published_at": "",
                    "fetched_at": "",
                }
            continue

        if line.startswith("*") and line.endswith("*") and current_story is not None:
            current_story["source"] = line.strip("*").strip()
            continue

        if line == "```json":
            in_json = True
            json_lines = []
            continue

        if line.startswith("- "):
            bullet = line[2:].strip()
            m = re.search(r"\(\[Source\]\((https?://[^\)]+)\)\)$", bullet)
            url = m.group(1) if m else ""
            headline = re.sub(r"\s*\(\[Source\]\((https?://[^\)]+)\)\)\s*$", "", bullet).strip()
            if current_section and current_section.get("name") == "From X/Twitter":
                tweet_headlines.append({"headline": headline, "url": url})
            elif current_section and current_section.get("name") == "From Reddit/HN/YC":
                source_label = ""
                label_match = re.match(r"\[([^\]]+)\]\s*(.+)$", headline)
                if label_match:
                    source_label = label_match.group(1).strip()
                    headline = label_match.group(2).strip()
                community_headlines.append({"source_label": source_label, "headline": headline, "url": url})
            continue

    flush_story()
    stories: List[Dict[str, Any]] = []
    for section in sections:
        if section["name"] in ("From X/Twitter", "From Reddit/HN/YC"):
            continue
        for story in section.get("articles", []):
            story["category"] = section["name"]
            stories.append(story)
    return sections, tweet_headlines, community_headlines


def _content_hash(payload: Dict[str, Any]) -> str:
    canonical_subset = {
        "digest_date": payload.get("digest_date"),
        "subject_line": payload.get("subject_line"),
        "intro": payload.get("intro"),
        "stories": payload.get("stories", []),
        "tweet_headlines": payload.get("tweet_headlines", []),
        "community_headlines": payload.get("community_headlines", []),
    }
    blob = json.dumps(canonical_subset, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def backfill(markdown_dir: Path) -> int:
    count = 0
    for md_path in sorted(markdown_dir.glob("*.md")):
        digest_date = md_path.stem
        json_path = markdown_dir / f"{digest_date}.json"
        if json_path.exists():
            continue
        raw = md_path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        sections, tweet_headlines, community_headlines = _parse_markdown_body(body)
        stories = [story for section in sections for story in section.get("articles", []) if section["name"] not in ("From X/Twitter", "From Reddit/HN/YC")]
        payload: Dict[str, Any] = {
            "schema_version": CANONICAL_SCHEMA_VERSION,
            "digest_date": digest_date,
            "issue_id": _issue_id_from_digest_date(digest_date),
            "subject_line": str(meta.get("subject", "")),
            "intro": str(meta.get("intro", "")),
            "article_count": len(stories),
            "stories": stories,
            "sections": [s for s in sections if s["name"] not in ("From X/Twitter", "From Reddit/HN/YC")],
            "tweet_headlines": tweet_headlines,
            "community_headlines": community_headlines,
            "build_meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_window_hours": 24,
                "use_sent": True,
                "source": "migrated",
                "source_markdown": str(md_path),
            },
        }
        payload["content_hash"] = _content_hash(payload)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        count += 1
        print(f"Backfilled {json_path}")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill canonical digest JSON from markdown.")
    parser.add_argument("--digest-dir", default="data/digests")
    args = parser.parse_args()
    created = backfill(Path(args.digest_dir))
    print(f"Created {created} canonical digest json files.")

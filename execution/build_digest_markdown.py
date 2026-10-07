"""
Build a daily digest markdown file with YAML frontmatter.

Default: compile from the existing canonical JSON (data/digests/YYYY-MM-DD.json).
Pass --rebuild to regenerate that JSON from storage (replay/backfill only).
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

import sys
sys.path.insert(0, ".")
from execution.digest_payload import (
    DigestBuildOptions,
    build_digest_payload,
    load_digest_payload,
    write_digest_payload,
)

load_dotenv()

def _yaml_quote(value: str) -> str:
    safe = (value or "").replace("\\", "\\\\").replace('"', '\\"')
    return f"\"{safe}\""


def _extract_embedded_payload(text: str) -> Dict[str, object]:
    stripped = (text or "").strip()
    if stripped.startswith("```json") and stripped.endswith("```"):
        inner = stripped[len("```json") : -3].strip()
        try:
            payload = json.loads(inner)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            return {}
    return {}


def _render_frontmatter(
    digest_date: str,
    subject: str,
    intro: str,
    sections: List[dict],
    tweet_count: int,
    community_count: int,
) -> str:
    lines = [
        "---",
        f"digest_date: {_yaml_quote(digest_date)}",
        f"subject: {_yaml_quote(subject)}",
        f"intro: {_yaml_quote(intro)}",
        f"article_count: {sum(len(s['articles']) for s in sections)}",
        f"tweet_headline_count: {tweet_count}",
        f"community_headline_count: {community_count}",
        "sections:",
    ]
    for section in sections:
        lines.append(f"  - name: {_yaml_quote(section['name'])}")
        lines.append(f"    article_count: {len(section['articles'])}")
    lines.extend(
        [
            "build_meta:",
            f"  generated_at: {_yaml_quote(datetime.now(timezone.utc).isoformat())}",
            "  source_window_hours: 24",
            "  version: \"digest-md-v1\"",
            "---",
            "",
        ]
    )
    return "\n".join(lines)


def _render_body(
    sections: List[dict],
    tweet_headlines: List[dict],
    community_headlines: List[dict],
    dev_headlines: Optional[List[dict]] = None,
) -> str:
    parts: List[str] = []
    for section in sections:
        parts.append(f"## {section['name']}\n")
        for article in section["articles"]:
            embedded_payload = _extract_embedded_payload(str(article.get("summary", "")))
            normalized_summary = (
                str(embedded_payload.get("summary", "")).strip()
                if embedded_payload
                else str(article.get("summary", "No summary available.")).strip()
            )
            normalized_opinion = (
                str(article.get("opinion", "")).strip()
                or str(embedded_payload.get("opinion", "")).strip()
            )
            normalized_topic = (
                str(article.get("topic", "")).strip()
                or str(embedded_payload.get("topic", "")).strip()
            )

            parts.append(f"### [{article.get('title', 'Untitled')}]({article.get('url', '#')})")
            parts.append(f"*{article.get('source', 'Unknown Source')}*")
            cluster = article.get("cluster") if isinstance(article.get("cluster"), dict) else {}
            badge_count = int(cluster.get("badge_count") or 0)
            if badge_count > 1 or cluster.get("is_update"):
                label = "Update" if cluster.get("is_update") and badge_count <= 1 else f"Covered by {badge_count} sources"
                if cluster.get("is_update") and badge_count > 1:
                    label = f"Update · {label}"
                parts.append(f"_{label}_")
                also = []
                for source in (cluster.get("sources") or [])[1:]:
                    name = str(source.get("source", "") or "Source")
                    url = str(source.get("url", "") or "#")
                    also.append(f"[{name}]({url})")
                if also:
                    parts.append("Also covered by " + ", ".join(also))
            article_payload = {
                "topic": normalized_topic,
                "summary": normalized_summary or "No summary available.",
                "opinion": normalized_opinion,
                "confidence": article.get("confidence"),
                "image_url": article.get("image_url") or "",
            }
            parts.append("```json")
            parts.append(json.dumps(article_payload, ensure_ascii=False, indent=2))
            parts.append("```")
            parts.append("")

    if tweet_headlines:
        parts.append("## From X/Twitter\n")
        for item in tweet_headlines:
            headline = item.get("headline", "")
            url = item.get("url", "")
            parts.append(f"- {headline} ([Source]({url}))")
        parts.append("")

    if community_headlines:
        parts.append("## From Reddit/HN/YC\n")
        for item in community_headlines:
            source = item.get("source_label", "Community")
            headline = item.get("headline", "")
            url = item.get("url", "")
            parts.append(f"- [{source}] {headline} ([Source]({url}))")
        parts.append("")

    if dev_headlines:
        parts.append("## Developer and open source\n")
        for item in dev_headlines:
            tag = str(item.get("tag", "") or "").strip()
            prefix = f"{tag} · " if tag else ""
            headline = item.get("headline", "")
            url = item.get("url", "")
            parts.append(f"- {prefix}{headline} ([Source]({url}))")
        parts.append("")

    return "\n".join(parts).strip() + "\n"


def build_digest_markdown(
    digest_date: Optional[str] = None,
    window_hours: int = 24,
    use_sent: bool = False,
    rebuild: bool = False,
) -> Tuple[Path, int]:
    resolved_date = digest_date or datetime.now(timezone.utc).date().isoformat()
    if rebuild:
        payload = build_digest_payload(
            DigestBuildOptions(
                digest_date=digest_date,
                window_hours=window_hours,
                use_sent=use_sent,
            )
        )
        write_digest_payload(payload)
    else:
        if use_sent:
            raise SystemExit(
                "--use-sent requires --rebuild (replay from already-sent DB rows)."
            )
        payload = load_digest_payload(digest_date=resolved_date)
        if not payload:
            raise SystemExit(
                f"Canonical digest payload missing for {resolved_date}. "
                "Run finalize first, or pass --rebuild to rebuild from storage."
            )
    safe_date = str(payload["digest_date"])
    sections = list(payload.get("sections", []))
    tweet_headlines = list(payload.get("tweet_headlines", []))
    community_headlines = list(payload.get("community_headlines", []))
    dev_headlines = list(payload.get("dev_headlines", []))

    frontmatter = _render_frontmatter(
        digest_date=safe_date,
        subject=str(payload.get("subject_line", "")),
        intro=str(payload.get("intro", "")),
        sections=sections,
        tweet_count=len(tweet_headlines),
        community_count=len(community_headlines),
    )
    body = _render_body(
        sections,
        tweet_headlines=tweet_headlines,
        community_headlines=community_headlines,
        dev_headlines=dev_headlines,
    )

    output_dir = Path(os.getenv("DIGEST_MARKDOWN_DIR", "data/digests"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{safe_date}.md"
    output_path.write_text(frontmatter + body, encoding="utf-8")
    print(f"Wrote digest markdown: {output_path}")
    return output_path, int(payload.get("article_count", 0))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compile daily digest markdown from canonical JSON (or rebuild from storage)"
    )
    parser.add_argument("--digest-date", type=str, default=None, help="YYYY-MM-DD (UTC)")
    parser.add_argument("--window-hours", type=int, default=int(os.getenv("DIGEST_WINDOW_HOURS", "24")))
    parser.add_argument(
        "--use-sent",
        action="store_true",
        help="With --rebuild, select already-sent stories for --digest-date (UTC day window)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild canonical JSON from storage (default: compile markdown from existing JSON)",
    )
    args = parser.parse_args()
    path, count = build_digest_markdown(
        digest_date=args.digest_date,
        window_hours=args.window_hours,
        use_sent=args.use_sent,
        rebuild=args.rebuild,
    )
    print(f"Done. articles={count} markdown={path}")

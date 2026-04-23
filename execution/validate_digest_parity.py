"""Validate canonical digest parity across email/web inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import sys

sys.path.insert(0, ".")

from execution.send_daily_email import _build_email_renderer_payload


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _story_signatures(stories: List[Dict[str, Any]]) -> List[str]:
    return [f"{s.get('title','')}|{s.get('url','')}" for s in stories]


def validate_parity(
    digest_date: str,
    digest_dir: Path,
    snapshot_dir: Path,
    issues_dir: Path,
    report_path: Path,
) -> Dict[str, Any]:
    snapshot_path = snapshot_dir / f"{digest_date}.sent.json"
    digest_path = digest_dir / f"{digest_date}.json"
    if snapshot_path.exists():
        digest = _load_json(snapshot_path)
    elif digest_path.exists():
        digest = _load_json(digest_path)
    else:
        raise SystemExit(f"Missing digest source for parity: {snapshot_path} or {digest_path}")

    stories = list(digest.get("stories", []))
    sections = list(digest.get("sections", []))
    tweet_headlines = list(digest.get("tweet_headlines", []))
    community_headlines = list(digest.get("community_headlines", []))

    # Email parity checks (input parity, not pixel parity).
    email_payload = _build_email_renderer_payload(
        sections=sections,
        intro=str(digest.get("intro", "")),
        subject=str(digest.get("subject_line", "")),
        unsubscribe_token="test-token",
        digest_date=digest_date,
        tweet_headlines=tweet_headlines,
        community_headlines=community_headlines,
    )
    email_story_sigs = [f"{s.get('headline','')}|{s.get('url','')}" for s in email_payload.get("stories", [])]
    canonical_story_sigs = _story_signatures(stories[: len(email_payload.get("stories", []))])

    checks: List[Dict[str, Any]] = []
    checks.append(
        {
            "name": "email_story_order_matches_canonical",
            "pass": email_story_sigs == canonical_story_sigs,
            "details": {"email_count": len(email_story_sigs), "canonical_count": len(canonical_story_sigs)},
        }
    )
    checks.append(
        {
            "name": "email_subject_matches_canonical",
            "pass": str(email_payload.get("subject")) == str(digest.get("subject_line")),
            "details": {},
        }
    )

    # Web parity checks.
    manifest_path = issues_dir / "index.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing archive manifest: {manifest_path}")
    manifest = _load_json(manifest_path)
    latest = manifest.get("latestIssue") or {}
    checks.append(
        {
            "name": "manifest_latest_digest_date_matches",
            "pass": str(latest.get("digestDate", "")) == digest_date,
            "details": {"manifest_latest": str(latest.get("digestDate", ""))},
        }
    )
    checks.append(
        {
            "name": "manifest_article_count_matches",
            "pass": int(latest.get("articleCount", -1)) == int(digest.get("article_count", -2)),
            "details": {},
        }
    )
    checks.append(
        {
            "name": "manifest_subject_matches",
            "pass": str(latest.get("subject", "")) == str(digest.get("subject_line", "")),
            "details": {},
        }
    )
    checks.append(
        {
            "name": "manifest_content_hash_matches",
            "pass": str(latest.get("contentHash", "")) == str(digest.get("content_hash", "")),
            "details": {},
        }
    )

    issue_html_path = issues_dir / f"{digest_date}.html"
    checks.append(
        {
            "name": "issue_html_exists_for_digest_date",
            "pass": issue_html_path.exists(),
            "details": {"issue_html": str(issue_html_path)},
        }
    )

    passed = all(item["pass"] for item in checks)
    report = {"digest_date": digest_date, "pass": passed, "checks": checks}
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate digest content parity.")
    parser.add_argument("--digest-date", required=True)
    parser.add_argument("--digest-dir", default="data/digests")
    parser.add_argument("--snapshot-dir", default="data/digests/snapshots")
    parser.add_argument("--issues-dir", default="frontend/issues")
    parser.add_argument("--report", default="parity-report.json")
    args = parser.parse_args()

    report = validate_parity(
        digest_date=args.digest_date,
        digest_dir=Path(args.digest_dir),
        snapshot_dir=Path(args.snapshot_dir),
        issues_dir=Path(args.issues_dir),
        report_path=Path(args.report),
    )
    print(json.dumps(report, indent=2))
    if not report["pass"]:
        raise SystemExit("Digest parity validation failed.")

"""Source-of-truth tests: send compiles existing JSON; archive prefers sent snapshots."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret")

from execution.build_digest_markdown import build_digest_markdown
from execution.build_web_archive import select_archive_issue_files

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_DIGEST_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily_digest.yml"
REBUILD_MARKDOWN_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "rebuild_digest_markdown.yml"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _canonical_payload(digest_date: str, article_count: int, source: str = "canonical") -> dict:
    stories = [
        {
            "title": f"Story {i}",
            "url": f"https://example.com/{digest_date}/{i}",
            "source": "Example",
            "summary": "Summary text for the story.",
            "opinion": "Why it matters.",
            "topic": "Models",
            "category": "Model Releases & Capabilities",
        }
        for i in range(article_count)
    ]
    return {
        "digest_date": digest_date,
        "subject_line": f"ISSUE · {article_count} STORIES",
        "intro": "Intro paragraph.",
        "article_count": article_count,
        "stories": stories,
        "sections": [
            {
                "name": "Model Releases & Capabilities",
                "articles": stories,
            }
        ],
        "tweet_headlines": [],
        "community_headlines": [],
        "build_meta": {"source": source},
        "content_hash": f"hash-{digest_date}-{article_count}",
    }


class CompileMarkdownFromCanonicalTests(unittest.TestCase):
    def test_compiles_existing_json_without_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp) / "digests"
            payload = _canonical_payload("2026-09-22", 16)
            _write_json(digest_dir / "2026-09-22.json", payload)
            with patch.dict("os.environ", {"DIGEST_MARKDOWN_DIR": str(digest_dir)}):
                path, count = build_digest_markdown(digest_date="2026-09-22")
            self.assertEqual(count, 16)
            self.assertEqual(path, digest_dir / "2026-09-22.md")
            self.assertTrue(path.exists())
            self.assertIn("16 STORIES", path.read_text(encoding="utf-8"))
            on_disk = json.loads((digest_dir / "2026-09-22.json").read_text(encoding="utf-8"))
            self.assertEqual(on_disk["article_count"], 16)
            self.assertEqual(on_disk["content_hash"], payload["content_hash"])

    def test_missing_json_fails_without_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp) / "digests"
            digest_dir.mkdir()
            with patch.dict("os.environ", {"DIGEST_MARKDOWN_DIR": str(digest_dir)}):
                with self.assertRaises(SystemExit) as ctx:
                    build_digest_markdown(digest_date="2026-09-22")
            self.assertIn("missing", str(ctx.exception).lower())
            self.assertIn("--rebuild", str(ctx.exception))

    def test_use_sent_without_rebuild_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp) / "digests"
            digest_dir.mkdir()
            with patch.dict("os.environ", {"DIGEST_MARKDOWN_DIR": str(digest_dir)}):
                with self.assertRaises(SystemExit) as ctx:
                    build_digest_markdown(digest_date="2026-09-22", use_sent=True)
            self.assertIn("--rebuild", str(ctx.exception))

    def test_rebuild_writes_payload_from_storage(self) -> None:
        rebuilt = _canonical_payload("2026-09-22", 12, source="rebuild")
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp) / "digests"
            digest_dir.mkdir()
            with patch.dict("os.environ", {"DIGEST_MARKDOWN_DIR": str(digest_dir)}):
                with patch(
                    "execution.build_digest_markdown.build_digest_payload",
                    return_value=rebuilt,
                ) as mocked_build:
                    path, count = build_digest_markdown(
                        digest_date="2026-09-22",
                        rebuild=True,
                    )
            mocked_build.assert_called_once()
            self.assertEqual(count, 12)
            written = json.loads((digest_dir / "2026-09-22.json").read_text(encoding="utf-8"))
            self.assertEqual(written["article_count"], 12)
            self.assertTrue(path.exists())


class ArchivePrefersSentSnapshotTests(unittest.TestCase):
    def test_sent_snapshot_wins_when_both_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp) / "digests"
            snapshot_dir = archive_dir / "snapshots"
            _write_json(archive_dir / "2026-09-22.json", _canonical_payload("2026-09-22", 16))
            _write_json(
                snapshot_dir / "2026-09-22.sent.json",
                _canonical_payload("2026-09-22", 12, source="sent_snapshot"),
            )
            files = select_archive_issue_files(archive_dir, snapshot_dir)
            self.assertEqual(files, [snapshot_dir / "2026-09-22.sent.json"])

    def test_canonical_used_when_no_sent_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp) / "digests"
            snapshot_dir = archive_dir / "snapshots"
            snapshot_dir.mkdir(parents=True)
            _write_json(archive_dir / "2026-09-21.json", _canonical_payload("2026-09-21", 10))
            files = select_archive_issue_files(archive_dir, snapshot_dir)
            self.assertEqual(files, [archive_dir / "2026-09-21.json"])

    def test_snapshot_only_date_is_included(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp) / "digests"
            snapshot_dir = archive_dir / "snapshots"
            archive_dir.mkdir()
            _write_json(
                snapshot_dir / "2026-04-21.sent.json",
                _canonical_payload("2026-04-21", 4, source="sent_snapshot"),
            )
            files = select_archive_issue_files(archive_dir, snapshot_dir)
            self.assertEqual(files, [snapshot_dir / "2026-04-21.sent.json"])

    def test_mixed_dates_prefer_sent_per_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp) / "digests"
            snapshot_dir = archive_dir / "snapshots"
            _write_json(archive_dir / "2026-09-21.json", _canonical_payload("2026-09-21", 10))
            _write_json(archive_dir / "2026-09-22.json", _canonical_payload("2026-09-22", 16))
            _write_json(
                snapshot_dir / "2026-09-22.sent.json",
                _canonical_payload("2026-09-22", 12, source="sent_snapshot"),
            )
            files = select_archive_issue_files(archive_dir, snapshot_dir)
            self.assertEqual(
                files,
                [
                    archive_dir / "2026-09-21.json",
                    snapshot_dir / "2026-09-22.sent.json",
                ],
            )


class WorkflowSourceOfTruthTests(unittest.TestCase):
    def test_daily_digest_compiles_json_without_rebuild(self) -> None:
        text = DAILY_DIGEST_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            'python execution/build_digest_markdown.py --digest-date "$(date -u +%F)"',
            text,
        )
        self.assertNotIn("build_digest_markdown.py --rebuild", text)

    def test_rebuild_workflow_passes_rebuild_flag(self) -> None:
        text = REBUILD_MARKDOWN_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("--rebuild", text)


if __name__ == "__main__":
    unittest.main()

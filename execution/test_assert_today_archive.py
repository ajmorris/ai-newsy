"""Tests for today's Vercel archive publish guard."""

import json
import tempfile
import unittest
from pathlib import Path

from execution.assert_today_archive import assert_today_archive_ready


def _write_ready_tree(root: Path, digest_date: str) -> None:
    digest_dir = root / "data" / "digests"
    issues_dir = root / "frontend" / "issues"
    digest_dir.mkdir(parents=True)
    issues_dir.mkdir(parents=True)
    (digest_dir / f"{digest_date}.json").write_text(
        json.dumps(
            {
                "digest_date": digest_date,
                "intro": "Hello from the digest.",
                "stories": [{"id": 1, "title": "Story", "opinion": "It matters."}],
            }
        ),
        encoding="utf-8",
    )
    (issues_dir / "index.json").write_text(
        json.dumps(
            {
                "latestIssue": {
                    "slug": digest_date,
                    "digestDate": digest_date,
                }
            }
        ),
        encoding="utf-8",
    )
    (issues_dir / f"{digest_date}.html").write_text("<html></html>", encoding="utf-8")


class AssertTodayArchiveTests(unittest.TestCase):
    def test_ready_tree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digest_date = "2026-09-02"
            _write_ready_tree(root, digest_date)
            result = assert_today_archive_ready(
                digest_dir=root / "data" / "digests",
                issues_dir=root / "frontend" / "issues",
                digest_date=digest_date,
            )
            self.assertEqual(result["digest_date"], digest_date)
            self.assertEqual(result["slug"], digest_date)

    def test_stale_manifest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ready_tree(root, "2026-09-01")
            (root / "data" / "digests" / "2026-09-02.json").write_text(
                json.dumps(
                    {
                        "digest_date": "2026-09-02",
                        "intro": "Today",
                        "stories": [{"id": 1, "opinion": "Yes"}],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit):
                assert_today_archive_ready(
                    digest_dir=root / "data" / "digests",
                    issues_dir=root / "frontend" / "issues",
                    digest_date="2026-09-02",
                )

    def test_missing_opinion_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ready_tree(root, "2026-09-02")
            (root / "data" / "digests" / "2026-09-02.json").write_text(
                json.dumps(
                    {
                        "digest_date": "2026-09-02",
                        "intro": "Today",
                        "stories": [{"id": 1, "opinion": ""}],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit):
                assert_today_archive_ready(
                    digest_dir=root / "data" / "digests",
                    issues_dir=root / "frontend" / "issues",
                    digest_date="2026-09-02",
                )

    def test_json_only_staged_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digest_date = "2026-09-02"
            _write_ready_tree(root, digest_date)
            with self.assertRaises(SystemExit):
                assert_today_archive_ready(
                    digest_dir=root / "data" / "digests",
                    issues_dir=root / "frontend" / "issues",
                    digest_date=digest_date,
                    require_staged=True,
                    staged_names=[f"data/digests/{digest_date}.json"],
                )


if __name__ == "__main__":
    unittest.main()

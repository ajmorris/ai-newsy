"""Tests for digest opinion healing, validation, and section grouping."""

import unittest

from execution.digest_payload import (
    assert_digest_stories_have_opinions,
    group_stories_into_sections,
    heal_digest_story_opinions,
    refresh_digest_payload_after_story_edit,
)


class HealDigestStoryOpinionsTests(unittest.TestCase):
    def test_heal_fills_empty_opinion(self) -> None:
        stories = [
            {
                "title": "T",
                "summary": "A" * 40,
                "opinion": "",
                "category": "Business, Deals & Funding",
            }
        ]
        heal_digest_story_opinions(
            stories,
            derive_fn=lambda title, summary, model: "Healed takeaway for readers.",
        )
        self.assertTrue(stories[0]["opinion"].strip())

    def test_assert_passes_when_all_have_opinion(self) -> None:
        stories = [{"opinion": "x", "summary": "s"}]
        assert_digest_stories_have_opinions(stories)

    def test_assert_fails_when_opinion_missing(self) -> None:
        stories = [{"id": 1, "opinion": "", "summary": "s"}]
        with self.assertRaises(SystemExit) as ctx:
            assert_digest_stories_have_opinions(stories)
        self.assertIn("Digest invariant failed", str(ctx.exception))


class GroupStoriesTests(unittest.TestCase):
    def test_groups_by_category(self) -> None:
        stories = [
            {"title": "a", "category": "B", "summary": "s", "opinion": "o"},
            {"title": "b", "category": "A", "summary": "s", "opinion": "o"},
        ]
        sections = group_stories_into_sections(stories)
        names = [s["name"] for s in sections]
        self.assertEqual(names, ["A", "B"])


class RefreshDigestPayloadTests(unittest.TestCase):
    def test_refresh_updates_hash_and_sections(self) -> None:
        stories = [
            {
                "title": "t",
                "summary": "s",
                "opinion": "o",
                "category": "Cat",
            }
        ]
        payload = {
            "digest_date": "2026-05-05",
            "issue_id": "20260505",
            "subject_line": "old",
            "intro": "i",
            "stories": [],
            "sections": [],
            "tweet_headlines": [],
            "community_headlines": [],
            "content_hash": "oldhash",
        }
        refresh_digest_payload_after_story_edit(payload, stories)
        self.assertEqual(len(payload["sections"]), 1)
        self.assertEqual(payload["article_count"], 1)
        self.assertNotEqual(payload["content_hash"], "oldhash")


class InspectCanonicalDigestTests(unittest.TestCase):
    def test_missing_file_needs_generate(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from execution.digest_payload import inspect_canonical_digest

        with TemporaryDirectory() as tmp:
            status = inspect_canonical_digest("2026-08-31", output_dir=Path(tmp))
        self.assertFalse(status["ok"])
        self.assertTrue(status["needs_generate"])
        self.assertEqual(status["reason"], "missing")

    def test_complete_payload_is_ok(self) -> None:
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from execution.digest_payload import inspect_canonical_digest

        payload = {
            "intro": "Today's thread is models versus tools.",
            "stories": [{"id": 1, "title": "T", "opinion": "It matters."}],
        }
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-08-31.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            status = inspect_canonical_digest("2026-08-31", output_dir=Path(tmp))
        self.assertTrue(status["ok"])
        self.assertFalse(status["needs_generate"])
        self.assertEqual(status["reason"], "ok")
        self.assertEqual(status["story_count"], 1)

    def test_missing_intro_needs_generate(self) -> None:
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from execution.digest_payload import inspect_canonical_digest

        payload = {
            "intro": "  ",
            "stories": [{"id": 1, "title": "T", "opinion": "It matters."}],
        }
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-08-31.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            status = inspect_canonical_digest("2026-08-31", output_dir=Path(tmp))
        self.assertFalse(status["ok"])
        self.assertTrue(status["needs_generate"])
        self.assertEqual(status["reason"], "missing_intro")

    def test_missing_opinions_needs_generate(self) -> None:
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from execution.digest_payload import inspect_canonical_digest

        payload = {
            "intro": "Today's thread is models versus tools.",
            "stories": [{"id": 7, "title": "T", "opinion": ""}],
        }
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-08-31.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            status = inspect_canonical_digest("2026-08-31", output_dir=Path(tmp))
        self.assertFalse(status["ok"])
        self.assertTrue(status["needs_generate"])
        self.assertEqual(status["reason"], "missing_opinions")
        self.assertEqual(status["missing_opinions"], [7])

    def test_committed_aug_27_digest_is_ok(self) -> None:
        from execution.digest_payload import inspect_canonical_digest

        status = inspect_canonical_digest("2026-08-27")
        self.assertTrue(status["ok"], status)
        self.assertFalse(status["needs_generate"])
        self.assertGreater(status["story_count"], 0)

    def test_inspect_cli_writes_github_output(self) -> None:
        import subprocess
        import sys
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "github_output"
            result = subprocess.run(
                [
                    sys.executable,
                    "execution/digest_payload.py",
                    "--inspect",
                    "--digest-date",
                    "2026-08-31",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env={
                    **__import__("os").environ,
                    "GITHUB_OUTPUT": str(output_path),
                    "DIGEST_MARKDOWN_DIR": tmp,
                },
                capture_output=True,
                text=True,
                check=True,
            )
            written = output_path.read_text(encoding="utf-8")
        self.assertIn("needs_generate=true", written)
        self.assertIn("payload_ok=false", written)
        self.assertIn("reason=missing", written)
        self.assertIn("needs_generate=True", result.stdout)


if __name__ == "__main__":
    unittest.main()

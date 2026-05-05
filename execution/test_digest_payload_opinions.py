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


if __name__ == "__main__":
    unittest.main()

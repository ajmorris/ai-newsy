"""Same-event articles with different URLs become one newsletter story."""

from __future__ import annotations

import json
import unittest

from execution.story_clusters import (
    apply_groups,
    cluster_with_model,
    clustering_precision,
)

WSJ = {
    "id": 1,
    "source": "WSJ",
    "title": "OpenAI agrees to buy a compute partner",
    "summary": "WSJ reports the deal is worth $4 billion.",
    "opinion": "Watch the price.",
    "url": "https://wsj.example/openai-deal",
    "published_at": "2026-03-01T10:00:00+00:00",
}
NYT = {
    "id": 2,
    "source": "NYT",
    "title": "OpenAI's compute purchase, according to people familiar",
    "summary": "NYT puts the purchase at $5 billion.",
    "opinion": "The number is disputed.",
    "url": "https://nyt.example/openai-deal",
    "published_at": "2026-03-01T12:00:00+00:00",
}
BREACH = {
    "id": 3,
    "source": "The Verge",
    "title": "OpenAI investigates a security breach",
    "summary": "A breach exposed internal tools. This is not the compute purchase.",
    "opinion": "Separate incident.",
    "url": "https://verge.example/breach",
    "published_at": "2026-03-01T09:00:00+00:00",
}
PRICING = {
    "id": 4,
    "source": "TechCrunch",
    "title": "OpenAI changes API pricing",
    "summary": "API prices fell for the small model.",
    "opinion": "Pricing is a different story.",
    "url": "https://tc.example/pricing",
    "published_at": "2026-03-01T08:00:00+00:00",
}


def _response() -> str:
    return json.dumps(
        {
            "groups": [
                {
                    "ids": ["1", "2"],
                    "reason": "Both describe the compute purchase.",
                    "headline": "OpenAI's compute purchase",
                    "summary": "WSJ reports the deal is worth $4 billion. NYT puts the purchase at $5 billion.",
                    "opinion": "The outlets do not agree on the price.",
                    "conflicts": ["WSJ reports $4 billion; NYT puts it at $5 billion."],
                    "update": False,
                },
                {
                    "ids": ["3"],
                    "reason": "Breach is a different event.",
                    "summary": "A breach exposed internal tools.",
                    "opinion": "Separate incident.",
                },
                {
                    "ids": ["4"],
                    "reason": "Pricing is a different event.",
                    "summary": "API prices fell for the small model.",
                    "opinion": "Pricing is a different story.",
                },
            ]
        }
    )


class StoryClusterTests(unittest.TestCase):
    def test_same_event_from_two_outlets_uses_one_slot(self) -> None:
        stories, log = apply_groups([WSJ, NYT, BREACH, PRICING], _response())
        self.assertEqual(len(stories), 3)
        merged = next(story for story in stories if story["id"] == 1)
        self.assertEqual(merged["url"], WSJ["url"])
        self.assertEqual(merged["cluster"]["badge_count"], 2)
        self.assertEqual(len(merged["cluster"]["sources"]), 2)
        self.assertIn("WSJ reports $4 billion", merged["opinion"])
        self.assertIn("NYT puts it at $5 billion", merged["opinion"])
        self.assertNotIn("cluster", next(story for story in stories if story["id"] == 3))
        self.assertEqual(merged["cluster"]["sources"][0]["source"], "WSJ")
        self.assertEqual(merged["cluster"]["sources"][1]["source"], "NYT")
        precision = clustering_precision(log, [("1", "2")])
        self.assertGreaterEqual(precision, 0.9)

    def test_lead_is_earliest_even_when_the_model_lists_it_second(self) -> None:
        response = json.dumps(
            {
                "groups": [
                    {
                        "ids": ["2", "1"],
                        "reason": "Same purchase.",
                        "summary": "WSJ reports the deal is worth $4 billion.",
                        "opinion": "Same event.",
                    }
                ]
            }
        )
        stories, _log = apply_groups([NYT, WSJ], response)
        self.assertEqual(stories[0]["url"], WSJ["url"])
        self.assertEqual(stories[0]["cluster"]["sources"][0]["id"], 1)
        self.assertEqual(stories[0]["cluster"]["sources"][1]["source"], "NYT")

    def test_model_failure_keeps_every_article(self) -> None:
        stories, log = cluster_with_model([WSJ, NYT], generate=lambda _prompt: "not json")
        self.assertEqual(len(stories), 2)
        self.assertIn("skipped", log[0]["reason"])

    def test_repeat_of_yesterdays_story_is_an_update(self) -> None:
        response = json.dumps(
            {
                "groups": [
                    {
                        "ids": ["1", "yesterday:0"],
                        "reason": "This purchase was already in yesterday's issue.",
                        "summary": "WSJ reports the deal is worth $4 billion.",
                        "opinion": "Still the same deal.",
                    }
                ]
            }
        )
        stories, log = apply_groups([WSJ], response)
        self.assertEqual(len(stories), 1)
        self.assertTrue(stories[0]["cluster"]["is_update"])
        self.assertTrue(log[0]["is_update"])

    def test_prompt_sends_title_and_summary_not_urls_as_the_match(self) -> None:
        from execution.story_clusters import build_cluster_prompt

        prompt = build_cluster_prompt([WSJ, BREACH], [])
        self.assertIn("OpenAI agrees to buy a compute partner", prompt)
        self.assertIn("A breach exposed internal tools", prompt)
        self.assertIn("Ignore whether the tone", prompt)


class DigestSlotTests(unittest.TestCase):
    def test_same_event_collapses_before_the_story_cap(self) -> None:
        from unittest.mock import patch

        from execution.digest_payload import DigestBuildOptions, build_digest_payload

        other = {
            "id": 5,
            "source": "Bloomberg",
            "title": "A chip export rule takes effect",
            "summary": "New export rules cover advanced chips.",
            "opinion": "Policy, not the purchase.",
            "url": "https://bbg.example/chips",
            "published_at": "2026-03-01T07:00:00+00:00",
            "topic": "Industry",
        }
        rows = [dict(WSJ), dict(NYT), dict(other)]

        def fake_generate(prompt: str, **_kwargs: object) -> str:
            if "group newsletter" in prompt:
                return _response_for_cap()
            return "Intro."

        with patch("execution.digest_payload.get_unsent_articles_for_digest", return_value=rows), patch(
            "execution.digest_payload.get_digest_extra",
            return_value={"payload": {"text": "Stored intro."}},
        ), patch("execution.digest_payload.load_sent_snapshot", return_value=None), patch(
            "execution.ai_client.generate_text_with_fallback",
            side_effect=fake_generate,
        ):
            payload = build_digest_payload(DigestBuildOptions(digest_date="2026-03-02", max_stories=2))

        self.assertEqual(payload["article_count"], 2)
        titles = [story["title"] for story in payload["stories"]]
        self.assertIn("OpenAI's compute purchase", titles)
        self.assertTrue(any(story.get("cluster", {}).get("badge_count") == 2 for story in payload["stories"]))
        self.assertTrue(any("chip export" in story["title"] for story in payload["stories"]))
        self.assertTrue(any(story.get("cluster") for story in payload["stories"]))
        from execution.digest_payload import _content_hash

        without = dict(payload)
        without["stories"] = [{key: value for key, value in story.items() if key != "cluster"} for story in payload["stories"]]
        self.assertEqual(payload["content_hash"], _content_hash(without))


def _response_for_cap() -> str:
    return json.dumps(
        {
            "groups": [
                {
                    "ids": ["1", "2"],
                    "reason": "Both describe the compute purchase.",
                    "headline": "OpenAI's compute purchase",
                    "summary": "WSJ reports the deal is worth $4 billion. NYT puts the purchase at $5 billion.",
                    "opinion": "The outlets do not agree on the price.",
                    "conflicts": ["WSJ reports $4 billion; NYT puts it at $5 billion."],
                },
                {
                    "ids": ["5"],
                    "reason": "Export rules are a different event.",
                    "summary": "New export rules cover advanced chips.",
                    "opinion": "Policy, not the purchase.",
                },
            ]
        }
    )


if __name__ == "__main__":
    unittest.main()

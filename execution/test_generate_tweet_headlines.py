import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
import types
import sys

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret")

if "notion_client" not in sys.modules:
    notion_client_stub = types.ModuleType("notion_client")
    notion_client_stub.Client = object
    notion_client_stub.__version__ = "test"
    sys.modules["notion_client"] = notion_client_stub

from execution.generate_tweet_headlines import (
    _build_generation_prompt,
    _lookback_start,
    curate_headlines,
    generate_headlines_for_tweets,
    parse_headline_response,
)


class TweetHeadlineCurationTests(unittest.TestCase):
    def test_lookback_start_uses_configured_hours(self) -> None:
        now = datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc)
        since = _lookback_start(hours=24, now=now)
        self.assertEqual(since.isoformat(), "2026-04-18T12:00:00+00:00")

    def test_dedupes_same_url_with_tracking_params(self) -> None:
        headlines = [
            {
                "tweet_id": "a",
                "headline": "Claude shares a __new design workflow__ for agent UX",
                "url": "https://x.com/acme/status/123?utm_source=x",
                "source_text": "Detailed design workflow with examples and benchmarks",
                "created_time": "2026-04-19T10:00:00+00:00",
            },
            {
                "tweet_id": "b",
                "headline": "Another take on __new design workflow__ for agent UX",
                "url": "https://twitter.com/acme/status/123",
                "source_text": "Same thread repeated with light rewording",
                "created_time": "2026-04-19T09:00:00+00:00",
            },
        ]

        curated = curate_headlines(
            headlines,
            max_headlines=12,
            min_learning_score=0,
            theme_similarity_threshold=0.38,
            max_per_theme=2,
            distinctness_threshold=0.45,
        )
        self.assertEqual(len(curated), 1)
        self.assertEqual(curated[0]["tweet_id"], "a")

    def test_collapses_repeated_theme_to_one_when_not_distinct(self) -> None:
        headlines = [
            {
                "tweet_id": "a",
                "headline": "Claude design tips for __agent onboarding screens__",
                "url": "https://twitter.com/a/1",
                "source_text": "UI tips for onboarding screens and interaction design",
                "created_time": "2026-04-19T10:00:00+00:00",
            },
            {
                "tweet_id": "b",
                "headline": "More Claude design advice on __agent onboarding screens__",
                "url": "https://twitter.com/b/2",
                "source_text": "More UI tips for onboarding screens and interaction design",
                "created_time": "2026-04-19T09:00:00+00:00",
            },
        ]
        curated = curate_headlines(
            headlines,
            max_headlines=12,
            min_learning_score=0,
            theme_similarity_threshold=0.20,
            max_per_theme=2,
            distinctness_threshold=0.55,
        )
        self.assertEqual(len(curated), 1)

    def test_keeps_multiple_when_same_theme_has_distinct_takeaways(self) -> None:
        headlines = [
            {
                "tweet_id": "a",
                "headline": "Claude design post explains __navigation hierarchy tests__",
                "url": "https://twitter.com/a/1",
                "source_text": "A/B test results on navigation hierarchy and retention",
                "created_time": "2026-04-19T10:00:00+00:00",
            },
            {
                "tweet_id": "b",
                "headline": "Claude design post shares __latency tradeoff benchmarks__",
                "url": "https://twitter.com/b/2",
                "source_text": "Latency tradeoffs and benchmark table for async rendering",
                "created_time": "2026-04-19T09:00:00+00:00",
            },
        ]
        curated = curate_headlines(
            headlines,
            max_headlines=12,
            min_learning_score=0,
            theme_similarity_threshold=0.20,
            max_per_theme=2,
            distinctness_threshold=0.45,
        )
        self.assertEqual(len(curated), 2)

    def test_filters_low_learning_value_items(self) -> None:
        headlines = [
            {
                "tweet_id": "a",
                "headline": "GM just dropped a __new post__",
                "url": "https://twitter.com/a/1",
                "source_text": "Good morning check this out",
                "created_time": "2026-04-19T10:00:00+00:00",
            },
            {
                "tweet_id": "b",
                "headline": "Practical guide to __latency optimization__ in agent loops",
                "url": "https://twitter.com/b/2",
                "source_text": "Step-by-step guide with benchmark numbers and failure analysis",
                "created_time": "2026-04-19T09:00:00+00:00",
            },
        ]
        curated = curate_headlines(
            headlines,
            max_headlines=12,
            min_learning_score=2,
            theme_similarity_threshold=0.20,
            max_per_theme=2,
            distinctness_threshold=0.45,
        )
        self.assertEqual(len(curated), 1)
        self.assertEqual(curated[0]["tweet_id"], "b")


class TweetHeadlineParseTests(unittest.TestCase):
    def _tweets(self):
        return [
            {
                "tweet_id": "11111111-2222-3333-4444-555555555555",
                "author": "Ada",
                "text": "A long note about agent evals and a benchmark table",
                "url": "https://x.com/ada/status/10",
                "created_time": "2026-10-05T01:00:00+00:00",
            },
            {
                "tweet_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "author": "Bea",
                "text": "Another note about prompt design tradeoffs",
                "url": "https://x.com/bea/status/11?utm_source=x",
                "created_time": "2026-10-05T02:00:00+00:00",
            },
        ]

    def test_parses_short_ids_fences_and_bullets(self) -> None:
        text = """```text
* 1|Ada published an __agent eval benchmark__
2: Bea shares __prompt design tradeoffs__
```"""
        parsed = parse_headline_response(text, self._tweets())
        self.assertEqual([item["tweet_id"] for item in parsed], [
            "11111111-2222-3333-4444-555555555555",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        ])
        self.assertIn("__agent eval benchmark__", parsed[0]["headline"])

    def test_parses_notion_id_without_dashes_and_url(self) -> None:
        text = "\n".join(
            [
                "11111111222233334444555555555555|Ada published an __agent eval benchmark__",
                "https://twitter.com/bea/status/11|Bea shares __prompt design tradeoffs__",
            ]
        )
        parsed = parse_headline_response(text, self._tweets())
        self.assertEqual(len(parsed), 2)

    def test_prompt_uses_short_ids(self) -> None:
        prompt = _build_generation_prompt("skill", self._tweets())
        self.assertIn("ID: 1", prompt)
        self.assertNotIn("11111111-2222-3333-4444-555555555555", prompt)
        self.assertIn("override every earlier instruction", prompt)

    def test_retries_unparsed_batch_then_keeps_matches(self) -> None:
        tweets = self._tweets()
        with patch.dict(os.environ, {"TWEET_HEADLINE_BATCH_SIZE": "20"}, clear=False):
            with patch(
                "execution.generate_tweet_headlines.generate_text_with_fallback",
                side_effect=[
                    "* A headline with __no id__",
                    "1|Ada published an __agent eval benchmark__",
                ],
            ) as generate:
                parsed = generate_headlines_for_tweets(tweets, skill_prompt="skill")
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(len(parsed), 1)
        second_prompt = generate.call_args_list[1].kwargs["prompt"]
        self.assertNotIn("skill", second_prompt)
        self.assertIn("ID: 1", second_prompt)

    def test_raises_when_every_batch_is_unparsed(self) -> None:
        with patch(
            "execution.generate_tweet_headlines.generate_text_with_fallback",
            return_value="Here are some thoughts, but no lines.",
        ):
            with self.assertRaises(RuntimeError):
                generate_headlines_for_tweets(self._tweets(), skill_prompt="skill")


if __name__ == "__main__":
    unittest.main()

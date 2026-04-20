import unittest
from datetime import datetime, timezone
import types
import sys

if "notion_client" not in sys.modules:
    notion_client_stub = types.ModuleType("notion_client")
    notion_client_stub.Client = object
    notion_client_stub.__version__ = "test"
    sys.modules["notion_client"] = notion_client_stub

from execution.generate_tweet_headlines import _lookback_start, curate_headlines


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


if __name__ == "__main__":
    unittest.main()

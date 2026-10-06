import unittest
from unittest.mock import patch

from execution.generate_community_headlines import generate_headlines_for_items


def _sample_items(count: int) -> list:
    return [
        {
            "item_id": str(index),
            "author": "author",
            "url": f"https://news.ycombinator.com/item?id={index}",
            "text": f"post text {index}",
            "created_time": "2026-04-19T10:00:00+00:00",
            "source_type": "hn",
            "source_label": "Hacker News",
            "subreddit": None,
        }
        for index in range(count)
    ]


class CommunityHeadlineBatchTests(unittest.TestCase):
    def test_two_batches_become_two_llm_calls(self) -> None:
        items = _sample_items(21)

        def fake_generate(prompt: str, **kwargs):
            self.assertEqual(kwargs.get("timeout_seconds"), 120)
            lines = [
                f"{item['item_id']}|A __headline__"
                for item in items
                if f"ITEM_ID: {item['item_id']}" in prompt
            ]
            return "\n".join(lines)

        with patch(
            "execution.generate_community_headlines.generate_text_with_fallback",
            side_effect=fake_generate,
        ) as generate:
            headlines = generate_headlines_for_items(
                items,
                "skill",
                batch_size=20,
                timeout_seconds=120,
            )

        self.assertEqual(generate.call_count, 2)
        self.assertEqual(len(headlines), 21)

    def test_timeout_on_first_batch_keeps_second_batch(self) -> None:
        items = _sample_items(2)

        def fake_generate(prompt: str, **kwargs):
            if "ITEM_ID: 0" in prompt:
                raise RuntimeError("Claude CLI timed out after 120s")
            return "1|Second __headline__"

        with patch(
            "execution.generate_community_headlines.generate_text_with_fallback",
            side_effect=fake_generate,
        ) as generate:
            headlines = generate_headlines_for_items(
                items,
                "skill",
                batch_size=1,
                timeout_seconds=120,
            )

        self.assertEqual(generate.call_count, 3)
        self.assertEqual([item["item_id"] for item in headlines], ["1"])

    def test_all_batches_failing_raises(self) -> None:
        items = _sample_items(2)
        with patch(
            "execution.generate_community_headlines.generate_text_with_fallback",
            side_effect=RuntimeError("Claude CLI timed out after 120s"),
        ) as generate:
            with self.assertRaisesRegex(RuntimeError, "All community headline batches failed"):
                generate_headlines_for_items(
                    items,
                    "skill",
                    batch_size=1,
                    timeout_seconds=120,
                )

        self.assertEqual(generate.call_count, 4)


if __name__ == "__main__":
    unittest.main()

"""Developer-section routing on a labeled sample of past-style items."""

from __future__ import annotations

import unittest

from execution.section_routing import route_item, split_main_and_dev

LABELED = [
    {"title": "Claude Code changelog", "url": "https://github.com/anthropics/claude-code/releases", "expect": "dev"},
    {"title": "Cursor 0.45", "url": "https://github.com/getcursor/cursor/releases/tag/v0.45.0", "expect": "dev"},
    {"title": "New package on PyPI", "url": "https://pypi.org/project/ai-newsy/", "expect": "dev"},
    {"title": "npm release", "url": "https://www.npmjs.com/package/mjml", "expect": "dev"},
    {"title": "GitLab CI template", "url": "https://gitlab.com/gitlab-org/cli/-/releases", "expect": "dev"},
    {"title": "Space demo", "url": "https://huggingface.co/spaces/demo/app", "expect": "dev"},
    {"title": "v1.2 of the local runner", "url": "https://example.com/blog/runner", "expect": "dev"},
    {"title": "Project changelog for March", "url": "https://example.com/changelog", "expect": "dev"},
    {"title": "Release notes: faster indexing", "url": "https://example.com/news/indexing", "expect": "dev"},
    {"title": "Breaking change in the API client", "url": "https://github.com/org/client/releases", "expect": "dev"},
    {"title": "A gotcha in the new installer", "url": "https://github.com/org/installer", "expect": "dev"},
    {"title": "WSJ: OpenAI signs a cloud deal", "url": "https://www.wsj.com/tech/openai-cloud", "expect": "main"},
    {"title": "NYT on school homework", "url": "https://www.nytimes.com/ai-homework", "expect": "main"},
    {"title": "Hugging Face blog on a paper", "url": "https://huggingface.co/blog/paper", "expect": "main"},
    {"title": "Model lab raises a round", "url": "https://techcrunch.com/fundraise", "expect": "main"},
    {"title": "Researchers measure energy use", "url": "https://www.nature.com/articles/energy", "expect": "main"},
    {"title": "Policy draft on training data", "url": "https://www.whitehouse.gov/ai-policy", "expect": "main"},
    {"title": "OpenAI releases open weights", "url": "https://github.com/openai/weights", "expect": "main"},
    {"title": "Library patch", "url": "https://github.com/org/lib/releases/v2.0.0", "expect": "main", "promote_to_main": True},
    {"title": "Editor plugin", "url": "https://github.com/org/plugin", "expect": "main", "significance_score": 0.9},
]


class SectionRoutingTests(unittest.TestCase):
    def test_labeled_sample_is_at_least_95_percent(self) -> None:
        correct = 0
        for item in LABELED:
            expected = item["expect"]
            routed = route_item(item)
            if routed == expected:
                correct += 1
        accuracy = correct / len(LABELED)
        self.assertGreaterEqual(accuracy, 0.95, f"routing accuracy {accuracy:.2%} on {len(LABELED)} items")
        self.assertGreaterEqual(len(LABELED), 20)

    def test_changelog_entries_collapse_to_one_bullet(self) -> None:
        items = [
            {
                "title": "Changelog: fix prompts",
                "url": "https://github.com/acme/tool/blob/main/CHANGELOG.md",
                "published_at": "2026-01-02",
            },
            {
                "title": "Changelog: add hooks",
                "url": "https://github.com/acme/tool/releases/tag/v1.2.0",
                "published_at": "2026-01-03",
            },
            {
                "title": "City council bans a chatbot",
                "url": "https://example.com/city",
            },
        ]
        main_items, dev_items = split_main_and_dev(items)
        self.assertEqual(len(main_items), 1)
        self.assertEqual(len(dev_items), 1)
        self.assertIn("Notable changes", dev_items[0]["headline"])
        self.assertNotIn("summary", dev_items[0])

    def test_llm_tiebreaker_can_route_a_tool_the_rules_missed(self) -> None:
        item = {"title": "A quiet helper for pull requests", "url": "https://example.com/helper"}
        self.assertEqual(route_item(item), "main")
        self.assertEqual(route_item(item, judge=lambda _item: "developer tooling"), "dev")
        self.assertEqual(route_item(item, judge=lambda _item: "news"), "main")

    def test_breaking_changes_rank_ahead_of_new_tools(self) -> None:
        items = [
            {"title": "New tool for logs", "url": "https://github.com/acme/logs", "published_at": "2026-02-02"},
            {"title": "Breaking change in auth", "url": "https://github.com/acme/auth/releases", "published_at": "2026-01-01"},
        ]
        _main, dev_items = split_main_and_dev(items)
        self.assertEqual(dev_items[0]["tag"], "Breaking change")
        self.assertLessEqual(len(dev_items), 8)


if __name__ == "__main__":
    unittest.main()

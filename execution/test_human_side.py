"""Human-side routing: labeled themes, a 2–4 item section, skip when thin."""

from __future__ import annotations

import unittest

from execution.feed_config import FEED_CATEGORIES, get_merged_feeds
from execution.human_side import classify_item, select_human_items

LABELED = [
    ("OpenAI lays off 200 employees after a reorg", "workforce", "workforce"),
    ("A hiring freeze hits the research staff", "The company paused hiring.", "workforce"),
    ("Workers return to office three days a week", "A new policy starts Monday.", "workforce"),
    ("City council debates worker surveillance cameras", "Cameras watch the warehouse floor.", "ethics"),
    ("An ethics board reviews the hiring model", "Fairness was the open question.", "ethics"),
    ("Algorithmic bias showed up in the loan tool", "Appeals rose after launch.", "ethics"),
    ("The data center's water use spiked", "Energy demand followed the new cluster.", "environment"),
    ("Carbon footprint of the training run", "Emissions were higher than forecast.", "environment"),
    ("An upskilling program for support teams", "Job training starts next month.", "skills"),
    ("AI literacy sessions for people managers", "Workforce training is optional today.", "skills"),
    ("Burnout is climbing on the platform team", "Remote work did not fix the load.", "culture"),
    ("Workplace culture shifted after the merger", "People managers are the bottleneck.", "culture"),
    ("The change management office owns the rollout plan", "Organizational change is the work.", "change management"),
    ("A change program replaces the old intake process", "The rollout plan names an owner.", "change management"),
    ("OpenAI ships a faster model", "Benchmarks improved. No staffing news.", ""),
    ("GitHub releases version 2.4 of the CLI", "Changelog lists bug fixes.", ""),
    ("Enterprise adoption of the chatbot grew", "Seats sold to new customers.", ""),
    ("Researchers describe a model training run", "The paper covers loss curves.", ""),
    ("Steve Jobs biography is reprinted", "A book review of a product founder.", ""),
    ("API prices fell for the small model", "A pricing change only.", ""),
]


def _story(title: str, summary: str, **extra):
    return {"id": extra.get("id", title), "title": title, "summary": summary, "url": "https://example.test/a", "source": "Example", **extra}


class HumanSideTests(unittest.TestCase):
    def test_labeled_sample_matches_the_theme(self) -> None:
        correct = 0
        for title, summary, expected in LABELED:
            got = classify_item(_story(title, summary))
            if got == expected:
                correct += 1
        self.assertGreaterEqual(correct / len(LABELED), 0.95)

    def test_section_is_omitted_when_fewer_than_two_qualify(self) -> None:
        stories = [
            _story("OpenAI lays off 200 employees", "A workforce cut."),
            _story("OpenAI ships a faster model", "Benchmarks improved."),
        ]
        self.assertEqual(select_human_items(stories), [])

    def test_section_caps_at_four_and_keeps_the_cluster(self) -> None:
        stories = [
            _story("OpenAI lays off 200 employees", "A workforce cut.", id=1, published_at="2026-03-02T10:00:00+00:00", cluster={"badge_count": 2, "sources": [{"source": "WSJ"}, {"source": "NYT"}], "is_update": False}),
            _story("Carbon footprint of the training run", "Emissions were higher.", id=2, published_at="2026-03-02T09:00:00+00:00"),
            _story("Burnout is climbing on the platform team", "Remote work did not fix the load.", id=3, published_at="2026-03-02T08:00:00+00:00"),
            _story("An upskilling program for support teams", "Job training starts next month.", id=4, published_at="2026-03-02T07:00:00+00:00"),
            _story("An ethics board reviews the hiring model", "Fairness was the open question.", id=5, published_at="2026-03-02T06:00:00+00:00"),
            _story("The change management office owns the rollout plan", "Organizational change is the work.", id=6, published_at="2026-03-02T05:00:00+00:00"),
        ]
        items = select_human_items(stories)
        self.assertGreaterEqual(len(items), 2)
        self.assertLessEqual(len(items), 4)
        lead = next(item for item in items if item["id"] == 1)
        self.assertEqual(lead["cluster"]["badge_count"], 2)
        self.assertNotIn("What this means", lead["meaning"])
        self.assertIn("people doing it", lead["meaning"])

    def test_registry_adds_at_least_ten_human_feeds(self) -> None:
        feeds = get_merged_feeds()
        human = [feed for feed in feeds if feed.get("category") == "human"]
        self.assertGreaterEqual(len(human), 10)
        self.assertTrue(all(feed.get("category") in FEED_CATEGORIES for feed in feeds))
        self.assertTrue(all(feed["primary_url"].startswith("https://") for feed in human))

    def test_tiebreaker_can_tag_what_the_rules_missed(self) -> None:
        item = _story("The office is rearranging how decisions get made", "No keyword in the title.")
        self.assertEqual(classify_item(item), "")
        self.assertEqual(classify_item(item, judge=lambda _item: "change management"), "change management")
        self.assertEqual(classify_item(item, judge=lambda _item: "sports"), "")


if __name__ == "__main__":
    unittest.main()

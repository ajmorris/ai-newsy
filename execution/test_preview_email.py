"""Local email preview covers every renderer variant and the digest payload path."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from execution.preview_email import (
    DEFAULT_FIXTURE,
    payload_from_digest,
    render_html,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MJML_INSTALLED = (REPO_ROOT / "emails" / "node_modules" / "mjml").exists()


class PreviewPayloadTests(unittest.TestCase):
    def test_date_payload_includes_quick_hit_sections(self) -> None:
        digest = {
            "intro": "Hello",
            "subject_line": "ISSUE 1",
            "sections": [
                {
                    "name": "Business",
                    "articles": [
                        {
                            "title": "A story",
                            "url": "https://example.com/story",
                            "source": "Example",
                            "summary": "Sum",
                            "opinion": "Why",
                        }
                    ],
                }
            ],
            "tweet_headlines": [{"headline": "A tweet", "url": "https://x.com/a"}],
            "community_headlines": [],
            "dev_headlines": [{"headline": "A dev note", "url": "https://example.com/dev"}],
            "human_items": [
                {"headline": "One human item", "url": "https://example.com/1", "meaning": "Care"},
                {"headline": "Two human items", "url": "https://example.com/2"},
            ],
        }

        payload = payload_from_digest(digest, "2026-10-30")

        self.assertEqual(payload["stories"][0]["headline"], "A story")
        self.assertEqual(
            [section["title"] for section in payload["quickHitSections"]],
            ["Developer and open source", "The human side"],
        )
        self.assertEqual(payload["tweetHeadlines"][0]["headline"], "A tweet")

    def test_one_human_item_does_not_open_the_section(self) -> None:
        digest = {
            "intro": "",
            "subject_line": "ISSUE 1",
            "sections": [],
            "dev_headlines": [],
            "human_items": [{"headline": "Only one", "url": "https://example.com/1"}],
        }

        payload = payload_from_digest(digest, "2026-10-30")

        self.assertEqual(payload["quickHitSections"], [])

    @unittest.skipUnless(MJML_INSTALLED, "emails dependencies are not installed")
    def test_showcase_html_includes_every_variant(self) -> None:
        payload = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
        html = render_html(payload)

        for snippet in (
            "Covered by 2 sources",
            "Also covered by",
            "Where coverage differs",
            "Update · Covered by 3 sources",
            "Covered by 4 sources",
            "No summary available.",
            "Follow the source for details.",
            "What this means for people leading change",
            "Here's what's going on in Twitter/X",
            "Here's what we're hearing from the community",
            "Developer and open source",
            "The human side",
            "4 min",
            "e8c0fbf690fb7de0c9bc31006a069c434114b13f",
        ):
            self.assertIn(snippet, html, snippet)

        self.assertRegex(html, r">\s*Update\s*<")
        self.assertNotIn("Covered by 1", html)
        self.assertIn(">Source</a>", html)
        self.assertGreaterEqual(html.lower().count("<img"), 4)
        self.assertIn("line-height:1.5", html)
        self.assertIn("line-height:1.25", html)
        self.assertNotIn("margin-top:4px", html)
        self.assertNotIn("line-height:1.65", html)

        renderer = (REPO_ROOT / "emails" / "render_email.mjs").read_text(encoding="utf-8")
        self.assertNotIn('padding="5px 0"', renderer)
        self.assertNotIn("margin-top:4px", renderer)
        self.assertNotIn('letter-spacing="2px"', renderer)


if __name__ == "__main__":
    unittest.main()

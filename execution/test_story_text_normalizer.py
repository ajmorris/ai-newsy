import unittest

from execution.build_web_archive import _render_story
from execution.story_text_normalizer import (
    extract_json_object,
    is_markdown_heavy,
    normalize_story_text,
)


class StoryTextNormalizerTests(unittest.TestCase):
    def test_extracts_json_from_fenced_block(self) -> None:
        blob = """Here is the output:
```json
{"topic":"Industry","summary":"Clean summary.","opinion":"Clean opinion.","confidence":0.9}
```"""
        parsed = extract_json_object(blob)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["summary"], "Clean summary.")

    def test_normalizes_markdown_heavy_blob(self) -> None:
        raw = """# Analysis of the Article

## Key Claims and Context

- **Core Warning**: The UK could face hacktivist attacks at scale.
- **Severity Comparison**: Impact could be nationally disruptive.
"""
        normalized = normalize_story_text(raw)
        self.assertNotIn("#", normalized)
        self.assertNotIn("**", normalized)
        self.assertTrue(normalized.startswith("Analysis of the Article"))
        self.assertFalse(is_markdown_heavy(normalized))

    def test_clean_summary_passes_through(self) -> None:
        clean = "OpenAI released an updated model with better coding reliability and lower latency."
        normalized = normalize_story_text(clean)
        self.assertEqual(normalized, clean)
        self.assertFalse(is_markdown_heavy(normalized))

    def test_archive_render_uses_sanitized_summary(self) -> None:
        story = {
            "source": "Guardian AI",
            "title": "UK could face hacktivist attacks at scale",
            "url": "https://example.com/story",
            "summary": "# Analysis of the Article\n\n## Key Claims\n\n- **Core Warning**: Something happened.",
            "opinion": "",
            "image_url": "",
        }
        html = _render_story(story)
        self.assertNotIn("## Key Claims", html)
        self.assertNotIn("**Core Warning**", html)
        self.assertIn("Analysis of the Article", html)


if __name__ == "__main__":
    unittest.main()

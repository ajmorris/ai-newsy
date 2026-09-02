"""Tests for Claude Desktop digest apply helpers."""

import json
import unittest

from execution.apply_claude_digest import _normalize_headlines
from execution.analyze_articles_single_pass import parse_strict_analysis_json


class NormalizeHeadlinesTests(unittest.TestCase):
    def test_drops_empty_and_keeps_url(self) -> None:
        rows = [
            {"headline": "  Hello  ", "url": "https://example.com"},
            {"headline": "", "url": "https://x.com/a"},
            "skip-me",
        ]
        out = _normalize_headlines(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["headline"], "Hello")
        self.assertEqual(out[0]["url"], "https://example.com")


class AnalysisRowTests(unittest.TestCase):
    def test_parse_accepts_desktop_row(self) -> None:
        row = {
            "id": 9,
            "topic": "Models",
            "summary": "A short summary of the release.",
            "opinion": "I am watching how builders use this.",
            "confidence": 0.7,
        }
        parsed = parse_strict_analysis_json(json.dumps(row))
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["topic"], "Models")
        self.assertTrue(parsed["opinion"])


if __name__ == "__main__":
    unittest.main()

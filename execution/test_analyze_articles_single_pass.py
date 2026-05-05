"""Tests for single-pass article analysis (JSON mode, retry, opinion derivation)."""

import unittest
from unittest.mock import patch

from execution.analyze_articles_single_pass import (
    analyze_article,
    derive_opinion_from_summary,
    parse_strict_analysis_json,
)


class ParseStrictAnalysisJsonTests(unittest.TestCase):
    def test_valid_json(self) -> None:
        raw = '{"topic":"Industry","summary":"A short summary.","opinion":"My take.","confidence":0.5}'
        out = parse_strict_analysis_json(raw)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(out["topic"], "Industry")
        self.assertTrue(out["summary"])
        self.assertEqual(out["opinion"], "My take.")

    def test_invalid_returns_none(self) -> None:
        self.assertIsNone(parse_strict_analysis_json("not json"))

    def test_empty_summary_returns_none(self) -> None:
        raw = '{"topic":"Industry","summary":"","opinion":"x","confidence":1}'
        self.assertIsNone(parse_strict_analysis_json(raw))


class AnalyzeArticleTests(unittest.TestCase):
    def test_model_path_first_call_complete(self) -> None:
        payload = (
            '{"topic":"Industry","summary":"Summary here.","opinion":"Opinion here.","confidence":0.9}'
        )
        with patch("execution.analyze_articles_single_pass.generate_text_with_fallback") as gen:
            gen.return_value = payload
            out = analyze_article("Title", "body", "https://example.com")
            self.assertEqual(out["opinion_source"], "model")
            self.assertEqual(gen.call_count, 1)

    def test_retry_path_second_call_complete(self) -> None:
        ok = '{"topic":"Industry","summary":"S2","opinion":"O2","confidence":0.8}'
        with patch("execution.analyze_articles_single_pass.generate_text_with_fallback") as gen:
            gen.side_effect = ["not valid json {", ok]
            out = analyze_article("T", "c", "https://e")
            self.assertEqual(out["opinion_source"], "retry")
            self.assertEqual(gen.call_count, 2)
            self.assertEqual(out["opinion"], "O2")

    def test_derived_path_when_both_json_missing_opinion(self) -> None:
        j = '{"topic":"Industry","summary":"Only summary.","opinion":"","confidence":1}'
        with patch("execution.analyze_articles_single_pass.generate_text_with_fallback") as gen:
            gen.side_effect = [j, j, "I am watching how this unfolds for builders."]
            out = analyze_article("T", "c", "https://e")
            self.assertEqual(out["opinion_source"], "derived")
            self.assertTrue(str(out.get("opinion", "")).strip())
            self.assertEqual(gen.call_count, 3)

    def test_none_when_no_summary_anywhere(self) -> None:
        bad = '{"topic":"Industry","summary":"","opinion":"","confidence":0}'
        with patch("execution.analyze_articles_single_pass.generate_text_with_fallback") as gen:
            gen.side_effect = [bad, "still not json"]
            out = analyze_article("T", "c", "https://e")
            self.assertEqual(out["opinion_source"], "none")
            self.assertEqual(out["summary"], "")


class DeriveOpinionTests(unittest.TestCase):
    def test_derive_calls_llm(self) -> None:
        with patch("execution.analyze_articles_single_pass.generate_text_with_fallback") as gen:
            gen.return_value = "  Watching this closely.  "
            out = derive_opinion_from_summary("My title", "My summary", "gemini-2.0-flash")
            self.assertIn("Watching", out)
            gen.assert_called_once()
            call_kw = gen.call_args.kwargs
            self.assertFalse(call_kw.get("json_mode", True))


if __name__ == "__main__":
    unittest.main()

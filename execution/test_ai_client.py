"""Tests for Claude-only AI client helpers."""

import os
import unittest
from unittest.mock import patch

from execution.ai_client import (
    DEFAULT_MODEL,
    generate_text_with_fallback,
    resolve_effort,
    resolve_model,
)


class ResolveModelTests(unittest.TestCase):
    def test_default_is_opus_5(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_MODEL", None)
            self.assertEqual(resolve_model(None), DEFAULT_MODEL)
            self.assertEqual(DEFAULT_MODEL, "claude-opus-5")

    def test_explicit_model_wins(self) -> None:
        self.assertEqual(resolve_model("claude-opus-5"), "claude-opus-5")


class ResolveEffortTests(unittest.TestCase):
    def test_default_low(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_EFFORT", None)
            self.assertEqual(resolve_effort(), "low")

    def test_invalid_effort_raises(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_EFFORT": "max"}):
            with self.assertRaises(RuntimeError):
                resolve_effort()


class GenerateTextAliasTests(unittest.TestCase):
    def test_fallback_alias_maps_gemini_model(self) -> None:
        with patch("execution.ai_client.generate_text", return_value="ok") as gen:
            out = generate_text_with_fallback(prompt="hi", gemini_model="claude-opus-5")
            self.assertEqual(out, "ok")
            gen.assert_called_once()
            self.assertEqual(gen.call_args.kwargs.get("model"), "claude-opus-5")


if __name__ == "__main__":
    unittest.main()

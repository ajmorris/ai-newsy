"""Tests for LLM client helpers and the Claude Code CLI provider."""

import json
import os
import subprocess
import unittest
from unittest.mock import patch

from execution.ai_client import (
    ClaudeCodeProvider,
    _error_category,
    _model_looks_compatible,
    _provider_default_model,
    llm_credentials_configured,
)


class CredentialGuardTests(unittest.TestCase):
    def test_true_when_oauth_token_set(self) -> None:
        with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "token"}, clear=True):
            self.assertTrue(llm_credentials_configured())

    def test_false_when_empty(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(llm_credentials_configured())


class ModelResolutionTests(unittest.TestCase):
    def test_claude_code_accepts_claude_models(self) -> None:
        self.assertTrue(_model_looks_compatible("claude_code", "claude-opus-4-6"))
        self.assertFalse(_model_looks_compatible("claude_code", "gemini-2.0-flash"))

    def test_claude_code_model_falls_back_to_anthropic_model(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": "claude-sonnet-4-6"}, clear=True):
            self.assertEqual(_provider_default_model("claude_code"), "claude-sonnet-4-6")


class ClaudeCodeProviderTests(unittest.TestCase):
    def test_requires_oauth_token(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "CLAUDE_CODE_OAUTH_TOKEN"):
                ClaudeCodeProvider().generate("hello", "claude-opus-4-6", 0.2)

    def test_requires_cli_on_path(self) -> None:
        with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "token"}, clear=True):
            with patch("execution.ai_client.shutil.which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "not on PATH"):
                    ClaudeCodeProvider().generate("hello", "claude-opus-4-6", 0.2)

    def test_returns_result_from_cli_json(self) -> None:
        payload = json.dumps({"result": "Hello from Claude", "is_error": False})
        completed = subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout=payload,
            stderr="",
        )
        with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "token"}, clear=True):
            with patch("execution.ai_client.shutil.which", return_value="/usr/bin/claude"):
                with patch("execution.ai_client.subprocess.run", return_value=completed) as run:
                    text = ClaudeCodeProvider().generate(
                        "Summarize this",
                        "claude-opus-4-6",
                        0.2,
                    )

        self.assertEqual(text, "Hello from Claude")
        command = run.call_args.args[0]
        self.assertEqual(command[0], "/usr/bin/claude")
        self.assertEqual(command[1], "-p")
        self.assertEqual(command[2], "Summarize this")
        self.assertIn("--output-format", command)
        self.assertIn("json", command)
        self.assertIn("--max-turns", command)
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertNotIn("token", command)

    def test_is_error_raises(self) -> None:
        payload = json.dumps({"result": "rate limited", "is_error": True})
        completed = subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout=payload,
            stderr="",
        )
        with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "token"}, clear=True):
            with patch("execution.ai_client.shutil.which", return_value="/usr/bin/claude"):
                with patch("execution.ai_client.subprocess.run", return_value=completed):
                    with self.assertRaisesRegex(RuntimeError, "rate limited"):
                        ClaudeCodeProvider().generate("hello", "claude-opus-4-6", 0.2)

    def test_oauth_error_is_auth_category(self) -> None:
        self.assertEqual(_error_category(RuntimeError("oauth token expired")), "auth")


if __name__ == "__main__":
    unittest.main()

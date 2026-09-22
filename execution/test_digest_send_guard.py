"""Tests for Daily AI Digest send-guard event matrix."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from execution.digest_send_guard import decide_should_send, main


REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_SCRIPT = REPO_ROOT / "execution" / "digest_send_guard.py"
DAILY_DIGEST_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily_digest.yml"


class DecideShouldSendTests(unittest.TestCase):
    def test_schedule_allows_send(self) -> None:
        # Reusable workflow inherits caller's cron event name.
        ok, reason = decide_should_send("schedule")
        self.assertTrue(ok)
        self.assertIn("pipeline", reason.lower())

    def test_workflow_call_allows_send(self) -> None:
        ok, reason = decide_should_send("workflow_call")
        self.assertTrue(ok)
        self.assertIn("pipeline", reason.lower())

    def test_workflow_dispatch_without_force_blocks(self) -> None:
        ok, reason = decide_should_send("workflow_dispatch", force_send=False)
        self.assertFalse(ok)
        self.assertIn("force_send", reason)

    def test_workflow_dispatch_with_force_allows(self) -> None:
        ok, reason = decide_should_send("workflow_dispatch", force_send=True)
        self.assertTrue(ok)
        self.assertIn("force_send=true", reason)

    def test_unsupported_event_blocks(self) -> None:
        ok, reason = decide_should_send("push")
        self.assertFalse(ok)
        self.assertIn("Unsupported event", reason)


class GuardCliTests(unittest.TestCase):
    def test_cli_schedule_writes_true_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github_output"
            env = {**os.environ, "GITHUB_OUTPUT": str(output)}
            proc = subprocess.run(
                [
                    "python3",
                    str(GUARD_SCRIPT),
                    "--event-name",
                    "schedule",
                    "--force-send",
                    "false",
                ],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("should_send=true", output.read_text(encoding="utf-8"))

    def test_cli_dispatch_without_force_writes_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github_output"
            env = {**os.environ, "GITHUB_OUTPUT": str(output)}
            proc = subprocess.run(
                [
                    "python3",
                    str(GUARD_SCRIPT),
                    "--event-name",
                    "workflow_dispatch",
                    "--force-send",
                    "false",
                ],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("should_send=false", output.read_text(encoding="utf-8"))

    def test_main_schedule_never_silently_skips(self) -> None:
        # Defensive: if decide_should_send ever blocked schedule, CLI must fail.
        # With current logic schedule always sends; assert exit 0 + true output.
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github_output"
            os.environ["GITHUB_OUTPUT"] = str(output)
            try:
                code = main(["--event-name", "schedule", "--force-send", "false"])
            finally:
                os.environ.pop("GITHUB_OUTPUT", None)
            self.assertEqual(code, 0)
            self.assertIn("should_send=true", output.read_text(encoding="utf-8"))

    def test_main_fails_loud_if_schedule_blocked(self) -> None:
        import execution.digest_send_guard as guard_mod

        original = guard_mod.decide_should_send
        guard_mod.decide_should_send = lambda event_name, force_send=False: (
            False,
            "injected block",
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github_output"
            os.environ["GITHUB_OUTPUT"] = str(output)
            try:
                code = main(["--event-name", "schedule", "--force-send", "false"])
            finally:
                os.environ.pop("GITHUB_OUTPUT", None)
                guard_mod.decide_should_send = original
            self.assertEqual(code, 1)
            self.assertIn("should_send=false", output.read_text(encoding="utf-8"))


class WorkflowWiresGuardTests(unittest.TestCase):
    def test_daily_digest_invokes_shared_guard(self) -> None:
        text = DAILY_DIGEST_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("execution/digest_send_guard.py", text)
        self.assertIn("github.event_name", text)
        self.assertIn("inputs.force_send", text)


if __name__ == "__main__":
    unittest.main()

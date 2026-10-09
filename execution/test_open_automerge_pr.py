"""Tests for landing digest commits through CI and auto-merge."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from execution.open_automerge_pr import (
    check_outcome,
    interpret_pull_request,
    main,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class InterpretPullRequestTests(unittest.TestCase):
    def test_merged_stops(self) -> None:
        decision = interpret_pull_request({"state": "MERGED"})
        self.assertEqual(decision.action, "merged")

    def test_closed_fails(self) -> None:
        decision = interpret_pull_request({"state": "CLOSED"})
        self.assertEqual(decision.action, "fail")

    def test_failed_check_fails_before_merge(self) -> None:
        decision = interpret_pull_request(
            {
                "state": "OPEN",
                "mergeStateStatus": "UNSTABLE",
                "statusCheckRollup": [
                    {
                        "workflowName": "CI",
                        "name": "test",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                    }
                ],
            }
        )
        self.assertEqual(decision.action, "fail")
        self.assertIn("CI / test", decision.message)

    def test_pending_check_waits(self) -> None:
        decision = interpret_pull_request(
            {
                "state": "OPEN",
                "mergeStateStatus": "BLOCKED",
                "statusCheckRollup": [
                    {
                        "workflowName": "CI",
                        "name": "test",
                        "status": "IN_PROGRESS",
                        "conclusion": "",
                    }
                ],
            }
        )
        self.assertEqual(decision.action, "wait")

    def test_missing_checks_wait(self) -> None:
        decision = interpret_pull_request(
            {"state": "OPEN", "mergeStateStatus": "BLOCKED", "statusCheckRollup": []}
        )
        self.assertEqual(decision.action, "wait")

    def test_green_checks_merge(self) -> None:
        decision = interpret_pull_request(
            {
                "state": "OPEN",
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {
                        "workflowName": "CI",
                        "name": "test",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                    }
                ],
            }
        )
        self.assertEqual(decision.action, "merge_now")

    def test_skipped_check_counts_as_passed(self) -> None:
        self.assertEqual(
            check_outcome({"status": "COMPLETED", "conclusion": "SKIPPED"}),
            "pass",
        )

    def test_behind_updates_branch_instead_of_merging(self) -> None:
        decision = interpret_pull_request(
            {
                "state": "OPEN",
                "mergeStateStatus": "BEHIND",
                "statusCheckRollup": [
                    {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}
                ],
            }
        )
        self.assertEqual(decision.action, "update_branch")

    def test_conflicts_fail(self) -> None:
        decision = interpret_pull_request(
            {"state": "OPEN", "mergeStateStatus": "DIRTY", "statusCheckRollup": []}
        )
        self.assertEqual(decision.action, "fail")

    def test_commit_status_failure_field(self) -> None:
        self.assertEqual(check_outcome({"context": "CI / test", "state": "FAILURE"}), "fail")


class WorkflowWiringTests(unittest.TestCase):
    def test_generated_commits_open_pull_requests(self) -> None:
        for name in (
            "finalize_digest_payload.yml",
            "daily_digest.yml",
            "publish_web_archive.yml",
            "rebuild_digest_markdown.yml",
        ):
            text = (REPO_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertIn("execution/open_automerge_pr.py", text, name)
            self.assertNotIn('git push origin "HEAD:', text, name)

    def test_ci_can_be_dispatched_onto_the_automation_branch(self) -> None:
        text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)

    def test_pipeline_grants_pull_request_permission_and_publishes_after_send(self) -> None:
        text = (REPO_ROOT / ".github" / "workflows" / "digest_pipeline.yml").read_text(encoding="utf-8")
        self.assertIn("pull-requests: write", text)
        self.assertIn("publish_web_archive.yml", text)

    def test_cli_rejects_unsafe_branch(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            main(["--branch", "automation/bad branch", "--base", "main", "--title", "t"])
        self.assertNotEqual(raised.exception.code, 0)


class CliHelpTests(unittest.TestCase):
    def test_help_exits_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "execution/open_automerge_pr.py", "--help"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--timeout-seconds", proc.stdout)


if __name__ == "__main__":
    unittest.main()

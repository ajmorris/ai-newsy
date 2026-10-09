"""Generated digest files are pushed to the base branch."""

from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DirectPushWiringTests(unittest.TestCase):
    def test_generated_commits_push_to_the_base_branch(self) -> None:
        for name in (
            "daily_digest.yml",
            "publish_web_archive.yml",
            "rebuild_digest_markdown.yml",
        ):
            text = (REPO_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertIn('git push origin "HEAD:', text, name)
            self.assertNotIn("open_automerge_pr.py", text, name)
            self.assertNotIn("GH_TOKEN:", text, name)
            self.assertNotIn("pull-requests:", text, name)

    def test_pipeline_publishes_after_send_without_pull_requests(self) -> None:
        text = (REPO_ROOT / ".github" / "workflows" / "digest_pipeline.yml").read_text(encoding="utf-8")
        self.assertIn("publish_web_archive.yml", text)
        self.assertIn("pipeline_run: true", text)
        self.assertNotIn("pull-requests:", text)
        self.assertNotIn("open_automerge_pr.py", text)

    def test_ci_runs_on_pull_requests_and_main(self) -> None:
        text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", text)
        self.assertIn('name: "CI / test"', text)
        self.assertNotIn("workflow_dispatch:", text)


if __name__ == "__main__":
    unittest.main()

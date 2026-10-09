#!/usr/bin/env python3
"""Land one local commit on the protected branch through a pull request.

The CI ruleset rejects direct pushes to the default branch. A pull request
opened with the Actions token also does not start other workflows, so this
script dispatches CI itself, enables auto-merge, and waits until the required
check is green and the pull request is merged.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional, Sequence


PASSING = {"SUCCESS", "SUCCESSFUL", "SKIPPED", "NEUTRAL"}
FAILING = {"FAILURE", "CANCELLED", "CANCELED", "TIMED_OUT", "ACTION_REQUIRED", "ERROR", "STALE"}
PENDING = {"QUEUED", "IN_PROGRESS", "PENDING", "WAITING", "REQUESTED", "EXPECTED"}
MERGE_READY = {"CLEAN", "UNSTABLE", "HAS_HOOKS", "UNKNOWN", "BLOCKED"}

GIT = [
    "git",
    "-c",
    "user.name=github-actions[bot]",
    "-c",
    "user.email=41898282+github-actions[bot]@users.noreply.github.com",
]


class PollDecision:
    def __init__(self, action: str, message: str) -> None:
        self.action = action
        self.message = message


def check_label(check: dict) -> str:
    workflow = str(check.get("workflowName") or "").strip()
    name = str(check.get("name") or check.get("context") or "check").strip()
    if workflow:
        return f"{workflow} / {name}"
    return name


def check_outcome(check: dict) -> str:
    """Return pass, fail, or pending for one statusCheckRollup entry."""
    status = str(check.get("status") or "").upper()
    conclusion = str(check.get("conclusion") or check.get("state") or "").upper()
    if conclusion in FAILING or status in FAILING:
        return "fail"
    if status in PENDING or conclusion in PENDING:
        return "pending"
    if conclusion in PASSING or status in PASSING:
        return "pass"
    return "pending"


def interpret_pull_request(payload: dict) -> PollDecision:
    """Decide whether to stop, merge, update the branch, or keep waiting."""
    state = str(payload.get("state") or "").upper()
    if state == "MERGED":
        return PollDecision("merged", "Pull request merged.")
    if state == "CLOSED":
        return PollDecision("fail", "Pull request closed without merging.")

    rollup = payload.get("statusCheckRollup") or []
    failed = [check_label(check) for check in rollup if check_outcome(check) == "fail"]
    if failed:
        return PollDecision("fail", "Required checks failed: " + ", ".join(failed))

    merge_state = str(payload.get("mergeStateStatus") or "").upper()
    if merge_state == "DIRTY":
        return PollDecision("fail", "Pull request conflicts with the base branch.")
    if merge_state == "BEHIND":
        return PollDecision("update_branch", "Branch is behind the base branch.")

    if rollup and all(check_outcome(check) == "pass" for check in rollup):
        if merge_state in MERGE_READY or not merge_state:
            return PollDecision("merge_now", "Checks passed. Merging.")
    return PollDecision("wait", "Waiting for CI / test.")


def _run(
    args: Sequence[str],
    cwd: Optional[Path] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=True,
    )


def ensure_gh_token() -> None:
    """Point gh at the Actions token. gh reads GH_TOKEN and ignores GITHUB_TOKEN."""
    if (os.environ.get("GH_TOKEN") or "").strip():
        return
    github_token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    if not github_token:
        raise SystemExit(
            "GH_TOKEN is not set. In GitHub Actions set GH_TOKEN to github.token."
        )
    os.environ["GH_TOKEN"] = github_token


def _validate_ref(name: str, label: str) -> str:
    if not name or any(char.isspace() for char in name) or ".." in name:
        raise SystemExit(f"Unsafe {label}: {name!r}")
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._/-")
    if any(char not in allowed for char in name):
        raise SystemExit(f"Unsafe {label}: {name!r}")
    return name


def _cherry_pick_onto_base(base: str, branch: str) -> str:
    """Put HEAD's commit on a branch cut from origin/base. Return pushed or empty."""
    head = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    _run(["git", "fetch", "origin", base])
    _run(["git", "worktree", "prune"], check=False)
    _run(["git", "branch", "-f", branch, f"origin/{base}"])

    parent = Path(tempfile.mkdtemp(prefix="automerge-"))
    worktree = parent / "wt"
    try:
        _run(["git", "worktree", "add", str(worktree), branch])
        picked = _run(GIT + ["cherry-pick", head], cwd=worktree, check=False)
        combined = f"{picked.stdout}\n{picked.stderr}"
        if picked.returncode != 0:
            if "empty" in combined.lower():
                _run(GIT + ["cherry-pick", "--abort"], cwd=worktree, check=False)
                print("Commit is already on the base branch. Nothing to open.")
                return "empty"
            raise SystemExit(combined.strip() or f"cherry-pick failed ({picked.returncode})")
        _run(["git", "push", "--force-with-lease", "-u", "origin", branch], cwd=worktree)
    finally:
        _run(["git", "worktree", "remove", "--force", str(worktree)], check=False)
        shutil.rmtree(parent, ignore_errors=True)
    return "pushed"


def _update_branch(base: str, branch: str) -> None:
    _run(["git", "fetch", "origin", base, branch])
    _run(["git", "worktree", "prune"], check=False)
    parent = Path(tempfile.mkdtemp(prefix="automerge-update-"))
    worktree = parent / "wt"
    try:
        _run(["git", "worktree", "add", str(worktree), branch])
        merged = _run(GIT + ["merge", f"origin/{base}", "--no-edit"], cwd=worktree, check=False)
        if merged.returncode != 0:
            raise SystemExit((merged.stdout + merged.stderr).strip() or "Could not update branch")
        _run(["git", "push", "--force-with-lease", "origin", branch], cwd=worktree)
    finally:
        _run(["git", "worktree", "remove", "--force", str(worktree)], check=False)
        shutil.rmtree(parent, ignore_errors=True)


def _pr_number(branch: str, base: str, title: str, body: str) -> str:
    listed = _run(
        [
            "gh",
            "pr",
            "list",
            "--head",
            branch,
            "--base",
            base,
            "--json",
            "number",
            "--jq",
            ".[0].number",
        ],
        check=False,
    )
    number = (listed.stdout or "").strip()
    if number and number != "null":
        print(f"Using existing pull request #{number}")
        return number
    created = _run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            base,
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
        ]
    )
    url = (created.stdout or "").strip()
    print(url)
    viewed = _run(["gh", "pr", "view", url or branch, "--json", "number", "--jq", ".number"])
    return viewed.stdout.strip()


def _dispatch_ci(branch: str, workflow: str) -> None:
    last = ""
    for _attempt in range(5):
        dispatched = _run(["gh", "workflow", "run", workflow, "--ref", branch], check=False)
        if dispatched.returncode == 0:
            print(f"Dispatched {workflow} on {branch}")
            return
        last = (dispatched.stderr or dispatched.stdout or "").strip()
        time.sleep(3)
    raise SystemExit(last or f"Could not dispatch {workflow}")


def _enable_automerge(number: str) -> None:
    enabled = _run(
        ["gh", "pr", "merge", number, "--auto", "--squash", "--delete-branch"],
        check=False,
    )
    if enabled.returncode == 0:
        print(f"Auto-merge enabled for #{number}")
        return
    message = (enabled.stderr or enabled.stdout or "").strip()
    print(message or "Auto-merge is not enabled yet. Will retry after checks report.")


def _view(number: str) -> dict:
    viewed = _run(
        [
            "gh",
            "pr",
            "view",
            number,
            "--json",
            "state,statusCheckRollup,mergeStateStatus",
        ]
    )
    return json.loads(viewed.stdout)


def wait_for_merge(
    number: str,
    base: str,
    branch: str,
    workflow: str,
    timeout_seconds: int,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> None:
    """Poll until the pull request merges, a check fails, or the timeout elapses."""
    deadline = now() + timeout_seconds
    updates = 0
    while now() < deadline:
        decision = interpret_pull_request(_view(number))
        print(decision.message)
        if decision.action == "merged":
            return
        if decision.action == "fail":
            raise SystemExit(decision.message)
        if decision.action == "update_branch":
            updates += 1
            if updates > 3:
                raise SystemExit("Branch stayed behind the base branch.")
            _update_branch(base, branch)
            _dispatch_ci(branch, workflow)
            _enable_automerge(number)
        elif decision.action == "merge_now":
            merged = _run(
                ["gh", "pr", "merge", number, "--squash", "--delete-branch"],
                check=False,
            )
            if merged.returncode != 0:
                message = (merged.stderr or merged.stdout or "").strip()
                print(message)
                if "up to date" in message.lower() or "behind" in message.lower():
                    updates += 1
                    if updates > 3:
                        raise SystemExit("Branch stayed behind the base branch.")
                    _update_branch(base, branch)
                    _dispatch_ci(branch, workflow)
                    _enable_automerge(number)
        sleep(15)
    raise SystemExit(f"Timed out after {timeout_seconds}s waiting for #{number} to merge.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--body",
        default="Generated by the digest pipeline. Auto-merge runs after CI / test passes.",
    )
    parser.add_argument("--workflow", default="ci.yml")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args(argv)

    branch = _validate_ref(args.branch, "branch")
    base = _validate_ref(args.base, "base")
    ensure_gh_token()
    if _cherry_pick_onto_base(base, branch) == "empty":
        return 0
    number = _pr_number(branch, base, args.title, args.body)
    _dispatch_ci(branch, args.workflow)
    _enable_automerge(number)
    wait_for_merge(number, base, branch, args.workflow, args.timeout_seconds)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        print(detail or f"Command failed: {' '.join(exc.cmd)}", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc

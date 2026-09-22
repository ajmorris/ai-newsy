#!/usr/bin/env python3
"""Decide whether Daily AI Digest should proceed past the send guard.

Reusable workflows inherit the *caller's* event name. When digest_pipeline.yml
invokes daily_digest.yml on cron, github.event_name is ``schedule``, not
``workflow_call``. Treat both as pipeline sends. Manual dispatch still requires
force_send=true.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Tuple


def decide_should_send(event_name: str, force_send: bool = False) -> Tuple[bool, str]:
    """Return (should_send, reason) for the Daily AI Digest guard."""
    name = (event_name or "").strip()

    # Pipeline cron (reusable workflow inherits caller event) or explicit call.
    if name in ("schedule", "workflow_call"):
        return True, "Called from digest pipeline after finalize."

    if name == "workflow_dispatch":
        if force_send:
            return True, "Manual run with force_send=true."
        return False, "Manual run blocked unless force_send=true."

    return False, f"Unsupported event: {name or '(empty)'}."


def _write_github_output(should_send: bool) -> None:
    output_path = (os.getenv("GITHUB_OUTPUT") or "").strip()
    line = f"should_send={'true' if should_send else 'false'}"
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    else:
        print(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily AI Digest send guard")
    parser.add_argument(
        "--event-name",
        required=True,
        help="github.event_name (schedule|workflow_call|workflow_dispatch|...)",
    )
    parser.add_argument(
        "--force-send",
        default="false",
        help="inputs.force_send as true/false string",
    )
    args = parser.parse_args(argv)

    force = str(args.force_send).strip().lower() in ("1", "true", "yes")
    should_send, reason = decide_should_send(args.event_name, force_send=force)

    if should_send:
        print(f"Guard: proceeding with send. Reason: {reason}")
    else:
        print(f"Guard: skipping later steps. Reason: {reason}")

    # Pipeline schedule must never silently no-op.
    if args.event_name.strip() == "schedule" and not should_send:
        print("Guard: refusing silent skip for schedule event.", file=sys.stderr)
        _write_github_output(False)
        return 1

    _write_github_output(should_send)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

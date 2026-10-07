"""Return a recorded model response when LLM_FIXTURE_PATH is set.

The fixture file is JSON: {"default": "...", "cases": [{"contains": "...", "response": "..."}]}.
The first case whose `contains` text appears in the prompt wins.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def fixture_response_for_prompt(prompt: str) -> Optional[str]:
    path = (os.getenv("LLM_FIXTURE_PATH") or "").strip()
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    for case in cases:
        if not isinstance(case, dict):
            continue
        needle = str(case.get("contains", "") or "")
        if needle and needle in prompt:
            return str(case.get("response", ""))
    if "default" in payload:
        return str(payload.get("default", ""))
    raise RuntimeError(f"LLM fixture {path} has no match for this prompt")

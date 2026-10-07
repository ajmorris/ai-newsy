"""Collapse articles that describe the same event into one newsletter slot.

The match is title plus summary. URLs are kept so every source stays linked.
Positive or negative tone is not a reason to merge or to keep items apart.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

Generate = Callable[[str], str]

CLUSTER_PROMPT = """You group newsletter candidates that describe the same event.
Compare title and summary only. Ignore whether the tone is positive or negative.
Two outlets can disagree and still be the same event. Do not merge different events
that merely share a company, product, or person.

Return JSON only:
{{"groups":[{{"ids":["id"],"reason":"why these are one event","headline":"","summary":"","opinion":"","conflicts":["WSJ reports X; NYT puts it at Y"],"update":false}}]}}

Rules:
- Every candidate id appears in exactly one group.
- A group summary and opinion may only use facts written in those summaries.
- Do not average conflicting figures. Put them in conflicts, attributed to the source.
- update is true only when the group matches one of the already covered items.
- Single-item groups still need a reason.

Already covered:
{already_covered}

Candidates:
{candidates}
"""


def _parse_time(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.max
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.max


def _extract_json(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, count=1, flags=re.IGNORECASE).strip()
        raw = re.sub(r"\s*```$", "", raw, count=1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("cluster response did not contain JSON")
    payload = json.loads(raw[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("cluster response JSON must be an object")
    return payload


def _lead_item(items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return min(items, key=lambda item: _parse_time(str(item.get("published_at") or item.get("fetched_at") or "")))


def _cluster_payload(items: Sequence[Dict[str, Any]], group: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if len(items) < 2 and not group.get("update"):
        return None
    lead = _lead_item(items)
    ordered = [lead] + [item for item in items if item is not lead]
    sources = []
    for item in ordered:
        sources.append(
            {
                "id": item.get("id"),
                "source": item.get("source", ""),
                "title": item.get("title", ""),
                "url": item.get("url", ""),
            }
        )
    conflicts = [str(line).strip() for line in group.get("conflicts") or [] if str(line).strip()]
    return {
        "sources": sources,
        "badge_count": len(items),
        "conflicts": conflicts,
        "is_update": bool(group.get("update")),
        "reason": str(group.get("reason", "") or "").strip(),
    }


def apply_groups(items: Sequence[Dict[str, Any]], response_text: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Turn a model grouping into newsletter stories. Unknown ids are kept alone."""
    by_id = {str(item.get("id")): item for item in items}
    payload = _extract_json(response_text)
    groups = payload.get("groups") or []
    used = set()
    stories: List[Dict[str, Any]] = []
    log: List[Dict[str, Any]] = []

    for group in groups:
        if not isinstance(group, dict):
            continue
        ids = [str(item_id) for item_id in group.get("ids") or []]
        if any(item_id.startswith("yesterday:") for item_id in ids):
            group = {**group, "update": True}
        members = []
        for item_id in ids:
            if item_id.startswith("yesterday:"):
                continue
            item = by_id.get(item_id)
            if item is None or item_id in used:
                continue
            members.append(item)
            used.add(item_id)
        if not members:
            continue
        merged = _merge_members(members, group)
        stories.append(merged)
        log.append(
            {
                "ids": [member.get("id") for member in members],
                "reason": str(group.get("reason", "") or ""),
                "badge_count": len(members),
                "is_update": bool(group.get("update")),
            }
        )

    for item in items:
        if str(item.get("id")) not in used:
            stories.append(dict(item))
            log.append({"ids": [item.get("id")], "reason": "left ungrouped", "badge_count": 1, "is_update": False})
    return stories, log


def _merge_members(members: Sequence[Dict[str, Any]], group: Dict[str, Any]) -> Dict[str, Any]:
    lead = dict(_lead_item(members))
    headline = str(group.get("headline", "") or "").strip()
    summary = str(group.get("summary", "") or "").strip() or str(lead.get("summary", "") or "")
    opinion = str(group.get("opinion", "") or "").strip() or str(lead.get("opinion", "") or "")
    cluster = _cluster_payload(members, group)
    if cluster and cluster["conflicts"]:
        differing = " ".join(cluster["conflicts"])
        if differing not in opinion:
            opinion = f"{opinion} Where coverage differs: {differing}".strip()
    if headline:
        lead["title"] = headline
    lead["summary"] = summary
    lead["opinion"] = opinion
    if cluster and (cluster["badge_count"] > 1 or cluster["is_update"]):
        lead["cluster"] = cluster
    else:
        lead.pop("cluster", None)
    return lead


def clustering_precision(log: Sequence[Dict[str, Any]], same_event_pairs: Sequence[tuple]) -> float:
    """Precision of merges: a pair merged by the log is correct when it is labeled same-event."""
    labeled = {tuple(sorted((str(left), str(right)))) for left, right in same_event_pairs}
    predicted = []
    for entry in log:
        ids = [str(item_id) for item_id in entry.get("ids") or []]
        if len(ids) < 2:
            continue
        for index, left in enumerate(ids):
            for right in ids[index + 1 :]:
                predicted.append(tuple(sorted((left, right))))
    if not predicted:
        return 1.0
    correct = sum(1 for pair in predicted if pair in labeled)
    return correct / len(predicted)


def build_cluster_prompt(items: Sequence[Dict[str, Any]], already_covered: Sequence[Dict[str, Any]]) -> str:
    candidates = []
    for item in items:
        candidates.append(
            {
                "id": str(item.get("id")),
                "source": item.get("source", ""),
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
            }
        )
    covered = []
    for index, item in enumerate(already_covered):
        covered.append(
            {
                "id": f"yesterday:{index}",
                "source": item.get("source", ""),
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
            }
        )
    return CLUSTER_PROMPT.format(
        already_covered=json.dumps(covered, ensure_ascii=False),
        candidates=json.dumps(candidates, ensure_ascii=False),
    )


CLUSTER_BATCH = 40


def _cluster_once(
    items: Sequence[Dict[str, Any]],
    covered: Sequence[Dict[str, Any]],
    generate: Generate,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    prompt = build_cluster_prompt(items, covered)
    try:
        response = generate(prompt)
        stories, log = apply_groups(items, response)
    except Exception as exc:
        print(f"    Warning: story clustering skipped: {exc}")
        return [dict(item) for item in items], [{"ids": [item.get("id") for item in items], "reason": f"skipped: {exc}"}]
    for entry in log:
        print(f"    Cluster {entry.get('ids')}: {entry.get('reason')}")
    return stories, log


def cluster_with_model(
    items: Sequence[Dict[str, Any]],
    already_covered: Optional[Sequence[Dict[str, Any]]] = None,
    generate: Optional[Generate] = None,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Group items with one model call, batched when the window is large.

    A failure leaves every article in that batch as its own story.
    """
    covered = list(already_covered or [])
    if len(items) < 2 and not covered:
        return [dict(item) for item in items], []
    if generate is None:
        from execution.ai_client import generate_text_with_fallback

        def generate(prompt: str) -> str:
            return generate_text_with_fallback(prompt=prompt, json_mode=True)

    stories: List[Dict[str, Any]] = []
    log: List[Dict[str, Any]] = []
    for start in range(0, len(items), CLUSTER_BATCH):
        chunk_stories, chunk_log = _cluster_once(items[start : start + CLUSTER_BATCH], covered, generate)
        stories.extend(chunk_stories)
        log.extend(chunk_log)
    return stories, log

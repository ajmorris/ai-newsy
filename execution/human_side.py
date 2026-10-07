"""Pick a short human-side section from titles and summaries.

Rules decide the tag. The model is only a tiebreaker when HUMAN_LLM_TIEBREAKER=1.
The section is omitted when fewer than two items qualify.
"""

from __future__ import annotations

import os
import re
from typing import Callable, Dict, List, Optional, Sequence

Judge = Callable[[Dict], str]

HUMAN_MIN = 2
HUMAN_MAX = 4
SECTION_TITLE = "The human side"

TAGS = (
    "change management",
    "workforce",
    "skills",
    "culture",
    "ethics",
    "environment",
)

_RULES = (
    (
        "environment",
        (
            r"\bclimate\b",
            r"\bemissions?\b",
            r"\bcarbon footprint\b",
            r"\bdata centers?\b.{0,40}\b(energy|water|power)\b",
            r"\b(energy|water|power)\b.{0,40}\bdata centers?\b",
        ),
    ),
    (
        "ethics",
        (
            r"\bethic",
            r"\balgorithmic bias\b",
            r"\bfairness\b",
            r"\bworker surveillance\b",
            r"\bsurveillance\b",
        ),
    ),
    (
        "skills",
        (
            r"\bupskilling\b",
            r"\breskilling\b",
            r"\bai literacy\b",
            r"\bjob training\b",
            r"\bworkforce training\b",
        ),
    ),
    (
        "workforce",
        (
            r"\blayoffs?\b",
            r"\bjob cuts\b",
            r"\bhiring freeze\b",
            r"\bworkforce\b",
            r"\bemployees?\b",
            r"\bworkers?\b",
            r"\breturn to office\b",
        ),
    ),
    (
        "culture",
        (
            r"\bworkplace culture\b",
            r"\bcompany culture\b",
            r"\bburnout\b",
            r"\bremote work\b",
            r"\bpeople managers?\b",
        ),
    ),
    (
        "change management",
        (
            r"\bchange management\b",
            r"\borganizational change\b",
            r"\bchange program\b",
            r"\brollout plan\b",
        ),
    ),
)

MEANING = {
    "change management": "Name the behavior that has to change, and who owns the rollout.",
    "workforce": "Be explicit about whose work changes and what happens to the people doing it.",
    "skills": "Pair the new tool with time and training, or the skill gap stays with the team.",
    "culture": "Watch how the change lands on trust, load, and how people work together.",
    "ethics": "Decide the boundary before the tool is in daily use.",
    "environment": "Count the energy and resource cost next to the capability gain.",
}


def _blob(item: Dict) -> str:
    return f"{item.get('title', '')} {item.get('headline', '')} {item.get('summary', '')}".lower()


def rule_tag(item: Dict) -> str:
    text = _blob(item)
    for tag, patterns in _RULES:
        if any(re.search(pattern, text) for pattern in patterns):
            return tag
    return ""


def llm_human_judge(item: Dict) -> str:
    """Ask the model only when HUMAN_LLM_TIEBREAKER=1. Rules still win first."""
    if os.getenv("HUMAN_LLM_TIEBREAKER", "").strip() not in {"1", "true", "yes"}:
        return ""
    from execution.ai_client import generate_text_with_fallback

    prompt = (
        "Classify this item as one of: change management, workforce, skills, culture, "
        "ethics, environment, none. Reply with the label only.\n"
        f"Title: {item.get('title', '')}\nSummary: {item.get('summary', '')}"
    )
    label = generate_text_with_fallback(prompt=prompt, json_mode=False).strip().lower()
    return label if label in TAGS else ""


def classify_item(item: Dict, judge: Optional[Judge] = None) -> str:
    tag = rule_tag(item)
    if tag:
        return tag
    if judge is not None:
        label = str(judge(item) or "").strip().lower()
        return label if label in TAGS else ""
    return llm_human_judge(item)


def _human_item(story: Dict, tag: str) -> Dict:
    item = {
        "id": story.get("id"),
        "headline": str(story.get("title") or story.get("headline") or "").strip(),
        "url": str(story.get("url") or "").strip(),
        "source": str(story.get("source") or "").strip(),
        "summary": str(story.get("summary") or "").strip(),
        "tag": tag,
        "meaning": MEANING[tag],
        "published_at": str(story.get("published_at") or ""),
    }
    cluster = story.get("cluster")
    if isinstance(cluster, dict) and (int(cluster.get("badge_count") or 0) > 1 or cluster.get("is_update")):
        item["cluster"] = cluster
    return item


def select_human_items(stories: Sequence[Dict], judge: Optional[Judge] = None) -> List[Dict]:
    """Return 2–4 human-side items, or nothing when the day is thin."""
    chosen: List[Dict] = []
    for story in stories:
        tag = classify_item(story, judge=judge)
        if not tag:
            continue
        chosen.append(_human_item(story, tag))
    if len(chosen) < HUMAN_MIN:
        return []
    chosen.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    picked: List[Dict] = []
    seen_tags = set()
    for item in chosen:
        if item["tag"] in seen_tags:
            continue
        picked.append(item)
        seen_tags.add(item["tag"])
        if len(picked) == HUMAN_MAX:
            return picked
    picked_ids = {id(item) for item in picked}
    for item in chosen:
        if id(item) in picked_ids:
            continue
        picked.append(item)
        if len(picked) == HUMAN_MAX:
            break
    return picked

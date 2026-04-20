"""
Semantic deduplication across news sources.

Runs after summarize_articles.py. For every summarized, unsent, not-yet-checked
article fetched within the lookback window:
  1. Embed title + summary + opinion via Gemini.
  2. Union-find cluster by pairwise cosine similarity >= threshold.
  3. For each cluster of size >= 2, ask Gemini to (a) confirm which articles
     are genuinely duplicates (same story AND overlapping takeaway) and
     (b) pick the strongest one as the winner.
  4. Flag losers via articles.is_duplicate_of; stamp dedup_checked_at on every
     evaluated article so subsequent runs skip them.

Losers remain in the DB for auditing; get_unsent_articles() filters them out
so they never reach the email.
"""

import os
import argparse
import json
import math
import time
from typing import Any, Dict, List

from dotenv import load_dotenv
from google import genai

import sys
sys.path.insert(0, '.')
from execution.database import (
    get_dedup_candidates,
    mark_article_duplicate,
    mark_dedup_checked,
)

load_dotenv()

client = genai.Client()

EMBED_MODEL = os.getenv("DEDUP_EMBED_MODEL", "text-embedding-004")
JUDGE_MODEL = os.getenv("DEDUP_JUDGE_MODEL", "gemini-2.0-flash")

DEFAULT_JUDGE_PROMPT = """You are deduplicating AI news articles for a daily newsletter.
You will receive a cluster of articles that may cover the same story.

For each article, the ID, source, title, summary, and opinion/takeaway are provided.

Your job:
1. Group articles that ACTUALLY cover the same core story AND whose opinion, sentiment, or takeaway substantially overlap. Articles that share only a topic but offer distinctly different angles, perspectives, or conclusions are NOT duplicates — keep them in separate single-item groups.
2. Within each duplicate group of size >= 2, pick the single strongest article as the winner: clearest writing, most depth/detail, most insightful opinion. Prefer articles whose opinion adds unique analytical value over wire-report-style summaries.

Return STRICT JSON in this exact shape with no prose and no markdown code fences:
{"groups": [{"article_ids": [<int>, ...], "winner_id": <int>, "reason": "<short string, max 200 chars>"}, ...]}

Rules:
- Every article id from the input MUST appear in exactly one group.
- A group of size 1 is fine (article is unique); winner_id equals its only id and reason may be empty.
- For a group of size >= 2, winner_id MUST be one of the group's article_ids.
- `reason` briefly justifies why they are duplicates and why the winner was chosen."""

JUDGE_PROMPT = os.getenv("PROMPT_DEDUP", DEFAULT_JUDGE_PROMPT)


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Return one embedding vector per text. Uses google-genai embed_content."""
    result = client.models.embed_content(model=EMBED_MODEL, contents=texts)
    return [list(e.values) for e in result.embeddings]


def _cluster_by_similarity(
    articles: List[Dict[str, Any]],
    vectors: List[List[float]],
    threshold: float,
) -> List[List[Dict[str, Any]]]:
    """Union-find: any two articles with cosine >= threshold land in one cluster."""
    n = len(articles)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            if _cosine(vectors[i], vectors[j]) >= threshold:
                union(i, j)

    buckets: Dict[int, List[Dict[str, Any]]] = {}
    for i in range(n):
        buckets.setdefault(find(i), []).append(articles[i])
    return list(buckets.values())


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()
    return t


def _judge_cluster(cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ask Gemini to verdict duplicates within a cluster. Falls back to keeping all on parse error."""
    items = [
        {
            "id": a["id"],
            "source": a.get("source", ""),
            "title": a.get("title", ""),
            "summary": (a.get("summary") or "")[:600],
            "opinion": (a.get("opinion") or "")[:400],
        }
        for a in cluster
    ]
    prompt = f"{JUDGE_PROMPT}\n\nArticles:\n{json.dumps(items, ensure_ascii=False)}"
    try:
        response = client.models.generate_content(
            model=JUDGE_MODEL,
            contents=prompt,
        )
        text = _strip_json_fences(response.text or "")
        return json.loads(text)
    except Exception as exc:
        print(f"    ! Judge call/parse failed ({type(exc).__name__}): keeping cluster as singletons")
        return {
            "groups": [
                {"article_ids": [a["id"]], "winner_id": a["id"], "reason": ""}
                for a in cluster
            ]
        }


def run(lookback_hours: int, threshold: float, dry_run: bool = False, limit: int = None) -> int:
    articles = get_dedup_candidates(lookback_hours=lookback_hours)
    if limit:
        articles = articles[:limit]

    print(f"\n{'=' * 50}")
    print(f"Dedup: {len(articles)} candidate(s), threshold={threshold}, lookback={lookback_hours}h")
    print(f"{'=' * 50}\n")

    if len(articles) < 2:
        if articles and not dry_run:
            mark_dedup_checked([a["id"] for a in articles])
        print("Nothing to compare.")
        return 0

    texts = [
        f"{a.get('title', '')}\n{a.get('summary') or ''}\n{a.get('opinion') or ''}"
        for a in articles
    ]
    try:
        vectors = _embed_texts(texts)
    except Exception as exc:
        print(f"Embedding failed ({type(exc).__name__}: {exc}); aborting dedup pass.")
        return 0

    clusters = _cluster_by_similarity(articles, vectors, threshold)
    multi = [c for c in clusters if len(c) > 1]
    singletons = [c[0] for c in clusters if len(c) == 1]
    print(f"  {len(multi)} candidate cluster(s), {len(singletons)} singleton(s)")

    duplicates_marked = 0
    checked_ids: List[int] = [a["id"] for a in singletons]

    for cluster in multi:
        ids_in = [a["id"] for a in cluster]
        print(f"\n  Cluster ids={ids_in}")
        for a in cluster:
            print(f"    [{a['id']}] {a.get('source', '')}: {a.get('title', '')[:70]}")

        if dry_run:
            checked_ids.extend(ids_in)
            continue

        verdict = _judge_cluster(cluster)
        seen_in_verdict: set = set()
        for group in verdict.get("groups", []):
            try:
                group_ids = [int(x) for x in group.get("article_ids", [])]
            except (TypeError, ValueError):
                continue
            if not group_ids:
                continue
            try:
                winner = int(group.get("winner_id", group_ids[0]))
            except (TypeError, ValueError):
                winner = group_ids[0]
            if winner not in group_ids:
                winner = group_ids[0]
            reason = (group.get("reason") or "").strip()

            seen_in_verdict.update(group_ids)
            if len(group_ids) > 1:
                for lid in group_ids:
                    if lid != winner:
                        mark_article_duplicate(lid, winner, reason)
                        duplicates_marked += 1
                        print(f"    ✗ {lid} duplicate_of {winner} — {reason[:80]}")
                checked_ids.append(winner)
            else:
                checked_ids.append(group_ids[0])

        # Safety net: any cluster id the judge silently dropped should still be stamped.
        for aid in ids_in:
            if aid not in seen_in_verdict:
                checked_ids.append(aid)

        time.sleep(0.5)

    if not dry_run and checked_ids:
        # de-dupe the stamp list
        mark_dedup_checked(list(dict.fromkeys(checked_ids)))

    print(f"\nMarked {duplicates_marked} duplicate(s).")
    return duplicates_marked


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Semantic deduplication of news articles")
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=int(os.getenv("DEDUP_LOOKBACK_HOURS", "24")),
        help="Only consider articles fetched within this many hours (default 24)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.getenv("DEDUP_SIMILARITY_THRESHOLD", "0.75")),
        help="Cosine similarity threshold for clustering candidates (default 0.75)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print only, do not write to DB")
    parser.add_argument("--limit", type=int, default=None, help="Max candidates to process")
    args = parser.parse_args()

    if not os.getenv("GEMINI_API_KEY"):
        print("GEMINI_API_KEY not set in .env")
        exit(1)

    n = run(
        lookback_hours=args.lookback_hours,
        threshold=args.threshold,
        dry_run=args.dry_run,
        limit=args.limit,
    )
    print(f"Done. {n} duplicate(s) marked.")

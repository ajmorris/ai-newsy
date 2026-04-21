"""
Generate Reddit/HN/YC headlines for digest extras.
"""

import argparse
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests
from dotenv import load_dotenv

import sys
sys.path.insert(0, ".")
from execution.ai_client import generate_text_with_fallback
from execution.database import upsert_digest_extra

load_dotenv()

SKILL_PATH = Path(".skills/headlines-SKILL.md")


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"Invalid {name}={raw!r}; using default {default}")
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"Invalid {name}={raw!r}; using default {default}")
        return default


def _env_str(name: str, default: str) -> str:
    raw = (os.getenv(name) or "").strip()
    return raw or default


def _sanitize_date(value: Optional[str]) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).date().isoformat()


def _canonicalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return url.strip().lower()
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    clean_query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source"}
    ]
    query = urlencode(clean_query, doseq=True)
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower() or "https", host, path, "", query, ""))


def _tokenize(text: str) -> Set[str]:
    words = re.findall(r"[a-z0-9]{3,}", (text or "").lower())
    stop_words = {
        "about", "after", "also", "been", "from", "have", "into", "just", "more",
        "only", "over", "that", "their", "there", "they", "this", "very", "with",
        "your", "what", "when", "will", "would", "than", "them", "were", "does",
        "dont", "cant", "http", "https", "reddit", "hacker", "news", "show", "ask",
    }
    return {word for word in words if word not in stop_words}


def _jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _normalize_anchor(headline: str) -> str:
    normalized = re.sub(r"\*\*(.+?)\*\*", r"__\1__", headline or "")
    return normalized.replace("**", "").strip()


def load_skill_prompt(skill_path: Path = SKILL_PATH) -> str:
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill prompt not found at {skill_path}")
    return skill_path.read_text(encoding="utf-8").strip()


def _subreddit_allowlist() -> Set[str]:
    raw = _env_str(
        "COMMUNITY_SUBREDDITS",
        "MachineLearning,artificial,LocalLLaMA,OpenAI,singularity",
    )
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _parse_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def fetch_reddit_posts(limit: int, hours: int) -> List[dict]:
    headers = {"User-Agent": _env_str("REDDIT_USER_AGENT", "ai-newsy-digest/1.0")}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    allowlist = _subreddit_allowlist()
    per_subreddit = max(5, min(50, max(1, limit // max(len(allowlist), 1))))
    posts: List[dict] = []

    for subreddit in sorted(allowlist):
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={per_subreddit}"
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            print(f"Reddit fetch failed for r/{subreddit}: {exc}")
            continue

        children = data.get("data", {}).get("children", [])
        for child in children:
            item = (child or {}).get("data", {})
            created = datetime.fromtimestamp(item.get("created_utc", 0), tz=timezone.utc)
            if created < cutoff:
                continue
            subreddit_name = (item.get("subreddit") or "").lower()
            if subreddit_name not in allowlist:
                continue
            permalink = item.get("permalink") or ""
            url_value = item.get("url_overridden_by_dest") or item.get("url") or ""
            posts.append(
                {
                    "item_id": f"reddit:{item.get('id', '')}",
                    "created_time": _parse_timestamp(item.get("created_utc", 0)),
                    "author": item.get("author") or "Unknown",
                    "text": item.get("title") or "",
                    "url": url_value or f"https://reddit.com{permalink}",
                    "source_type": "reddit",
                    "source_label": f"Reddit r/{subreddit_name}",
                    "subreddit": subreddit_name,
                }
            )
            if len(posts) >= limit:
                return posts
    return posts[:limit]


def fetch_hn_posts(limit: int, hours: int) -> List[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    params = {"tags": "story", "hitsPerPage": str(min(max(limit, 20), 200))}
    posts: List[dict] = []
    try:
        response = requests.get(
            "https://hn.algolia.com/api/v1/search_by_date",
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        hits = response.json().get("hits", [])
    except Exception as exc:
        print(f"HN fetch failed: {exc}")
        return []

    for hit in hits:
        created_raw = hit.get("created_at")
        if not created_raw:
            continue
        created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        if created < cutoff:
            continue
        title = (hit.get("title") or "").strip()
        if not title:
            continue
        hn_url = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
        url_value = hit.get("url") or hn_url
        posts.append(
            {
                "item_id": f"hn:{hit.get('objectID', '')}",
                "created_time": created.isoformat(),
                "author": hit.get("author") or "Unknown",
                "text": title,
                "url": url_value,
                "source_type": "hacker_news",
                "source_label": "Hacker News",
            }
        )
        if len(posts) >= limit:
            break
    return posts


def fetch_yc_posts(limit: int, hours: int) -> List[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    feed_url = _env_str("YC_RSS_URL", "https://www.ycombinator.com/blog/feed")
    posts: List[dict] = []
    try:
        parsed = feedparser.parse(feed_url)
    except Exception as exc:
        print(f"YC fetch failed: {exc}")
        return []

    for entry in parsed.entries:
        struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if struct:
            created = datetime(*struct[:6], tzinfo=timezone.utc)
        else:
            created = datetime.now(timezone.utc)
        if created < cutoff:
            continue
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        posts.append(
            {
                "item_id": f"yc:{entry.get('id', entry.get('link', title))}",
                "created_time": created.isoformat(),
                "author": entry.get("author", "Y Combinator"),
                "text": title,
                "url": entry.get("link", ""),
                "source_type": "yc",
                "source_label": "Y Combinator",
            }
        )
        if len(posts) >= limit:
            break
    return posts


def fetch_recent_community_items(limit: int, hours: int) -> List[dict]:
    source_limit = max(5, limit // 3)
    rows = []
    rows.extend(fetch_reddit_posts(limit=source_limit, hours=hours))
    rows.extend(fetch_hn_posts(limit=source_limit, hours=hours))
    rows.extend(fetch_yc_posts(limit=source_limit, hours=hours))
    rows.sort(key=lambda item: item.get("created_time", ""), reverse=True)
    return rows[:limit]


def _build_generation_prompt(skill_prompt: str, items: List[dict]) -> str:
    blocks = []
    for item in items:
        blocks.append(
            "\n".join(
                [
                    f"ITEM_ID: {item.get('item_id', '')}",
                    f"SOURCE: {item.get('source_label', '')}",
                    f"AUTHOR: {item.get('author', 'Unknown')}",
                    f"URL: {item.get('url', '')}",
                    f"TEXT: {item.get('text', '')}",
                ]
            )
        )

    rows_blob = "\n\n---\n\n".join(blocks)
    return (
        f"{skill_prompt}\n\n"
        "Generate headlines for these community posts.\n"
        "Output requirements (strict):\n"
        "1. One line per included post.\n"
        "2. Format: ITEM_ID|HEADLINE\n"
        "3. HEADLINE must include exactly one __anchor phrase__ wrapped in double underscores.\n"
        "4. Omit low-signal posts entirely.\n"
        "5. No markdown bullets, numbering, or preamble.\n\n"
        f"{rows_blob}"
    )


def generate_headlines_for_items(items: List[dict], skill_prompt: str) -> List[dict]:
    if not items:
        return []
    prompt = _build_generation_prompt(skill_prompt, items)
    model_name = _env_str("COMMUNITY_HEADLINES_MODEL", "gemini-2.0-flash")
    text = generate_text_with_fallback(prompt=prompt, gemini_model=model_name)
    item_index = {item["item_id"]: item for item in items}
    headlines: List[dict] = []

    for line in text.splitlines():
        if "|" not in line:
            continue
        item_id, headline = line.split("|", 1)
        item_id = item_id.strip()
        headline = _normalize_anchor(headline.strip().lstrip("-").strip())
        if not item_id or not headline:
            continue
        source = item_index.get(item_id)
        if not source:
            continue
        headlines.append(
            {
                "item_id": item_id,
                "headline": headline,
                "url": source.get("url", ""),
                "author": source.get("author", "Unknown"),
                "created_time": source.get("created_time", ""),
                "source_text": source.get("text", ""),
                "source_type": source.get("source_type", ""),
                "source_label": source.get("source_label", ""),
                "subreddit": source.get("subreddit"),
            }
        )
    return headlines


def _learning_value_score(item: dict) -> int:
    merged = f"{(item.get('headline') or '').lower()} {(item.get('source_text') or '').lower()}"
    score = 0
    if re.search(r"\d", merged):
        score += 1
    if len(_tokenize(merged)) >= 8:
        score += 1
    insight_keywords = {
        "benchmark", "guide", "explain", "how", "lessons", "learned", "analysis",
        "breakdown", "workflow", "case", "study", "mistake", "experiment", "result",
        "prompt", "design", "tradeoff", "latency", "accuracy", "security", "launch",
    }
    if any(keyword in merged for keyword in insight_keywords):
        score += 1
    low_signal_patterns = ["check this out", "follow me", "new post", "watch this", "hot take"]
    if any(pattern in merged for pattern in low_signal_patterns):
        score -= 2
    return score


def _cluster_theme_headlines(items: List[dict], similarity_threshold: float) -> List[List[dict]]:
    clusters: List[List[dict]] = []
    centroids: List[Set[str]] = []
    for item in items:
        tokens = _tokenize(f"{item.get('headline', '')} {item.get('source_text', '')}")
        item["theme_tokens"] = tokens
        placed = False
        for idx, centroid in enumerate(centroids):
            if _jaccard_similarity(tokens, centroid) >= similarity_threshold:
                clusters[idx].append(item)
                centroids[idx] = centroid | tokens
                placed = True
                break
        if not placed:
            clusters.append([item])
            centroids.append(set(tokens))
    return clusters


def _distinct_take(candidate: dict, chosen: List[dict], threshold: float) -> bool:
    candidate_tokens = candidate.get("theme_tokens", set())
    if not candidate_tokens:
        return False
    chosen_tokens: Set[str] = set()
    for item in chosen:
        chosen_tokens |= item.get("theme_tokens", set())
    novelty = len(candidate_tokens - chosen_tokens) / max(len(candidate_tokens), 1)
    if novelty >= threshold:
        return True
    candidate_url = _canonicalize_url(candidate.get("url", ""))
    chosen_urls = {_canonicalize_url(item.get("url", "")) for item in chosen}
    return bool(candidate_url) and candidate_url not in chosen_urls and novelty >= (threshold * 0.6)


def curate_headlines(
    headlines: List[dict],
    max_headlines: int,
    min_learning_score: int,
    theme_similarity_threshold: float,
    max_per_theme: int,
    distinctness_threshold: float,
) -> List[dict]:
    deduped: List[dict] = []
    seen_headlines: Set[str] = set()
    seen_urls: Set[str] = set()
    for item in headlines:
        normalized_headline = re.sub(r"\s+", " ", item.get("headline", "")).strip().lower()
        canonical_url = _canonicalize_url(item.get("url", ""))
        if not normalized_headline:
            continue
        if normalized_headline in seen_headlines:
            continue
        if canonical_url and canonical_url in seen_urls:
            continue
        item["canonical_url"] = canonical_url
        seen_headlines.add(normalized_headline)
        if canonical_url:
            seen_urls.add(canonical_url)
        deduped.append(item)

    learning_scores = Counter()
    learning_pass: List[dict] = []
    for item in deduped:
        score = _learning_value_score(item)
        item["learning_score"] = score
        learning_scores[score] += 1
        if score >= min_learning_score:
            learning_pass.append(item)

    clusters = _cluster_theme_headlines(learning_pass, similarity_threshold=theme_similarity_threshold)
    selected: List[dict] = []
    for cluster in clusters:
        ranked = sorted(
            cluster,
            key=lambda item: (item.get("learning_score", 0), item.get("created_time", "")),
            reverse=True,
        )
        if not ranked:
            continue
        chosen = [ranked[0]]
        for candidate in ranked[1:]:
            if len(chosen) >= max_per_theme:
                break
            if _distinct_take(candidate, chosen, threshold=distinctness_threshold):
                chosen.append(candidate)
        selected.extend(chosen)

    selected.sort(
        key=lambda item: (item.get("learning_score", 0), item.get("created_time", "")),
        reverse=True,
    )
    print(
        "Community headline curation: "
        f"raw={len(headlines)}, deduped={len(deduped)}, learning_pass={len(learning_pass)}, "
        f"clusters={len(clusters)}, final={len(selected)}"
    )
    print(
        "Learning score distribution: "
        + ", ".join(f"{score}:{count}" for score, count in sorted(learning_scores.items()))
    )
    curated = []
    for item in selected[:max_headlines]:
        serialized_item = dict(item)
        serialized_item.pop("theme_tokens", None)
        curated.append(serialized_item)
    return curated


def persist_headlines(headlines: List[dict], source_count: int, digest_date: str) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": source_count,
        "headline_count": len(headlines),
        "headlines": headlines,
    }
    upsert_digest_extra(digest_date=digest_date, key="community_headlines", payload=payload)


def main(hours: int, limit: int, max_headlines: int, digest_date: Optional[str], dry_run: bool) -> None:
    safe_date = _sanitize_date(digest_date)
    print(f"Generating community headlines for digest date: {safe_date}")
    items = fetch_recent_community_items(limit=limit, hours=hours)
    print(f"Fetched {len(items)} community posts (Reddit/HN/YC)")

    if not items:
        if not dry_run:
            persist_headlines([], source_count=0, digest_date=safe_date)
        print("No community posts found in selected window; stored empty payload.")
        return

    skill_prompt = load_skill_prompt()
    headlines = generate_headlines_for_items(items, skill_prompt=skill_prompt)
    headlines = curate_headlines(
        headlines=headlines,
        max_headlines=max_headlines,
        min_learning_score=_env_int("COMMUNITY_MIN_LEARNING_SCORE", 2),
        theme_similarity_threshold=_env_float("COMMUNITY_THEME_SIMILARITY_THRESHOLD", 0.38),
        max_per_theme=_env_int("COMMUNITY_MAX_PER_THEME", 2),
        distinctness_threshold=_env_float("COMMUNITY_DISTINCTNESS_THRESHOLD", 0.45),
    )
    print(f"Generated {len(headlines)} curated community headlines")

    if dry_run:
        for item in headlines:
            print(f"- [{item.get('source_label', 'Community')}] {item.get('headline')} ({item.get('url', '')})")
        return

    persist_headlines(headlines=headlines, source_count=len(items), digest_date=safe_date)
    print("Stored community headlines in digest_extras")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate community headlines from Reddit/HN/YC")
    parser.add_argument("--hours", type=int, default=_env_int("COMMUNITY_LOOKBACK_HOURS", 24))
    parser.add_argument("--limit", type=int, default=_env_int("COMMUNITY_FETCH_LIMIT", 120))
    parser.add_argument("--max-headlines", type=int, default=_env_int("COMMUNITY_MAX_HEADLINES", 12))
    parser.add_argument("--digest-date", type=str, default=None, help="YYYY-MM-DD (UTC)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        main(
            hours=args.hours,
            limit=args.limit,
            max_headlines=args.max_headlines,
            digest_date=args.digest_date,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"Community headline generation failed: {exc}")
        raise

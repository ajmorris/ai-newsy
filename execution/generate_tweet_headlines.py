"""
Generate daily tweet headlines for digest extras.

Pipeline:
1. Pull Notion rows from the last 24 hours (by Notion created_time).
2. Normalize tweet fields (author/text/url).
3. Apply headline-writing skill guidance via Gemini.
4. Persist generated bullets for today's digest send.
"""

import argparse
from collections import Counter
import inspect
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv
from google import genai
import notion_client
from notion_client import Client as NotionClient

import sys
sys.path.insert(0, '.')
from execution.database import upsert_digest_extra

load_dotenv()

client = genai.Client()

SKILL_PATH = Path(".skills/headlines-SKILL.md")
# Debug log is opt-in via DEBUG_LOG_PATH env var. Absent/unwritable paths
# become silent no-ops so the script still runs in GitHub Actions.
_DEBUG_LOG_ENV = os.getenv("DEBUG_LOG_PATH", "").strip()
DEBUG_LOG_PATH: Optional[Path] = Path(_DEBUG_LOG_ENV) if _DEBUG_LOG_ENV else None
DEBUG_SESSION_ID = "9f6bd3"


def _debug_log(hypothesis_id: str, location: str, message: str, data: Dict) -> None:
    # region agent log
    if DEBUG_LOG_PATH is None:
        return
    payload = {
        "sessionId": DEBUG_SESSION_ID,
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except OSError:
        # Swallow logging errors so they never break the pipeline.
        pass
    # endregion


def _first_rich_text_plain(rich_text: list) -> str:
    if not rich_text:
        return ""
    parts = [chunk.get("plain_text", "") for chunk in rich_text if isinstance(chunk, dict)]
    return "".join(parts).strip()


def _extract_page_text(properties: Dict) -> str:
    text_candidates = ["text", "tweet", "content", "body", "post"]
    for name, value in properties.items():
        prop_name = name.lower()
        if not isinstance(value, dict):
            continue
        if value.get("type") == "title":
            maybe = _first_rich_text_plain(value.get("title", []))
            if prop_name in text_candidates and maybe:
                return maybe
        if value.get("type") == "rich_text":
            maybe = _first_rich_text_plain(value.get("rich_text", []))
            if any(key in prop_name for key in text_candidates) and maybe:
                return maybe

    # Fallback: first non-empty title or rich_text field.
    for value in properties.values():
        if not isinstance(value, dict):
            continue
        if value.get("type") == "title":
            maybe = _first_rich_text_plain(value.get("title", []))
            if maybe:
                return maybe
        if value.get("type") == "rich_text":
            maybe = _first_rich_text_plain(value.get("rich_text", []))
            if maybe:
                return maybe
    return ""


def _extract_page_author(properties: Dict) -> str:
    author_keys = ["author", "name", "person", "account", "creator", "handle"]
    for name, value in properties.items():
        prop_name = name.lower()
        if not any(key in prop_name for key in author_keys):
            continue
        if not isinstance(value, dict):
            continue
        ptype = value.get("type")
        if ptype == "rich_text":
            maybe = _first_rich_text_plain(value.get("rich_text", []))
            if maybe:
                return maybe
        if ptype == "title":
            maybe = _first_rich_text_plain(value.get("title", []))
            if maybe:
                return maybe
        if ptype == "people":
            people = value.get("people", [])
            if people:
                return people[0].get("name", "") or "Unknown"
        if ptype == "select" and value.get("select"):
            return value["select"].get("name", "") or "Unknown"
        if ptype == "url" and value.get("url"):
            url_value = value.get("url", "")
            return url_value.split("/")[-1] if "/" in url_value else url_value
    return "Unknown"


def _extract_page_url(properties: Dict) -> str:
    url_candidates = ["url", "link", "tweet"]
    for name, value in properties.items():
        prop_name = name.lower()
        if not isinstance(value, dict):
            continue
        if value.get("type") == "url" and value.get("url"):
            if any(key in prop_name for key in url_candidates):
                return value["url"].strip()
    # Fallback: any URL property.
    for value in properties.values():
        if isinstance(value, dict) and value.get("type") == "url" and value.get("url"):
            return value["url"].strip()
    return ""


def load_skill_prompt(skill_path: Path = SKILL_PATH) -> str:
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill prompt not found at {skill_path}")
    return skill_path.read_text(encoding="utf-8").strip()


def _lookback_start(hours: int, now: Optional[datetime] = None) -> datetime:
    anchor = now or datetime.now(timezone.utc)
    return anchor - timedelta(hours=hours)


def fetch_recent_tweets(limit: int = 100, hours: int = 24) -> List[dict]:
    notion_api_key = os.getenv("NOTION_API_KEY", "")
    notion_db_id = os.getenv("NOTION_TWEETS_DATABASE_ID", "")
    _debug_log(
        "H3",
        "generate_tweet_headlines.py:fetch_recent_tweets:env_check",
        "Validated required Notion env vars",
        {
            "has_notion_api_key": bool(notion_api_key),
            "has_notion_db_id": bool(notion_db_id),
            "db_id_length": len(notion_db_id or ""),
        },
    )
    if not notion_api_key or not notion_db_id:
        raise RuntimeError("NOTION_API_KEY and NOTION_TWEETS_DATABASE_ID are required")

    notion = NotionClient(auth=notion_api_key)
    _debug_log(
        "H1",
        "generate_tweet_headlines.py:fetch_recent_tweets:client_init",
        "Inspected Notion SDK capabilities",
        {
            "notion_client_version": getattr(notion_client, "__version__", "unknown"),
            "has_databases_attr": hasattr(notion, "databases"),
            "has_data_sources_attr": hasattr(notion, "data_sources"),
            "has_databases_query": hasattr(getattr(notion, "databases", None), "query"),
            "has_data_sources_query": hasattr(getattr(notion, "data_sources", None), "query"),
        },
    )
    since = _lookback_start(hours=hours)
    cursor: Optional[str] = None
    rows: List[dict] = []
    query_mode = "unknown"
    resolved_data_source_id: Optional[str] = None

    if hasattr(getattr(notion, "databases", None), "query"):
        query_mode = "databases.query"
    elif hasattr(getattr(notion, "data_sources", None), "query"):
        query_mode = "data_sources.query"
        try:
            db_response = notion.databases.retrieve(database_id=notion_db_id)
            data_sources = db_response.get("data_sources", []) if isinstance(db_response, dict) else []
            if data_sources:
                resolved_data_source_id = data_sources[0].get("id")
        except Exception as exc:
            _debug_log(
                "H5",
                "generate_tweet_headlines.py:fetch_recent_tweets:resolve_data_source_error",
                "Failed resolving data source id from database",
                {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )

    _debug_log(
        "H5",
        "generate_tweet_headlines.py:fetch_recent_tweets:query_mode_selection",
        "Selected Notion query mode",
        {
            "query_mode": query_mode,
            "resolved_data_source_id_present": bool(resolved_data_source_id),
        },
    )

    while True:
        query_payload = {
            "page_size": min(limit, 100),
            "filter": {
                "timestamp": "created_time",
                "created_time": {"on_or_after": since.isoformat()},
            },
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        }
        if query_mode == "databases.query":
            query_payload["database_id"] = notion_db_id
        elif query_mode == "data_sources.query":
            query_payload["data_source_id"] = resolved_data_source_id or notion_db_id
        else:
            raise RuntimeError("No supported Notion query endpoint found on client")
        if cursor:
            query_payload["start_cursor"] = cursor

        _debug_log(
            "H4",
            "generate_tweet_headlines.py:fetch_recent_tweets:query_attempt",
            "Attempting query via notion.databases.query",
            {
                "payload_keys": sorted(query_payload.keys()),
                "has_start_cursor": bool(cursor),
                "query_mode": query_mode,
            },
        )
        try:
            if query_mode == "databases.query":
                response = notion.databases.query(**query_payload)
            else:
                ds_query = notion.data_sources.query
                _debug_log(
                    "H5",
                    "generate_tweet_headlines.py:fetch_recent_tweets:data_sources_signature",
                    "Captured data_sources.query signature",
                    {
                        "signature": str(inspect.signature(ds_query)),
                    },
                )
                response = ds_query(**query_payload)
        except Exception as exc:
            _debug_log(
                "H2",
                "generate_tweet_headlines.py:fetch_recent_tweets:query_error",
                "Notion query call failed",
                {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            raise
        for page in response.get("results", []):
            if len(rows) >= limit:
                break
            properties = page.get("properties", {})
            rows.append(
                {
                    "tweet_id": page.get("id", ""),
                    "created_time": page.get("created_time", ""),
                    "author": _extract_page_author(properties),
                    "text": _extract_page_text(properties),
                    "url": _extract_page_url(properties),
                }
            )

        if len(rows) >= limit or not response.get("has_more"):
            break
        cursor = response.get("next_cursor")

    return [row for row in rows if row.get("text")]


def _build_generation_prompt(skill_prompt: str, tweets: List[dict]) -> str:
    tweet_blocks = []
    for tweet in tweets:
        tweet_blocks.append(
            "\n".join(
                [
                    f"TWEET_ID: {tweet['tweet_id']}",
                    f"AUTHOR: {tweet.get('author', 'Unknown')}",
                    f"URL: {tweet.get('url', '')}",
                    f"TEXT: {tweet.get('text', '')}",
                ]
            )
        )

    rows_blob = "\n\n---\n\n".join(tweet_blocks)
    return (
        f"{skill_prompt}\n\n"
        "Generate headlines for these tweets.\n"
        "Output requirements (strict):\n"
        "1. One line per included tweet.\n"
        "2. Format: TWEET_ID|HEADLINE\n"
        "3. HEADLINE must include exactly one __anchor phrase__ wrapped in double underscores.\n"
        "   Example: The __anchor phrase__ is the only part that will be linked.\n"
        "   Do NOT use asterisks for emphasis (no **like this**).\n"
        "4. Omit low-signal tweets entirely.\n"
        "5. No markdown bullets, numbering, or preamble.\n\n"
        f"{rows_blob}"
    )


def _normalize_headline_anchors(headline: str) -> str:
    """
    Normalize any markdown-style **anchor** into __anchor__ and strip leftover asterisks.
    This keeps storage consistent and avoids resend rendering literal markdown.
    """
    normalized = re.sub(r"\*\*(.+?)\*\*", r"__\1__", headline)
    normalized = normalized.replace("**", "")
    return normalized.strip()


def generate_headlines_for_tweets(tweets: List[dict], skill_prompt: str) -> List[dict]:
    if not tweets:
        return []

    prompt = _build_generation_prompt(skill_prompt, tweets)
    model_name = _env_str("TWEET_HEADLINES_MODEL", "gemini-2.0-flash")
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    text = (response.text or "").strip()

    tweet_index = {tweet["tweet_id"]: tweet for tweet in tweets}
    headlines = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        tweet_id, raw_headline = line.split("|", 1)
        tweet_id = tweet_id.strip()
        raw_headline = _normalize_headline_anchors(raw_headline.strip().lstrip("-").strip())
        if not tweet_id or not raw_headline:
            continue
        source = tweet_index.get(tweet_id)
        if not source:
            continue
        headlines.append(
            {
                "tweet_id": tweet_id,
                "headline": raw_headline,
                "url": source.get("url", ""),
                "author": source.get("author", "Unknown"),
                "created_time": source.get("created_time", ""),
                "source_text": source.get("text", ""),
            }
        )
    return headlines


def _sanitize_date(value: Optional[str]) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).date().isoformat()


def _env_int(name: str, default: int) -> int:
    """
    Read an integer env var with safe fallback for empty/invalid values.
    """
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"Invalid {name}={raw!r}; using default {default}")
        return default


def _env_str(name: str, default: str) -> str:
    """
    Read a string env var with fallback for empty values.
    """
    raw = (os.getenv(name) or "").strip()
    return raw or default


def _env_float(name: str, default: float) -> float:
    """
    Read a float env var with safe fallback for empty/invalid values.
    """
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"Invalid {name}={raw!r}; using default {default}")
        return default


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
    if host == "x.com":
        host = "twitter.com"

    clean_query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source"}
    ]
    query = urlencode(clean_query, doseq=True)
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower() or "https", host, path, "", query, ""))


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _tokenize(text: str) -> Set[str]:
    words = re.findall(r"[a-z0-9]{3,}", (text or "").lower())
    stop_words = {
        "about", "after", "also", "been", "from", "have", "into", "just", "more",
        "only", "over", "that", "their", "there", "they", "this", "very", "with",
        "your", "what", "when", "will", "would", "than", "them", "were", "does",
        "dont", "cant", "http", "https", "twitter", "thread",
    }
    return {word for word in words if word not in stop_words}


def _jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _learning_value_score(item: dict) -> int:
    headline = (item.get("headline") or "").lower()
    tweet_text = (item.get("source_text") or "").lower()
    merged = f"{headline} {tweet_text}"
    score = 0

    if re.search(r"\d", merged):
        score += 1
    if len(_tokenize(merged)) >= 8:
        score += 1

    insight_keywords = {
        "benchmark", "guide", "explain", "how", "lessons", "learned", "analysis",
        "breakdown", "workflow", "case", "study", "mistake", "experiment", "result",
        "prompt", "design", "tradeoff", "latency", "accuracy", "security",
    }
    if any(keyword in merged for keyword in insight_keywords):
        score += 1

    low_signal_patterns = [
        "gm", "good morning", "follow me", "check this out", "big news", "coming soon",
        "new post", "new blog", "just dropped", "read this", "watch this",
    ]
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


def _log_tweet_window(tweets: List[dict], lookback_hours: int) -> None:
    parsed_times = [
        dt
        for dt in (_parse_datetime(tweet.get("created_time", "")) for tweet in tweets)
        if dt is not None
    ]
    if not parsed_times:
        print(f"Lookback configured to {lookback_hours}h; no parseable tweet timestamps found.")
        return
    newest = max(parsed_times)
    oldest = min(parsed_times)
    print(
        f"Lookback configured to {lookback_hours}h; fetched window spans "
        f"{oldest.isoformat()} to {newest.isoformat()} ({len(parsed_times)} timestamped rows)."
    )


def persist_headlines(headlines: List[dict], source_count: int, digest_date: str) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": source_count,
        "headline_count": len(headlines),
        "headlines": headlines,
    }
    upsert_digest_extra(digest_date=digest_date, key="tweet_headlines", payload=payload)


def curate_headlines(
    headlines: List[dict],
    max_headlines: int,
    min_learning_score: int,
    theme_similarity_threshold: float,
    max_per_theme: int,
    distinctness_threshold: float,
) -> List[dict]:
    if not headlines:
        return []

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

    learning_pass: List[dict] = []
    learning_scores = Counter()
    for item in deduped:
        score = _learning_value_score(item)
        item["learning_score"] = score
        learning_scores[score] += 1
        if score >= min_learning_score:
            learning_pass.append(item)

    clusters = _cluster_theme_headlines(
        learning_pass,
        similarity_threshold=theme_similarity_threshold,
    )
    selected: List[dict] = []
    for cluster in clusters:
        ranked = sorted(
            cluster,
            key=lambda item: (
                item.get("learning_score", 0),
                item.get("created_time", ""),
            ),
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
        key=lambda item: (
            item.get("learning_score", 0),
            item.get("created_time", ""),
        ),
        reverse=True,
    )

    print(
        "Headline curation: "
        f"raw={len(headlines)}, deduped={len(deduped)}, "
        f"learning_pass={len(learning_pass)}, clusters={len(clusters)}, final={len(selected)}"
    )
    print(
        "Learning score distribution: "
        + ", ".join(f"{score}:{count}" for score, count in sorted(learning_scores.items()))
    )

    return selected[:max_headlines]


def main(hours: int, limit: int, max_headlines: int, digest_date: Optional[str], dry_run: bool) -> None:
    safe_date = _sanitize_date(digest_date)
    print(f"Generating tweet headlines for digest date: {safe_date}")
    tweets = fetch_recent_tweets(limit=limit, hours=hours)
    print(f"Fetched {len(tweets)} tweets from Notion")
    _log_tweet_window(tweets, lookback_hours=hours)

    if not tweets:
        if not dry_run:
            persist_headlines([], source_count=0, digest_date=safe_date)
        print("No tweets found in the selected window; stored empty payload.")
        return

    skill_prompt = load_skill_prompt()
    headlines = generate_headlines_for_tweets(tweets, skill_prompt=skill_prompt)
    headlines = curate_headlines(
        headlines,
        max_headlines=max_headlines,
        min_learning_score=_env_int("TWEET_MIN_LEARNING_SCORE", 2),
        theme_similarity_threshold=_env_float("TWEET_THEME_SIMILARITY_THRESHOLD", 0.38),
        max_per_theme=_env_int("TWEET_MAX_PER_THEME", 2),
        distinctness_threshold=_env_float("TWEET_DISTINCTNESS_THRESHOLD", 0.45),
    )
    print(f"Generated {len(headlines)} curated headlines")

    if dry_run:
        for item in headlines:
            print(f"- {item['headline']} ({item.get('url', 'no-url')})")
        return

    persist_headlines(headlines, source_count=len(tweets), digest_date=safe_date)
    print("Stored tweet headlines in digest_extras")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate tweet headlines from Notion rows")
    parser.add_argument("--hours", type=int, default=_env_int("TWEET_LOOKBACK_HOURS", 24))
    parser.add_argument("--limit", type=int, default=_env_int("TWEET_FETCH_LIMIT", 100))
    parser.add_argument(
        "--max-headlines",
        type=int,
        default=_env_int("TWEET_MAX_HEADLINES", 12),
    )
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
        print(f"Tweet headline generation failed: {exc}")
        # Non-zero for workflow observability; sender still has runtime fallback for missing extras.
        raise

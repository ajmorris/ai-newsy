"""
Database helper module for AI Newsy.
Uses Supabase (PostgreSQL) for persistent storage.
"""

import os
import secrets
import json
import time
import base64
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Debug log is opt-in via DEBUG_LOG_PATH env var. Absent/unwritable paths
# become silent no-ops so the module still loads in GitHub Actions.
_DEBUG_LOG_ENV = os.getenv("DEBUG_LOG_PATH", "").strip()
DEBUG_LOG_PATH: Optional[Path] = Path(_DEBUG_LOG_ENV) if _DEBUG_LOG_ENV else None
DEBUG_SESSION_ID = "9f6bd3"


def _debug_log(hypothesis_id: str, location: str, message: str, data: Dict[str, Any]) -> None:
    # region agent log
    if DEBUG_LOG_PATH is None:
        return
    payload = {
        "sessionId": DEBUG_SESSION_ID,
        "runId": "pre-fix-rls",
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


def _jwt_role_from_key(key: str) -> str:
    try:
        parts = key.split(".")
        if len(parts) != 3:
            return "unknown"
        payload_part = parts[1]
        padding = "=" * (-len(payload_part) % 4)
        decoded = base64.urlsafe_b64decode(payload_part + padding).decode("utf-8")
        claims = json.loads(decoded)
        return str(claims.get("role", "unknown"))
    except Exception:
        return "unknown"

def _resolve_supabase_key() -> str:
    """Prefer service role key for backend write operations."""
    service_role = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if service_role:
        return service_role
    return os.getenv("SUPABASE_KEY", "")


# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    _resolve_supabase_key(),
)


# ===========================================
# SUBSCRIBER OPERATIONS
# ===========================================

def add_subscriber(email: str) -> dict:
    """
    Add a new subscriber with a confirmation token.
    Returns the subscriber record or raises if email exists.
    """
    token = secrets.token_urlsafe(32)
    result = supabase.table("subscribers").insert({
        "email": email.lower().strip(),
        "confirm_token": token,
        "confirmed": False,
        "subscribed_at": datetime.utcnow().isoformat()
    }).execute()
    return result.data[0] if result.data else {}


def confirm_subscriber(token: str) -> Optional[dict]:
    """
    Confirm a subscriber by their token.
    Returns the updated subscriber or None if token not found.
    """
    result = supabase.table("subscribers").update({
        "confirmed": True
    }).eq("confirm_token", token).eq("confirmed", False).execute()
    return result.data[0] if result.data else None


def unsubscribe(token: str) -> Optional[dict]:
    """
    Unsubscribe a user by their token.
    Sets unsubscribed_at timestamp.
    """
    result = supabase.table("subscribers").update({
        "unsubscribed_at": datetime.utcnow().isoformat()
    }).eq("confirm_token", token).execute()
    return result.data[0] if result.data else None


def get_active_subscribers() -> list:
    """
    Get all confirmed subscribers who haven't unsubscribed.
    """
    result = supabase.table("subscribers").select("*").eq(
        "confirmed", True
    ).is_("unsubscribed_at", "null").execute()
    return result.data or []


def subscriber_exists(email: str) -> bool:
    """Check if an email is already subscribed."""
    result = supabase.table("subscribers").select("id").eq(
        "email", email.lower().strip()
    ).execute()
    return len(result.data) > 0


# ===========================================
# ARTICLE OPERATIONS
# ===========================================

def add_article(
    url: str,
    title: str,
    source: str,
    content: str = "",
    published_at: Optional[str] = None,
) -> Optional[dict]:
    """
    Add a new article if URL doesn't exist (deduplication).
    Returns the article or None if already exists.
    """
    # Check for existing
    existing = supabase.table("articles").select("id").eq("url", url).execute()
    if existing.data:
        return None  # Already exists

    now_iso = datetime.utcnow().isoformat()
    pub_iso = published_at or now_iso

    result = supabase.table("articles").insert({
        "url": url,
        "title": title,
        "source": source,
        "content": content,
        "fetched_at": now_iso,
        "published_at": pub_iso,
    }).execute()
    return result.data[0] if result.data else None


def get_unsummarized_articles() -> list:
    """Get articles that haven't been summarized yet."""
    result = supabase.table("articles").select("*").is_(
        "summary", "null"
    ).execute()
    return result.data or []


def update_article_summary(article_id: int, summary: str) -> dict:
    """Update an article with its AI-generated summary."""
    result = supabase.table("articles").update({
        "summary": summary
    }).eq("id", article_id).execute()
    return result.data[0] if result.data else {}


def update_article_image(article_id: int, image_url: str) -> None:
    """Set image_url for an article (e.g. og:image from page)."""
    supabase.table("articles").update({
        "image_url": image_url
    }).eq("id", article_id).execute()


def get_unsent_articles(
    topic: Optional[str] = None,
    require_summary: bool = True,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list:
    """
    Get articles that haven't been sent yet.
    If topic is set, filter to that topic only.
    If require_summary is True, only return articles that have been summarized.
    If since/until are provided, constrain by fetched_at time window (UTC).
    """
    query = supabase.table("articles").select("*").is_("sent_at", "null").is_(
        "is_duplicate_of", "null"
    )
    if require_summary:
        query = query.not_.is_("summary", "null")
    if topic is not None:
        query = query.eq("topic", topic)
    if since is not None:
        query = query.gte("published_at", since.isoformat())
    if until is not None:
        query = query.lte("published_at", until.isoformat())
    result = query.execute()
    return result.data or []


def get_sent_articles(
    require_summary: bool = True,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list:
    """
    Get articles that have already been sent.
    If require_summary is True, only return articles that have a summary.
    Time window filters apply to sent_at.
    """
    query = supabase.table("articles").select("*").not_.is_("sent_at", "null")
    if require_summary:
        query = query.not_.is_("summary", "null")
    if since is not None:
        query = query.gte("sent_at", since.isoformat())
    if until is not None:
        query = query.lt("sent_at", until.isoformat())
    result = query.execute()
    return result.data or []


def get_unsent_articles_with_topic_set() -> list:
    """Get unsent articles that have a topic set (for topic-based digest selection)."""
    result = supabase.table("articles").select("*").is_("sent_at", "null").not_.is_(
        "topic", "null"
    ).execute()
    return result.data or []


def get_articles_without_topic(limit: Optional[int] = None) -> list:
    """Get articles that have no topic set (for topic assignment at ingest)."""
    result = supabase.table("articles").select("*").is_("topic", "null").execute()
    data = result.data or []
    if limit:
        data = data[:limit]
    return data


def update_article_topic(article_id: int, topic: str) -> None:
    """Set topic for an article."""
    supabase.table("articles").update({"topic": topic}).eq("id", article_id).execute()


def get_unsent_articles_for_digest(
    max_per_source: int = 2,
    interleave: bool = True,
    topic: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list:
    """
    Get unsent articles with a cap per source for variety.
    When topic is set: returns articles with that topic (summary optional; use for JIT flow).
    When topic is None: returns only summarized articles (current behavior).
    Time window filters can be applied via since/until on published_at.
    Groups by source, takes at most max_per_source per source (newest by published_at).
    If interleave is True, returns articles in round-robin order by source.
    """
    from collections import defaultdict
    require_summary = topic is None
    all_articles = get_unsent_articles(
        topic=topic,
        require_summary=require_summary,
        since=since,
        until=until,
    )
    by_source = defaultdict(list)
    for a in all_articles:
        by_source[a.get("source", "Unknown")].append(a)

    # Per source: keep newest max_per_source, sorted newest first
    capped = {}
    for source, articles in by_source.items():
        sorted_articles = sorted(
            articles,
            key=lambda x: x.get("published_at") or x.get("fetched_at") or "",
            reverse=True
        )
        capped[source] = sorted_articles[:max_per_source]

    if not interleave:
        result = []
        for articles in capped.values():
            result.extend(articles)
        result.sort(key=lambda x: x.get("published_at") or x.get("fetched_at") or "", reverse=True)
        return result

    # Round-robin by source so the same publication does not appear back-to-back
    result = []
    sources = sorted(capped.keys())
    idx = {s: 0 for s in sources}
    while True:
        added = False
        for s in sources:
            if idx[s] < len(capped[s]):
                result.append(capped[s][idx[s]])
                idx[s] += 1
                added = True
        if not added:
            break
    return result


def mark_articles_sent(article_ids: list) -> None:
    """Mark articles as sent."""
    sent_time = datetime.utcnow().isoformat()
    for article_id in article_ids:
        supabase.table("articles").update({
            "sent_at": sent_time
        }).eq("id", article_id).execute()


# ===========================================
# SEMANTIC DEDUPLICATION
# ===========================================

def get_dedup_candidates(lookback_hours: int = 24) -> list:
    """
    Return summarized, unsent, not-yet-checked articles fetched within the
    lookback window. These are the candidates a dedup pass will compare.
    """
    from datetime import timedelta
    since = (datetime.utcnow() - timedelta(hours=lookback_hours)).isoformat()
    query = (
        supabase.table("articles")
        .select("id, url, title, source, summary, opinion, published_at, fetched_at")
        .is_("sent_at", "null")
        .is_("is_duplicate_of", "null")
        .is_("dedup_checked_at", "null")
        .not_.is_("summary", "null")
        .gte("fetched_at", since)
    )
    result = query.execute()
    return result.data or []


def mark_article_duplicate(loser_id: int, winner_id: int, reason: str = "") -> None:
    """
    Flag an article as a duplicate of the winner. Also stamps dedup_checked_at
    so the loser is not re-evaluated on subsequent runs.
    """
    supabase.table("articles").update({
        "is_duplicate_of": winner_id,
        "dedup_reason": reason[:500] if reason else None,
        "dedup_checked_at": datetime.utcnow().isoformat(),
    }).eq("id", loser_id).execute()


def mark_dedup_checked(article_ids: list) -> None:
    """Stamp dedup_checked_at on articles that were evaluated (winners + singletons)."""
    if not article_ids:
        return
    checked_at = datetime.utcnow().isoformat()
    supabase.table("articles").update({
        "dedup_checked_at": checked_at,
    }).in_("id", list(article_ids)).execute()


# ===========================================
# DIGEST LOG (topic rotation)
# ===========================================

def insert_digest_log(topic: str) -> None:
    """Record which topic was used for a digest (for rotation)."""
    supabase.table("digests").insert({
        "topic": topic,
        "sent_at": datetime.utcnow().isoformat(),
    }).execute()


def upsert_digest_extra(digest_date: str, key: str, payload: Dict[str, Any]) -> dict:
    """
    Upsert supplemental digest data for a date/key pair.
    Example key: 'tweet_headlines'
    """
    _debug_log(
        "H6",
        "database.py:upsert_digest_extra:before_upsert",
        "Attempting digest_extras upsert",
        {
            "digest_date": digest_date,
            "key": key,
            "payload_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
            "supabase_key_role": _jwt_role_from_key(_resolve_supabase_key()),
            "using_service_role_key": bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")),
        },
    )
    try:
        result = supabase.table("digest_extras").upsert(
            {
                "digest_date": digest_date,
                "key": key,
                "payload": payload,
                "updated_at": datetime.utcnow().isoformat(),
            },
            on_conflict="digest_date,key",
        ).execute()
        _debug_log(
            "H8",
            "database.py:upsert_digest_extra:upsert_success",
            "digest_extras upsert succeeded",
            {"row_count": len(result.data or [])},
        )
        return result.data[0] if result.data else {}
    except Exception as exc:
        _debug_log(
            "H7",
            "database.py:upsert_digest_extra:upsert_failure",
            "digest_extras upsert failed",
            {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        raise


def get_digest_extra(digest_date: str, key: str) -> Optional[dict]:
    """Get supplemental digest data for a date/key pair."""
    result = supabase.table("digest_extras").select("*").eq(
        "digest_date", digest_date
    ).eq("key", key).limit(1).execute()
    if not result.data:
        return None
    return result.data[0]


def get_topics_used_in_last_k_days(k: int) -> list:
    """Return list of topics that appear in digests in the last k days (for rotation exclusion)."""
    from datetime import timedelta
    since = (datetime.utcnow() - timedelta(days=k)).isoformat()
    result = supabase.table("digests").select("topic").gte("sent_at", since).execute()
    if not result.data:
        return []
    return list({row["topic"] for row in result.data})


def get_article_count() -> int:
    """Get total count of articles in database."""
    result = supabase.table("articles").select("id", count="exact").execute()
    return result.count or 0


def delete_articles_older_than(days: int) -> int:
    """
    Delete articles whose fetched_at is older than the given number of days.
    Returns the number of rows deleted.
    """
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = supabase.table("articles").delete().lt("published_at", cutoff).execute()
    return len(result.data) if result.data else 0


if __name__ == "__main__":
    # Quick test
    print(f"Connected to Supabase: {os.getenv('SUPABASE_URL', 'NOT SET')[:30]}...")
    print(f"Total articles: {get_article_count()}")
    print(f"Active subscribers: {len(get_active_subscribers())}")

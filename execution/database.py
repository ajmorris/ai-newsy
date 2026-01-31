"""
Database helper module for AI Newsy.
Uses Supabase (PostgreSQL) for persistent storage.
"""

import os
import secrets
from datetime import datetime
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_KEY", "")
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

def add_article(url: str, title: str, source: str, content: str = "") -> Optional[dict]:
    """
    Add a new article if URL doesn't exist (deduplication).
    Returns the article or None if already exists.
    """
    # Check for existing
    existing = supabase.table("articles").select("id").eq("url", url).execute()
    if existing.data:
        return None  # Already exists
    
    result = supabase.table("articles").insert({
        "url": url,
        "title": title,
        "source": source,
        "content": content,
        "fetched_at": datetime.utcnow().isoformat()
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


def get_unsent_articles(topic: Optional[str] = None, require_summary: bool = True) -> list:
    """
    Get articles that haven't been sent yet.
    If topic is set, filter to that topic only.
    If require_summary is True, only return articles that have been summarized.
    """
    query = supabase.table("articles").select("*").is_("sent_at", "null")
    if require_summary:
        query = query.not_.is_("summary", "null")
    if topic is not None:
        query = query.eq("topic", topic)
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
) -> list:
    """
    Get unsent articles with a cap per source for variety.
    When topic is set: returns articles with that topic (summary optional; use for JIT flow).
    When topic is None: returns only summarized articles (current behavior).
    Groups by source, takes at most max_per_source per source (newest by fetched_at).
    If interleave is True, returns articles in round-robin order by source.
    """
    from collections import defaultdict
    require_summary = topic is None
    all_articles = get_unsent_articles(topic=topic, require_summary=require_summary)
    by_source = defaultdict(list)
    for a in all_articles:
        by_source[a.get("source", "Unknown")].append(a)

    # Per source: keep newest max_per_source, sorted newest first
    capped = {}
    for source, articles in by_source.items():
        sorted_articles = sorted(
            articles,
            key=lambda x: x.get("fetched_at") or "",
            reverse=True
        )
        capped[source] = sorted_articles[:max_per_source]

    if not interleave:
        result = []
        for articles in capped.values():
            result.extend(articles)
        result.sort(key=lambda x: x.get("fetched_at") or "", reverse=True)
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
# DIGEST LOG (topic rotation)
# ===========================================

def insert_digest_log(topic: str) -> None:
    """Record which topic was used for a digest (for rotation)."""
    supabase.table("digests").insert({
        "topic": topic,
        "sent_at": datetime.utcnow().isoformat(),
    }).execute()


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
    result = supabase.table("articles").delete().lt("fetched_at", cutoff).execute()
    return len(result.data) if result.data else 0


if __name__ == "__main__":
    # Quick test
    print(f"Connected to Supabase: {os.getenv('SUPABASE_URL', 'NOT SET')[:30]}...")
    print(f"Total articles: {get_article_count()}")
    print(f"Active subscribers: {len(get_active_subscribers())}")

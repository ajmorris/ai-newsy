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


def get_unsent_articles() -> list:
    """Get summarized articles that haven't been sent yet."""
    result = supabase.table("articles").select("*").not_.is_(
        "summary", "null"
    ).is_("sent_at", "null").execute()
    return result.data or []


def mark_articles_sent(article_ids: list) -> None:
    """Mark articles as sent."""
    sent_time = datetime.utcnow().isoformat()
    for article_id in article_ids:
        supabase.table("articles").update({
            "sent_at": sent_time
        }).eq("id", article_id).execute()


def get_article_count() -> int:
    """Get total count of articles in database."""
    result = supabase.table("articles").select("id", count="exact").execute()
    return result.count or 0


if __name__ == "__main__":
    # Quick test
    print(f"Connected to Supabase: {os.getenv('SUPABASE_URL', 'NOT SET')[:30]}...")
    print(f"Total articles: {get_article_count()}")
    print(f"Active subscribers: {len(get_active_subscribers())}")

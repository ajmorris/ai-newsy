"""
Fetch AI-related posts from X/Twitter accounts.
Uses Twitter API v2 to get recent tweets from configured accounts.
"""

import os
import argparse
import time
from datetime import datetime
import requests
from dotenv import load_dotenv

import sys
sys.path.insert(0, '.')
from execution.database import add_article, get_article_count

load_dotenv()

# X API configuration
BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")
X_ACCOUNTS = os.getenv("X_ACCOUNTS", "OpenAI,AnthropicAI,GoogleAI").split(",")

# API endpoints
BASE_URL = "https://api.twitter.com/2"


def get_headers():
    """Get authorization headers for X API."""
    return {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }


def get_user_id(username: str) -> str:
    """Get X user ID from username."""
    url = f"{BASE_URL}/users/by/username/{username}"
    response = requests.get(url, headers=get_headers())
    
    if response.status_code == 200:
        data = response.json()
        return data.get("data", {}).get("id")
    else:
        print(f"    Error getting user ID for @{username}: {response.status_code}")
        return None


def get_user_tweets(user_id: str, username: str, max_results: int = 10) -> list:
    """
    Get recent tweets from a user.
    Returns list of tweet dicts.
    """
    url = f"{BASE_URL}/users/{user_id}/tweets"
    params = {
        "max_results": min(max_results, 100),
        "tweet.fields": "created_at,text,public_metrics",
        "exclude": "retweets,replies"
    }
    
    response = requests.get(url, headers=get_headers(), params=params)
    
    if response.status_code == 200:
        data = response.json()
        tweets = data.get("data", [])
        
        articles = []
        for tweet in tweets:
            tweet_id = tweet.get("id")
            text = tweet.get("text", "")
            created_at = tweet.get("created_at", "")
            
            # Create tweet URL
            url = f"https://twitter.com/{username}/status/{tweet_id}"
            
            # Use first line or first 100 chars as title
            title = text.split('\n')[0][:100]
            if len(text) > 100:
                title += "..."
            
            articles.append({
                "url": url,
                "title": f"@{username}: {title}",
                "source": f"X (@{username})",
                "content": text
            })
        
        return articles
    else:
        print(f"    Error fetching tweets: {response.status_code} - {response.text[:200]}")
        return []


def fetch_all_accounts(limit_per_account: int = 5, dry_run: bool = False) -> int:
    """
    Fetch tweets from all configured X accounts.
    Returns total count of new articles added.
    """
    if not BEARER_TOKEN or BEARER_TOKEN == "your-twitter-bearer-token":
        print("⚠️  X_BEARER_TOKEN not configured. Skipping X/Twitter fetch.")
        print("   Get one at: https://developer.twitter.com/en/portal/dashboard")
        return 0
    
    print(f"\n{'='*50}")
    print(f"X/Twitter Fetch - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Accounts: {', '.join(['@' + a for a in X_ACCOUNTS])}")
    print(f"{'='*50}\n")
    
    total_new = 0
    total_found = 0
    
    for username in X_ACCOUNTS:
        username = username.strip()
        print(f"  Fetching: @{username}...")
        
        # Get user ID first
        user_id = get_user_id(username)
        if not user_id:
            continue
        
        # Get tweets
        articles = get_user_tweets(user_id, username, max_results=limit_per_account)
        total_found += len(articles)
        print(f"    Found {len(articles)} tweets")
        
        for article in articles:
            if dry_run:
                print(f"    [DRY RUN] Would add: {article['title'][:50]}...")
                total_new += 1
            else:
                result = add_article(
                    url=article['url'],
                    title=article['title'],
                    source=article['source'],
                    content=article['content']
                )
                if result:
                    print(f"    ✓ Added: {article['title'][:50]}...")
                    total_new += 1
        
        # Rate limit: 1 request per second
        time.sleep(1)
    
    print(f"\n{'='*50}")
    print(f"Summary: Found {total_found} tweets, added {total_new} new")
    print(f"Total articles in database: {get_article_count()}")
    print(f"{'='*50}\n")
    
    return total_new


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI posts from X/Twitter")
    parser.add_argument('--dry-run', action='store_true',
                        help="Print tweets without inserting")
    parser.add_argument('--limit', type=int, default=5,
                        help="Max tweets per account (default: 5)")
    args = parser.parse_args()
    
    new_count = fetch_all_accounts(
        limit_per_account=args.limit,
        dry_run=args.dry_run
    )
    
    print(f"Done! Added {new_count} new posts from X.")

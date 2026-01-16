"""
Summarize articles using AI (Google Gemini).
Gets unsummarized articles from database and generates concise summaries.
"""

import os
import argparse
import time
from dotenv import load_dotenv
import google.generativeai as genai

import sys
sys.path.insert(0, '.')
from execution.database import get_unsummarized_articles, update_article_summary

load_dotenv()

# Initialize Gemini client
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

# Summarization prompt
SYSTEM_PROMPT = """You are a concise tech news summarizer. Given an article title and content, write a 2-3 sentence summary that:
1. Captures the key news/announcement
2. Explains why it matters
3. Uses clear, accessible language

Keep it informative but brief - this is for a daily email digest. Just return the summary, no preamble."""


def summarize_article(title: str, content: str) -> str:
    """
    Generate a summary for a single article using Gemini.
    Returns the summary text.
    """
    try:
        prompt = f"{SYSTEM_PROMPT}\n\nTitle: {title}\n\nContent: {content}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"    Error summarizing: {e}")
        return ""


def summarize_all(dry_run: bool = False, limit: int = None) -> int:
    """
    Summarize all unsummarized articles.
    Returns count of articles summarized.
    """
    articles = get_unsummarized_articles()
    
    if limit:
        articles = articles[:limit]
    
    print(f"\n{'='*50}")
    print(f"AI Summarization (Gemini) - {len(articles)} articles to process")
    print(f"{'='*50}\n")
    
    if not articles:
        print("No unsummarized articles found.")
        return 0
    
    summarized = 0
    
    for article in articles:
        title = article.get('title', '')
        content = article.get('content', '') or title
        article_id = article.get('id')
        
        print(f"  Summarizing: {title[:50]}...")
        
        if dry_run:
            print(f"    [DRY RUN] Would summarize article {article_id}")
            summarized += 1
            continue
        
        summary = summarize_article(title, content)
        
        if summary:
            update_article_summary(article_id, summary)
            print(f"    ✓ Summary: {summary[:80]}...")
            summarized += 1
        else:
            print(f"    ✗ Failed to summarize")
        
        # Rate limiting - be nice to the API
        time.sleep(0.5)
    
    print(f"\n{'='*50}")
    print(f"Summarized {summarized} of {len(articles)} articles")
    print(f"{'='*50}\n")
    
    return summarized


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize articles with AI")
    parser.add_argument('--dry-run', action='store_true',
                        help="Process without calling AI API")
    parser.add_argument('--limit', type=int, default=None,
                        help="Limit number of articles to summarize")
    args = parser.parse_args()
    
    # Check for API key
    if not os.getenv("GEMINI_API_KEY"):
        print("⚠️  GEMINI_API_KEY not configured in .env")
        print("   Get one at: https://aistudio.google.com/apikey")
        exit(1)
    
    count = summarize_all(dry_run=args.dry_run, limit=args.limit)
    print(f"Done! Summarized {count} articles.")

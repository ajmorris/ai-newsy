import os
import argparse
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import google.generativeai as genai

import sys
sys.path.insert(0, '.')
from execution.database import get_unsummarized_articles, update_article_summary, supabase

load_dotenv()

# Initialize Gemini client
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

# Summarization prompt
SYSTEM_PROMPT = """You are an expert AI news analyst. Given an article title and content, you will provide:
1. SUMMARY: A concise 2-3 sentence summary capturing the key news and why it matters.
2. OPINION: A sharp, insightful 1-2 sentence "takeaway" or opinion on the implications, relevance, or quality of the news. 

Keep it informative, objective but critical, and brief. 

Format your response exactly like this:
SUMMARY: [Your summary here]
OPINION: [Your opinion here]"""


def scrape_url(url: str) -> str:
    """Attempt to scrape text content from a URL."""
    if "twitter.com" in url or "x.com" in url:
        return "" # Don't try to scrape X itself, just use the tweet text
        
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text()
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            return text[:4000] # Limit content size
        return ""
    except Exception as e:
        print(f"    Warning: Scrape failed for {url}: {e}")
        return ""


def summarize_article(title: str, content: str, url: str) -> tuple:
    """
    Generate a summary and opinion for a single article using Gemini.
    Returns (summary, opinion).
    """
    try:
        # If it's an external link from X, try to get more context
        scraped_content = ""
        if "X (@" in title and url and "twitter.com" not in url:
            print(f"    Scraping external link: {url}...")
            scraped_content = scrape_url(url)
        
        # Combine content for Gemini
        context = f"Title: {title}\nURL: {url}\n"
        if scraped_content:
            context += f"Scraped Page Content: {scraped_content[:3000]}\n"
        context += f"Original Source Content: {content}"
        
        prompt = f"{SYSTEM_PROMPT}\n\n{context}"
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        summary = ""
        opinion = ""
        
        if "SUMMARY:" in text and "OPINION:" in text:
            parts = text.split("OPINION:")
            summary = parts[0].replace("SUMMARY:", "").strip()
            opinion = parts[1].strip()
        else:
            summary = text # Fallback
            
        return summary, opinion
    except Exception as e:
        print(f"    Error summarizing: {e}")
        return "", ""


def update_article_analysis(article_id: int, summary: str, opinion: str) -> dict:
    """Update an article with its summary and opinion."""
    result = supabase.table("articles").update({
        "summary": summary,
        "opinion": opinion
    }).eq("id", article_id).execute()
    return result.data[0] if result.data else {}


def summarize_all(dry_run: bool = False, limit: int = None) -> int:
    """
    Summarize all unsummarized articles.
    Returns count of articles summarized.
    """
    articles = get_unsummarized_articles()
    
    if limit:
        articles = articles[:limit]
    
    print(f"\n{'='*50}")
    print(f"AI Analysis (Gemini) - {len(articles)} articles to process")
    print(f"{'='*50}\n")
    
    if not articles:
        print("No unsummarized articles found.")
        return 0
    
    summarized = 0
    
    for article in articles:
        title = article.get('title', '')
        content = article.get('content', '') or title
        url = article.get('url', '')
        article_id = article.get('id')
        
        print(f"  Analyzing: {title[:50]}...")
        
        if dry_run:
            print(f"    [DRY RUN] Would analyze article {article_id}")
            summarized += 1
            continue
        
        summary, opinion = summarize_article(title, content, url)
        
        if summary:
            update_article_analysis(article_id, summary, opinion)
            print(f"    ✓ Summary: {summary[:60]}...")
            if opinion:
                print(f"    💭 Opinion: {opinion[:60]}...")
            summarized += 1
        else:
            print(f"    ✗ Failed to analyze")
        
        # Rate limiting - be nice to the API
        time.sleep(0.5)
    
    print(f"\n{'='*50}")
    print(f"Analyzed {summarized} of {len(articles)} articles")
    print(f"{'='*50}\n")
    
    return summarized


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze articles with AI")
    parser.add_argument('--dry-run', action='store_true',
                        help="Process without calling AI API")
    parser.add_argument('--limit', type=int, default=None,
                        help="Limit number of articles to analyze")
    args = parser.parse_args()
    
    # Check for API key
    if not os.getenv("GEMINI_API_KEY"):
        print("⚠️  GEMINI_API_KEY not configured in .env")
        print("   Get one at: https://aistudio.google.com/apikey")
        exit(1)
    
    count = summarize_all(dry_run=args.dry_run, limit=args.limit)
    print(f"Done! Analyzed {count} articles.")

"""
Run single-pass LLM analysis for unsent articles.
Each article is processed at most once and persisted as structured output.
"""

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import sys
sys.path.insert(0, ".")
from execution.ai_client import generate_text_with_fallback
from execution.database import (
    get_articles_without_analysis,
    get_articles_by_analysis_run_id,
    update_article_analysis_payload,
    update_article_image,
    upsert_digest_extra,
)

load_dotenv()

TOPICS = [
    "Models",
    "Agents & Tools",
    "MCP & SKILLs",
    "Safety",
    "Industry",
]

PROMPT_VERSION = "single-pass-v1"
DEFAULT_ANALYSIS_PROMPT = """You are classifying and summarizing AI news for a daily digest.
Return strictly valid JSON with this exact shape:
{
  "topic": "Models|Agents & Tools|MCP & SKILLs|Safety|Industry",
  "summary": "2-3 sentence concise summary",
  "opinion": "1-2 sentence takeaway",
  "confidence": 0.0
}

Rules:
- topic must be exactly one of the allowed labels
- no markdown, no prose outside JSON
- confidence is a float between 0 and 1
"""
ANALYSIS_PROMPT = os.getenv("PROMPT_SINGLE_PASS_ANALYSIS", DEFAULT_ANALYSIS_PROMPT)
ANALYSIS_MODEL = os.getenv("SINGLE_PASS_MODEL", "gemini-2.0-flash")


def scrape_url(url: str) -> str:
    """Best-effort scrape for richer context when feed snippet is short."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AI-Newsy/1.0)"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.content, "html.parser")
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        cleaned = "\n".join(chunk for chunk in chunks if chunk)
        return cleaned[:4500]
    except Exception:
        return ""


def extract_og_image(url: str) -> Optional[str]:
    """Extract og:image or twitter:image URL from source page."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AI-Newsy/1.0)"}
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.content, "html.parser")
        meta = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if meta and meta.get("content"):
            value = (meta.get("content") or "").strip()
            if value.startswith("http"):
                return value
        return None
    except Exception:
        return None


def _safe_analysis_payload(text: str) -> Dict[str, object]:
    """Parse model JSON output with a resilient fallback."""
    try:
        payload = json.loads(text)
    except Exception:
        payload = {
            "topic": "Industry",
            "summary": text.strip(),
            "opinion": "",
            "confidence": 0.0,
        }

    topic = str(payload.get("topic", "Industry")).strip()
    if topic not in TOPICS:
        topic = "Industry"

    summary = str(payload.get("summary", "")).strip()
    opinion = str(payload.get("opinion", "")).strip()
    confidence_raw = payload.get("confidence", 0.0)
    try:
        confidence = max(0.0, min(float(confidence_raw), 1.0))
    except Exception:
        confidence = 0.0

    return {
        "topic": topic,
        "summary": summary,
        "opinion": opinion,
        "confidence": confidence,
    }


def analyze_article(title: str, content: str, url: str) -> Dict[str, object]:
    """Call model once for topic + summary + opinion."""
    prompt = (
        f"{ANALYSIS_PROMPT}\n\n"
        f"Title: {title}\n"
        f"URL: {url}\n"
        f"Content:\n{content}"
    )
    raw = generate_text_with_fallback(prompt=prompt, gemini_model=ANALYSIS_MODEL)
    return _safe_analysis_payload(raw)


def _build_context(article: dict) -> str:
    snippet = (article.get("content") or "").strip()
    if len(snippet) >= 400:
        return snippet[:2500]
    scraped = scrape_url(article.get("url", ""))
    if scraped:
        return f"{snippet}\n\n{scraped}".strip()[:4500]
    return snippet[:2500]


def run_single_pass(
    dry_run: bool = False,
    limit: Optional[int] = None,
    window_hours: int = 48,
) -> Tuple[int, str]:
    """Process unanalyzed articles and persist structured output."""
    run_id = os.getenv("SINGLE_PASS_RUN_ID", str(uuid.uuid4()))
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    articles = get_articles_without_analysis(limit=limit, since=since, unsent_only=True)
    print(f"Single-pass analysis run_id={run_id}")
    print(f"Analysis window: last {window_hours} hour(s) since {since.isoformat()}")
    print(f"Articles pending analysis: {len(articles)}")

    processed = 0
    for article in articles:
        article_id = article.get("id")
        title = article.get("title", "")
        url = article.get("url", "")
        print(f"  [{article_id}] {title[:70]}...")
        if dry_run:
            processed += 1
            continue

        context = _build_context(article)
        payload = analyze_article(title=title, content=context, url=url)
        if not payload.get("summary"):
            print("    Skipped: empty summary")
            continue

        payload["source_url"] = url
        payload["prompt_version"] = PROMPT_VERSION
        update_article_analysis_payload(
            article_id=article_id,
            payload=payload,
            model=ANALYSIS_MODEL,
            prompt_version=PROMPT_VERSION,
            run_id=run_id,
        )

        image_url = extract_og_image(url)
        if image_url:
            try:
                update_article_image(article_id, image_url)
            except Exception:
                pass

        processed += 1
        time.sleep(0.4)

    run_rows = get_articles_by_analysis_run_id(run_id)
    persisted_count = len(run_rows)
    print(f"Processed in this run: {processed}")
    print(f"Persisted with run_id marker: {persisted_count}")

    digest_date = datetime.now(timezone.utc).date().isoformat()
    upsert_digest_extra(
        digest_date=digest_date,
        key="single_pass_run_stats",
        payload={
            "run_id": run_id,
            "model": ANALYSIS_MODEL,
            "prompt_version": PROMPT_VERSION,
            "processed_count": processed,
            "persisted_count": persisted_count,
            "pending_after_run": len(
                get_articles_without_analysis(since=since, unsent_only=True)
            ),
            "window_hours": window_hours,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    print(f"Stored run stats in digest_extras for {digest_date}")
    return processed, run_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run one-shot LLM analysis per article")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--window-hours",
        type=int,
        default=int(os.getenv("SINGLE_PASS_WINDOW_HOURS", "48")),
    )
    args = parser.parse_args()

    if not os.getenv("GEMINI_API_KEY") and not os.getenv("ANTHROPIC_KEY"):
        print("No AI key configured. Set GEMINI_API_KEY and/or ANTHROPIC_KEY in .env")
        raise SystemExit(1)

    count, run_id = run_single_pass(
        dry_run=args.dry_run,
        limit=args.limit,
        window_hours=max(1, args.window_hours),
    )
    print(f"Done. analyzed={count} run_id={run_id}")

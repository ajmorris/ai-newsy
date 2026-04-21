"""
Send daily email digest to subscribers.
Compiles summarized articles and sends via Resend.
Includes AI-generated introduction synthesizing all stories.
"""

import os
import argparse
import html
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dotenv import load_dotenv
import resend

import sys
sys.path.insert(0, '.')
from execution.database import (
    get_unsent_articles,
    get_sent_articles,
    get_active_subscribers,
    mark_articles_sent,
    insert_digest_log,
    get_digest_extra,
)
from execution.ai_client import generate_text_with_fallback

load_dotenv()

# Resend configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
resend.api_key = RESEND_API_KEY
EMAIL_FROM = os.getenv("EMAIL_FROM", "newsletter@example.com")
APP_URL = os.getenv("APP_URL", "https://your-app.vercel.app")

# Intro prompt (override via PROMPT_INTRO env var)
DEFAULT_INTRO_PROMPT = """You are writing the opening paragraph for a daily AI news digest email. 
Given these article summaries, write a 2-3 sentence engaging introduction that:
1. Highlights the most significant theme or story of the day
2. Gives readers a preview of what to expect
3. Uses a friendly, conversational tone

Keep it concise and hook the reader. No greeting or sign-off, just the intro paragraph.

Today's stories:
{article_summaries}"""

INTRO_PROMPT = os.getenv("PROMPT_INTRO", DEFAULT_INTRO_PROMPT)

# Fixed topics for daily digest sections
DIGEST_TOPICS: List[str] = [
    "Models",
    "Agents & Tools",
    "MCP & Skills",
    "Safety",
    "Industry",
]

# Mapping from internal topic labels to reader-facing categories
TOPIC_TO_CATEGORY: Dict[str, str] = {
    "Models": "Model Releases & Capabilities",
    "Agents & Tools": "Tools, Infrastructure & Open Source",
    "MCP & SKILLs": "Tools, Infrastructure & Open Source",
    "Safety": "Safety, Policy & Regulation",
    "Industry": "Business, Deals & Funding",
}

DEFAULT_CATEGORY = "Other AI News"


def generate_intro(articles: list) -> str:
    """Generate an AI introduction synthesizing all articles."""
    try:
        # Build context from all articles
        article_summaries = "\n".join([
            f"- {a.get('title', '')}: {a.get('summary', '')}" 
            for a in articles
        ])
        
        prompt = INTRO_PROMPT.format(article_summaries=article_summaries)

        return generate_text_with_fallback(
            prompt=prompt,
            gemini_model="gemini-2.0-flash",
        )
    except Exception as e:
        print(f"    Error generating intro: {e}")
        return "Here's what's making waves in AI today."


def _parse_frontmatter(markdown_text: str) -> tuple:
    """Parse very simple YAML frontmatter key/value pairs."""
    if not markdown_text.startswith("---\n"):
        return {}, markdown_text
    end_idx = markdown_text.find("\n---\n", 4)
    if end_idx == -1:
        return {}, markdown_text

    frontmatter_block = markdown_text[4:end_idx]
    body = markdown_text[end_idx + 5 :]
    metadata: Dict[str, str] = {}
    for raw_line in frontmatter_block.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line or line.startswith("-"):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        metadata[key] = value
    return metadata, body


def _md_inline_to_html(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\[(.+?)\]\((https?://[^\)]+)\)", r'<a href="\2" style="color: #6246ea; text-decoration: underline;">\1</a>', escaped)
    return escaped


def _markdown_body_to_html(markdown_body: str) -> str:
    lines = markdown_body.splitlines()
    output: List[str] = []
    in_list = False
    in_json_block = False
    json_lines: List[str] = []
    current_article: Optional[Dict[str, str]] = None

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            output.append("</ul>")
            in_list = False

    def flush_article() -> None:
        nonlocal current_article
        if not current_article:
            return

        source = _md_inline_to_html(current_article.get("source", "Unknown Source"))
        title = _md_inline_to_html(current_article.get("title", "Untitled"))
        link = html.escape(current_article.get("url", "#"), quote=True)
        summary = _md_inline_to_html(current_article.get("summary", "No summary available."))
        opinion = _md_inline_to_html(current_article.get("opinion", ""))
        image_url = html.escape(current_article.get("image_url", ""), quote=True)

        image_html = ""
        if image_url:
            image_alt = html.escape(current_article.get("title", "Article"), quote=True)
            image_html = (
                f'<div style="margin-bottom: 12px;"><img src="{image_url}" alt="{image_alt}" '
                'style="max-width: 100%; height: auto; max-height: 200px; object-fit: cover; display: block; border-radius: 6px;" '
                'width="560" /></div>'
            )

        opinion_html = ""
        if opinion:
            opinion_html = (
                '<div style="margin-top: 12px; padding: 12px 14px; background-color: #d1d1e9; '
                'border-left: 3px solid #6246ea; border-radius: 0 4px 4px 0;">'
                '<p style="margin: 0 0 4px 0; color: #6246ea; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Takeaway</p>'
                f'<p style="margin: 0; color: #2b2c34; font-size: 14px; line-height: 1.5;">{opinion}</p>'
                "</div>"
            )

        output.append(
            '<div style="padding: 24px 0; border-bottom: 1px solid #d1d1e9;">'
            f'<p style="margin: 0 0 6px 0; color: #6246ea; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500;">{source}</p>'
            f"{image_html}"
            f'<h3 style="margin: 0 0 8px 0; font-size: 20px; font-weight: 600; line-height: 1.35;">'
            f'<a href="{link}" style="color: #6246ea; text-decoration: none; padding: 4px 0; display: inline-block;">{title}</a>'
            "</h3>"
            f'<p style="margin: 0; color: #2b2c34; font-size: 15px; line-height: 1.6;">{summary}</p>'
            f"{opinion_html}"
            "</div>"
        )
        current_article = None

    for line in lines:
        stripped = line.strip()

        if in_json_block:
            if stripped == "```":
                in_json_block = False
                if current_article is not None:
                    try:
                        payload = json.loads("\n".join(json_lines))
                        current_article["summary"] = str(payload.get("summary", "")).strip()
                        current_article["opinion"] = str(payload.get("opinion", "")).strip()
                        raw_image = payload.get("image_url")
                        current_article["image_url"] = str(raw_image).strip() if raw_image else ""
                    except json.JSONDecodeError:
                        current_article["summary"] = "\n".join(json_lines).strip()
                json_lines = []
            else:
                json_lines.append(line)
            continue

        if not stripped:
            continue

        if stripped.startswith("## "):
            close_list()
            flush_article()
            output.append(f'<h2 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 600; color: #2b2c34;">{_md_inline_to_html(stripped[3:])}</h2>')
            continue

        if stripped.startswith("### "):
            close_list()
            flush_article()
            title_line = stripped[4:].strip()
            match = re.match(r"\[(.+?)\]\((https?://[^\)]+)\)", title_line)
            if match:
                current_article = {
                    "title": match.group(1),
                    "url": match.group(2),
                    "source": "Unknown Source",
                    "summary": "",
                    "opinion": "",
                    "image_url": "",
                }
            else:
                current_article = {
                    "title": title_line,
                    "url": "#",
                    "source": "Unknown Source",
                    "summary": "",
                    "opinion": "",
                    "image_url": "",
                }
            continue

        if stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 2 and current_article is not None:
            current_article["source"] = stripped[1:-1].strip()
            continue

        if stripped == "```json":
            in_json_block = True
            json_lines = []
            continue

        if stripped.startswith("- "):
            flush_article()
            if not in_list:
                output.append('<ul style="padding-left: 20px; margin: 0 0 12px 0;">')
                in_list = True
            output.append(f'<li style="margin-bottom: 10px; line-height: 1.6; color: #2b2c34;">{_md_inline_to_html(stripped[2:])}</li>')
            continue

        flush_article()
        output.append(f'<p style="margin: 0 0 10px 0; color: #2b2c34; font-size: 15px; line-height: 1.6;">{_md_inline_to_html(stripped)}</p>')

    close_list()
    flush_article()
    return "\n".join(output)


def _load_digest_markdown_email(
    digest_date: str,
    unsubscribe_token: str,
) -> Optional[Dict[str, str]]:
    markdown_dir = Path(os.getenv("DIGEST_MARKDOWN_DIR", "data/digests"))
    file_path = markdown_dir / f"{digest_date}.md"
    if not file_path.exists():
        return None

    raw = file_path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    subject = meta.get("subject", f"AI Newsy • {digest_date}")
    intro = meta.get("intro", "")
    body_html = _markdown_body_to_html(body)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #fffffe; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;">
        <div style="max-width: 560px; margin: 0 auto; padding: 48px 24px;">
            <div style="margin-bottom: 32px;">
                <h1 style="color: #2b2c34; font-size: 24px; margin: 0; font-weight: 700;">AI Newsy</h1>
                <p style="color: #6246ea; margin: 4px 0 0 0; font-size: 14px;">{digest_date}</p>
            </div>
            <div style="margin-bottom: 32px; padding: 20px; background-color: #d1d1e9; border-radius: 8px;">
                <p style="margin: 0; color: #2b2c34; font-size: 16px; line-height: 1.7;">{html.escape(intro)}</p>
            </div>
            <div style="margin-bottom: 32px;">
                {body_html}
            </div>
            <div style="padding-top: 24px; border-top: 1px solid #d1d1e9;">
                <p style="color: #2b2c34; font-size: 13px; margin: 0; line-height: 1.6;">
                    You're receiving this because you subscribed to AI Newsy.
                    <a href="{APP_URL}/api/unsubscribe?token={unsubscribe_token}" style="color: #6246ea; text-decoration: underline;">Unsubscribe</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    return {"subject": subject, "html": html_content}


def generate_email_html(
    sections: List[dict],
    intro: str,
    tweet_headlines: Optional[List[dict]] = None,
    community_headlines: Optional[List[dict]] = None,
    unsubscribe_token: str = "",
) -> str:
    """Generate HTML email with grouped sections. Links and takeaways styled for clarity."""
    today = datetime.now().strftime("%B %d, %Y")

    # ---- Sections and article cards ----
    section_blocks = ""
    for section in sections:
        name = section.get("name", DEFAULT_CATEGORY)
        articles = section.get("articles", [])

        article_cards = ""
        for article in articles:
            source = article.get("source", "Unknown Source")
            opinion = article.get("opinion", "")
            image_url = article.get("image_url") or ""

            opinion_html = ""
            if opinion:
                opinion_html = f"""
                <div style="margin-top: 12px; padding: 12px 14px; background-color: #d1d1e9; border-left: 3px solid #6246ea; border-radius: 0 4px 4px 0;">
                    <p style="margin: 0 0 4px 0; color: #6246ea; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Takeaway</p>
                    <p style="margin: 0; color: #2b2c34; font-size: 14px; line-height: 1.5;">{opinion}</p>
                </div>
                """

            image_html = ""
            if image_url:
                title_esc = (article.get("title") or "Article").replace('"', "&quot;")
                image_html = f'<div style="margin-bottom: 12px;"><img src="{image_url}" alt="{title_esc}" style="max-width: 100%; height: auto; max-height: 200px; object-fit: cover; display: block; border-radius: 6px;" width="560" /></div>'

            article_cards += f"""
            <div style="padding: 24px 0; border-bottom: 1px solid #d1d1e9;">
                <p style="margin: 0 0 6px 0; color: #6246ea; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500;">
                    {source}
                </p>
                {image_html}
                <h3 style="margin: 0 0 8px 0; font-size: 20px; font-weight: 600; line-height: 1.35;">
                    <a href="{article.get("url", "#")}" style="color: #6246ea; text-decoration: none; padding: 4px 0; display: inline-block;">{article.get("title", "Untitled")}</a>
                </h3>
                <p style="margin: 0; color: #2b2c34; font-size: 15px; line-height: 1.6;">
                    {article.get("summary", "No summary available.")}
                </p>
                {opinion_html}
            </div>
            """

        section_blocks += f"""
        <div style="margin-bottom: 32px;">
            <h2 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 600; color: #2b2c34;">
                {name}
            </h2>
            {article_cards}
        </div>
        """

    tweet_headlines = tweet_headlines or []
    community_headlines = community_headlines or []

    tweet_section_html = ""
    if tweet_headlines:
        tweet_items_html = "".join(
            [f"<li style=\"margin-bottom: 10px; line-height: 1.6; color: #2b2c34;\">{render_tweet_headline_html(item)}</li>" for item in tweet_headlines]
        )
        tweet_section_html = f"""
        <div style="margin-bottom: 32px;">
            <h2 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 600; color: #2b2c34;">
                From X/Twitter
            </h2>
            <ul style="padding-left: 20px; margin: 0;">
                {tweet_items_html}
            </ul>
        </div>
        """

    community_section_html = ""
    if community_headlines:
        community_items_html = "".join(
            [f"<li style=\"margin-bottom: 10px; line-height: 1.6; color: #2b2c34;\">{render_tweet_headline_html(item)}</li>" for item in community_headlines]
        )
        community_section_html = f"""
        <div style="margin-bottom: 32px;">
            <h2 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 600; color: #2b2c34;">
                From Reddit/HN/YC
            </h2>
            <ul style="padding-left: 20px; margin: 0;">
                {community_items_html}
            </ul>
        </div>
        """

    # Full email template (colors from Happy Hues palette 6)
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #fffffe; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;">
        <div style="max-width: 560px; margin: 0 auto; padding: 48px 24px;">
            <div style="margin-bottom: 32px;">
                <h1 style="color: #2b2c34; font-size: 24px; margin: 0; font-weight: 700;">AI Newsy</h1>
                <p style="color: #6246ea; margin: 4px 0 0 0; font-size: 14px;">{today}</p>
            </div>
            <div style="margin-bottom: 32px; padding: 20px; background-color: #d1d1e9; border-radius: 8px;">
                <p style="margin: 0; color: #2b2c34; font-size: 16px; line-height: 1.7;">{intro}</p>
            </div>
            <div style="margin-bottom: 32px;">
                {section_blocks}
            </div>
            {tweet_section_html}
            {community_section_html}
            <div style="padding-top: 24px; border-top: 1px solid #d1d1e9;">
                <p style="color: #2b2c34; font-size: 13px; margin: 0; line-height: 1.6;">
                    You're receiving this because you subscribed to AI Newsy.
                    <a href="{APP_URL}/api/unsubscribe?token={unsubscribe_token}" style="color: #6246ea; text-decoration: underline;">Unsubscribe</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def render_tweet_headline_html(item: dict) -> str:
    """
    Convert headline text with markdown-style __anchor__ into HTML.
    If URL exists and anchor is present, only the anchor phrase is linked.
    """
    headline = (item.get("headline") or "").strip()
    url = (item.get("url") or "").strip()
    if not headline:
        return ""

    if not url:
        return html.escape(headline)

    match = re.search(r"__(.+?)__", headline)
    if not match:
        title = html.escape(headline)
        safe_url = html.escape(url, quote=True)
        return (
            f"{title} "
            f'<a href="{safe_url}" style="color: #6246ea; text-decoration: underline;">Source</a>'
        )

    anchor_text = match.group(1)
    safe_anchor = html.escape(anchor_text)
    safe_url = html.escape(url, quote=True)
    linked = f'<a href="{safe_url}" style="color: #6246ea; text-decoration: underline;">{safe_anchor}</a>'
    replaced = headline[:match.start()] + linked + headline[match.end():]
    return html.escape(replaced).replace(html.escape(linked), linked)


def send_email(to_email: str, html_content: str, subject: str) -> bool:
    """Send a single email via Resend."""
    try:
        params = {
            "from": f"AI Newsy <{EMAIL_FROM}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"    Error sending to {to_email}: {e}")
        return False


def group_articles_by_category(articles: list) -> List[dict]:
    """
    Group articles into reader-facing categories based on their topic.
    Returns a list of sections with stable alphabetical ordering by category name.
    """
    by_category: Dict[str, list] = {}
    for article in articles:
        raw_topic = (article.get("topic") or "").strip()
        category = TOPIC_TO_CATEGORY.get(raw_topic, DEFAULT_CATEGORY)
        by_category.setdefault(category, []).append(article)

    sections = []
    for category in sorted(by_category.keys()):
        sections.append(
            {
                "name": category,
                "articles": by_category[category],
            }
        )
    return sections


def send_daily_digest(
    dry_run: bool = False,
    test_email: Optional[str] = None,
    sent_yesterday: bool = False,
) -> dict:
    """
    Send daily digest to all active subscribers (or only to test_email if set).
    When test_email is set: send only to that address, do not mark articles as sent.
    Returns dict with counts.
    """
    print(f"\n{'='*50}")
    print(f"Daily Email Digest - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if test_email:
        print(f"  [TEST MODE] Sending only to: {test_email}")
    print(f"{'='*50}\n")

    if sent_yesterday:
        today_utc = datetime.utcnow().date()
        yesterday_start = datetime.combine(today_utc - timedelta(days=1), datetime.min.time())
        today_start = datetime.combine(today_utc, datetime.min.time())
        print(
            "Using SENT replay window: "
            f"{yesterday_start.isoformat()} to {today_start.isoformat()} (UTC)"
        )
        articles = get_sent_articles(
            require_summary=True,
            since=yesterday_start,
            until=today_start,
        )
    else:
        window_hours = int(os.getenv("DIGEST_WINDOW_HOURS", "24"))
        since = datetime.utcnow() - timedelta(hours=window_hours)
        print(f"Using time window: last {window_hours} hour(s) since {since.isoformat()}")
        # Select all unsent, summarized articles within the time window
        articles = get_unsent_articles(
            topic=None,
            require_summary=True,
            since=since,
            until=None,
        )

    if not articles:
        print("No matching articles to include in digest.")
        return {"articles": 0, "sent": 0, "failed": 0}

    print(f"📰 {len(articles)} articles to include")

    if test_email:
        subscribers = [{"email": test_email, "confirm_token": "test-token"}]
        print(f"👥 Test: 1 recipient ({test_email})")
    else:
        subscribers = get_active_subscribers()
        if not subscribers:
            print("No active subscribers.")
            return {"articles": len(articles), "sent": 0, "failed": 0}
        print(f"👥 {len(subscribers)} active subscribers")

    # Generate AI introduction
    print("✨ Generating AI introduction...")
    intro = generate_intro(articles)
    print(f"   Intro: {intro[:80]}...")

    # Subject line (no longer single-topic; reflect total story count)
    today = datetime.now().strftime("%b %d")
    subject = f"AI Newsy • {today} • {len(articles)} Stories"
    if sent_yesterday:
        subject = f"[TEST Replay] {subject}"

    sent = 0
    failed = 0

    # Build sections once from article topics so each article appears only once
    sections = group_articles_by_category(articles)
    digest_date = datetime.utcnow().date().isoformat()
    extra = get_digest_extra(digest_date=digest_date, key="tweet_headlines")
    tweet_headlines = []
    if not extra:
        print(f"⚠️ No digest_extras row found for key=tweet_headlines on {digest_date}")
    elif isinstance(extra.get("payload"), dict):
        payload = extra["payload"]
        source_count = payload.get("source_count", "unknown")
        headline_count = payload.get("headline_count", "unknown")
        tweet_headlines = payload.get("headlines", []) or []
        print(
            "🐦 Tweet headlines extra found: "
            f"source_count={source_count}, payload_headline_count={headline_count}, "
            f"loaded_for_email={len(tweet_headlines)}"
        )
    else:
        print(f"⚠️ tweet_headlines payload is not a dict for digest_date={digest_date}")

    if not tweet_headlines and not sent_yesterday:
        print(
            "⚠️ Tweet headlines are empty for this digest send. "
            "Email will continue without the From X/Twitter section."
        )

    community_extra = get_digest_extra(digest_date=digest_date, key="community_headlines")
    community_headlines = []
    if not community_extra:
        print(f"⚠️ No digest_extras row found for key=community_headlines on {digest_date}")
    elif isinstance(community_extra.get("payload"), dict):
        payload = community_extra["payload"]
        source_count = payload.get("source_count", "unknown")
        headline_count = payload.get("headline_count", "unknown")
        community_headlines = payload.get("headlines", []) or []
        print(
            "🌐 Community headlines extra found: "
            f"source_count={source_count}, payload_headline_count={headline_count}, "
            f"loaded_for_email={len(community_headlines)}"
        )
    else:
        print(f"⚠️ community_headlines payload is not a dict for digest_date={digest_date}")

    if not community_headlines and not sent_yesterday:
        print(
            "⚠️ Community headlines are empty for this digest send. "
            "Email will continue without the From Reddit/HN/YC section."
        )

    for subscriber in subscribers:
        email = subscriber.get('email')
        token = subscriber.get('confirm_token', '')

        print(f"  Sending to: {email}...")

        if dry_run:
            print(f"    [DRY RUN] Would send {len(articles)} articles")
            sent += 1
            continue

        compiled = _load_digest_markdown_email(digest_date=digest_date, unsubscribe_token=token)
        if compiled:
            html = compiled["html"]
            subject_to_send = compiled["subject"]
        else:
            html = generate_email_html(
                sections,
                intro=intro,
                tweet_headlines=tweet_headlines,
                community_headlines=community_headlines,
                unsubscribe_token=token,
            )
            subject_to_send = subject
        
        if send_email(email, html, subject_to_send):
            print(f"    ✓ Sent!")
            sent += 1
        else:
            print(f"    ✗ Failed")
            failed += 1
    
    # Mark articles as sent (only if not dry run, not test mode, and we sent to at least one person)
    if not dry_run and not test_email and sent > 0:
        article_ids = [a.get('id') for a in articles]
        mark_articles_sent(article_ids)
        print(f"\n📌 Marked {len(article_ids)} articles as sent")
        # Log each digest topic for this send
        for topic in DIGEST_TOPICS:
            insert_digest_log(topic)
    
    print(f"\n{'='*50}")
    print(f"Summary: Sent to {sent}, Failed: {failed}")
    print(f"{'='*50}\n")
    
    return {"articles": len(articles), "sent": sent, "failed": failed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send daily email digest")
    parser.add_argument('--dry-run', action='store_true',
                        help="Process without sending emails")
    parser.add_argument('--test-email', type=str, default=None,
                        help="Send only to this email (e.g. for testing); does not mark articles as sent")
    parser.add_argument('--sent-yesterday', action='store_true',
                        help="Build digest from articles sent yesterday (UTC), for testing replay")
    args = parser.parse_args()

    # Check for API key
    if not RESEND_API_KEY or RESEND_API_KEY.strip() == "":
        print("RESEND_API_KEY not configured in .env")
        print("   Get one at: https://resend.com/api-keys")
        exit(1)

    result = send_daily_digest(
        dry_run=args.dry_run,
        test_email=args.test_email,
        sent_yesterday=args.sent_yesterday,
    )
    print(f"Done! Sent digest with {result['articles']} articles to {result['sent']} subscribers.")

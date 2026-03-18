"""
Send daily email digest to subscribers.
Compiles summarized articles and sends via SendGrid.
Includes AI-generated introduction synthesizing all stories.
"""

import os
import argparse
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent
from google import genai

import sys
sys.path.insert(0, '.')
from execution.database import (
    get_unsent_articles,
    get_active_subscribers,
    mark_articles_sent,
    insert_digest_log,
)
from execution.summarize_articles import summarize_selected

load_dotenv()

# SendGrid configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "newsletter@example.com")
APP_URL = os.getenv("APP_URL", "https://your-app.vercel.app")

# Initialize Gemini client (auto-reads GEMINI_API_KEY env var)
client = genai.Client()

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

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"    Error generating intro: {e}")
        return "Here's what's making waves in AI today."


def generate_email_html(
    sections: List[dict],
    intro: str,
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


def send_email(to_email: str, html_content: str, subject: str) -> bool:
    """Send a single email via SendGrid."""
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        
        message = Mail(
            from_email=Email(EMAIL_FROM, "AI Newsy"),
            to_emails=To(to_email),
            subject=subject,
            html_content=HtmlContent(html_content)
        )
        
        response = sg.send(message)
        return response.status_code in [200, 201, 202]
        
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


def send_daily_digest(dry_run: bool = False, test_email: Optional[str] = None) -> dict:
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
        print("No unsent articles to include in digest.")
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

    sent = 0
    failed = 0

    for subscriber in subscribers:
        email = subscriber.get('email')
        token = subscriber.get('confirm_token', '')

        print(f"  Sending to: {email}...")

        if dry_run:
            print(f"    [DRY RUN] Would send {len(articles)} articles")
            sent += 1
            continue

        # Build fixed topic-based sections; each topic includes all selected articles
        sections = [
            {
                "name": topic,
                "articles": articles,
            }
            for topic in DIGEST_TOPICS
        ]
        html = generate_email_html(sections, intro=intro, unsubscribe_token=token)
        
        if send_email(email, html, subject):
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
    args = parser.parse_args()

    # Check for API key
    if not SENDGRID_API_KEY or SENDGRID_API_KEY == "your-sendgrid-api-key":
        print("⚠️  SENDGRID_API_KEY not configured in .env")
        print("   Get one at: https://sendgrid.com/")
        exit(1)

    result = send_daily_digest(dry_run=args.dry_run, test_email=args.test_email)
    print(f"Done! Sent digest with {result['articles']} articles to {result['sent']} subscribers.")

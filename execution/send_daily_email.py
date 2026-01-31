"""
Send daily email digest to subscribers.
Compiles summarized articles and sends via SendGrid.
Includes AI-generated introduction synthesizing all stories.
"""

import os
import argparse
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent
import google.generativeai as genai

import sys
sys.path.insert(0, '.')
from execution.database import (
    get_unsent_articles_for_digest,
    get_active_subscribers,
    mark_articles_sent,
    get_unsent_articles_with_topic_set,
    get_topics_used_in_last_k_days,
    insert_digest_log,
)
from execution.summarize_articles import summarize_selected

load_dotenv()

# SendGrid configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "newsletter@example.com")
APP_URL = os.getenv("APP_URL", "https://your-app.vercel.app")

# Initialize Gemini for intro generation
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')


def generate_intro(articles: list) -> str:
    """Generate an AI introduction synthesizing all articles."""
    try:
        # Build context from all articles
        article_summaries = "\n".join([
            f"- {a.get('title', '')}: {a.get('summary', '')}" 
            for a in articles
        ])
        
        prompt = f"""You are writing the opening paragraph for a daily AI news digest email. 
Given these article summaries, write a 2-3 sentence engaging introduction that:
1. Highlights the most significant theme or story of the day
2. Gives readers a preview of what to expect
3. Uses a friendly, conversational tone

Keep it concise and hook the reader. No greeting or sign-off, just the intro paragraph.

Today's stories:
{article_summaries}"""

        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"    Error generating intro: {e}")
        return "Here's what's making waves in AI today."


def generate_email_html(
    articles_rss: list,
    articles_x: list,
    intro: str,
    unsubscribe_token: str = "",
) -> str:
    """Generate HTML email: articles section + Latest from socials (X). Links and takeaways styled for clarity."""
    today = datetime.now().strftime("%B %d, %Y")

    # ---- Articles section (RSS): prominent links, takeaway block, optional image ----
    article_cards = ""
    for article in articles_rss:
        source = article.get("source", "Unknown Source")
        opinion = article.get("opinion", "")
        image_url = article.get("image_url") or ""

        opinion_html = ""
        if opinion:
            opinion_html = f"""
            <div style="margin-top: 12px; padding: 12px 14px; background-color: #f8fafc; border-left: 3px solid #0f172a; border-radius: 0 4px 4px 0;">
                <p style="margin: 0 0 4px 0; color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Takeaway</p>
                <p style="margin: 0; color: #334155; font-size: 14px; line-height: 1.5;">{opinion}</p>
            </div>
            """

        image_html = ""
        if image_url:
            title_esc = (article.get("title") or "Article").replace('"', "&quot;")
            image_html = f'<div style="margin-bottom: 12px;"><img src="{image_url}" alt="{title_esc}" style="max-width: 100%; height: auto; max-height: 200px; object-fit: cover; display: block; border-radius: 6px;" width="560" /></div>'

        article_cards += f"""
        <div style="padding: 24px 0; border-bottom: 1px solid #f3f4f6;">
            <p style="margin: 0 0 6px 0; color: #9ca3af; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500;">
                {source}
            </p>
            {image_html}
            <h3 style="margin: 0 0 8px 0; font-size: 20px; font-weight: 600; line-height: 1.35;">
                <a href="{article.get("url", "#")}" style="color: #0f172a; text-decoration: none; padding: 4px 0; display: inline-block;">{article.get("title", "Untitled")}</a>
            </h3>
            <p style="margin: 0; color: #4b5563; font-size: 15px; line-height: 1.6;">
                {article.get("summary", "No summary available.")}
            </p>
            {opinion_html}
        </div>
        """

    # ---- Latest from socials (X) ----
    socials_html = ""
    if articles_x:
        social_cards = ""
        for item in articles_x:
            source = item.get("source", "X")
            content = (item.get("content") or "").replace("\n", "<br />")
            url = item.get("url", "#")
            social_cards += f"""
            <div style="padding: 16px; margin-bottom: 12px; background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
                <p style="margin: 0 0 8px 0; color: #64748b; font-size: 12px; font-weight: 600;">{source}</p>
                <p style="margin: 0 0 10px 0; color: #334155; font-size: 14px; line-height: 1.5;">{content}</p>
                <a href="{url}" style="color: #0f172a; font-size: 13px; font-weight: 500;">View on X →</a>
            </div>
            """
        socials_html = f"""
            <div style="margin-top: 32px; margin-bottom: 32px;">
                <h2 style="color: #0f172a; font-size: 18px; font-weight: 600; margin: 0 0 16px 0;">Latest from socials</h2>
                {social_cards}
            </div>
        """

    # Full email template
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;">
        <div style="max-width: 560px; margin: 0 auto; padding: 48px 24px;">
            <div style="margin-bottom: 32px;">
                <h1 style="color: #111827; font-size: 24px; margin: 0; font-weight: 700;">AI Newsy</h1>
                <p style="color: #6b7280; margin: 4px 0 0 0; font-size: 14px;">{today}</p>
            </div>
            <div style="margin-bottom: 32px; padding: 20px; background-color: #f9fafb; border-radius: 8px;">
                <p style="margin: 0; color: #374151; font-size: 16px; line-height: 1.7;">{intro}</p>
            </div>
            <div style="margin-bottom: 32px;">
                {article_cards}
            </div>
            {socials_html}
            <div style="padding-top: 24px; border-top: 1px solid #e5e7eb;">
                <p style="color: #9ca3af; font-size: 13px; margin: 0; line-height: 1.6;">
                    You're receiving this because you subscribed to AI Newsy.
                    <a href="{APP_URL}/api/unsubscribe?token={unsubscribe_token}" style="color: #9ca3af; text-decoration: underline;">Unsubscribe</a>
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


def choose_topic_for_today() -> Optional[str]:
    """
    Pick today's digest topic: unsent articles with a topic, exclude topics used in last K days,
    pick topic with most articles. Returns None if no topic-based pool or no eligible topic.
    """
    from collections import Counter
    articles_with_topic = get_unsent_articles_with_topic_set()
    if not articles_with_topic:
        return None
    cooldown_days = int(os.getenv("DIGEST_TOPIC_COOLDOWN_DAYS", "5"))
    excluded = set(get_topics_used_in_last_k_days(cooldown_days))
    counts = Counter(a.get("topic") for a in articles_with_topic if a.get("topic"))
    eligible = {t: c for t, c in counts.items() if t not in excluded}
    if not eligible:
        # All topics used recently: pick the one with most articles (used longest ago would need extra query)
        eligible = dict(counts)
    if not eligible:
        return None
    chosen = max(eligible.items(), key=lambda x: x[1])[0]
    return chosen


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

    max_per_source = int(os.getenv("DIGEST_MAX_PER_SOURCE", "2"))

    # Topic-based: choose topic, get candidates for that topic, JIT summarize if needed
    chosen_topic = choose_topic_for_today()
    if chosen_topic:
        print(f"📌 Today's topic: {chosen_topic}")
        articles = get_unsent_articles_for_digest(
            max_per_source=max_per_source, interleave=True, topic=chosen_topic
        )
        if articles:
            need_summary = [a for a in articles if not a.get("summary")]
            if need_summary:
                print(f"✨ Just-in-time summarizing {len(need_summary)} article(s)...")
                summarize_selected(articles, dry_run=dry_run)
    else:
        articles = get_unsent_articles_for_digest(
            max_per_source=max_per_source, interleave=True
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
    
    # Split into RSS articles and X/socials for two sections
    articles_rss = [a for a in articles if not (a.get("source") or "").startswith("X (")]
    articles_x = [a for a in articles if (a.get("source") or "").startswith("X (")]

    # Generate AI introduction from RSS articles only (topic narrative)
    print("✨ Generating AI introduction...")
    intro = generate_intro(articles_rss if articles_rss else articles)
    print(f"   Intro: {intro[:80]}...")

    # Subject line (include topic when topic-based)
    today = datetime.now().strftime("%b %d")
    if chosen_topic:
        subject = f"AI Newsy • {today} • {chosen_topic} • {len(articles)} Stories"
    else:
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

        html = generate_email_html(articles_rss, articles_x, intro=intro, unsubscribe_token=token)
        
        if send_email(email, html, subject):
            print(f"    ✓ Sent!")
            sent += 1
        else:
            print(f"    ✗ Failed")
            failed += 1
    
    # Mark articles as sent and record topic for rotation (only if not dry run, not test mode, and we sent to at least one person)
    if not dry_run and not test_email and sent > 0:
        article_ids = [a.get('id') for a in articles]
        mark_articles_sent(article_ids)
        if chosen_topic:
            insert_digest_log(chosen_topic)
            print(f"\n📌 Marked {len(article_ids)} articles as sent; recorded topic '{chosen_topic}' for rotation")
        else:
            print(f"\n📌 Marked {len(article_ids)} articles as sent")
    
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

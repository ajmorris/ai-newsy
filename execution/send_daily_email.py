"""
Send daily email digest to subscribers.
Compiles summarized articles and sends via SendGrid.
Includes AI-generated introduction synthesizing all stories.
"""

import os
import argparse
from datetime import datetime
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent
import google.generativeai as genai

import sys
sys.path.insert(0, '.')
from execution.database import get_unsent_articles, get_active_subscribers, mark_articles_sent

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


def generate_email_html(articles: list, intro: str, unsubscribe_token: str = "") -> str:
    """Generate HTML email content with minimal light design."""
    
    today = datetime.now().strftime("%B %d, %Y")
    
    # Build article cards - minimal design with opinions
    article_cards = ""
    for article in articles:
        source = article.get('source', 'Unknown Source')
        opinion = article.get('opinion', '')
        
        opinion_html = ""
        if opinion:
            opinion_html = f"""
            <div style="margin-top: 12px; padding-left: 12px; border-left: 2px solid #e5e7eb;">
                <p style="margin: 0; color: #6b7280; font-size: 13px; font-style: italic; line-height: 1.5;">
                    Takeaway: {opinion}
                </p>
            </div>
            """
            
        article_cards += f"""
        <div style="padding: 24px 0; border-bottom: 1px solid #f3f4f6;">
            <p style="margin: 0 0 6px 0; color: #9ca3af; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500;">
                {source}
            </p>
            <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 600; line-height: 1.4;">
                <a href="{article.get('url', '#')}" style="color: #111827; text-decoration: none;">{article.get('title', 'Untitled')}</a>
            </h3>
            <p style="margin: 0; color: #4b5563; font-size: 15px; line-height: 1.6;">
                {article.get('summary', 'No summary available.')}
            </p>
            {opinion_html}
        </div>
        """
    
    # Full email template - minimal light design
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;">
        <div style="max-width: 560px; margin: 0 auto; padding: 48px 24px;">
            
            <!-- Header -->
            <div style="margin-bottom: 32px;">
                <h1 style="color: #111827; font-size: 24px; margin: 0; font-weight: 700;">
                    AI Newsy
                </h1>
                <p style="color: #6b7280; margin: 4px 0 0 0; font-size: 14px;">
                    {today}
                </p>
            </div>
            
            <!-- Introduction -->
            <div style="margin-bottom: 32px; padding: 20px; background-color: #f9fafb; border-radius: 8px;">
                <p style="margin: 0; color: #374151; font-size: 16px; line-height: 1.7;">
                    {intro}
                </p>
            </div>
            
            <!-- Articles -->
            <div style="margin-bottom: 32px;">
                {article_cards}
            </div>
            
            <!-- Footer -->
            <div style="padding-top: 24px; border-top: 1px solid #e5e7eb;">
                <p style="color: #9ca3af; font-size: 13px; margin: 0; line-height: 1.6;">
                    You're receiving this because you subscribed to AI Newsy.
                    <a href="{APP_URL}/api/unsubscribe?token={unsubscribe_token}" 
                       style="color: #9ca3af; text-decoration: underline;">
                        Unsubscribe
                    </a>
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


def send_daily_digest(dry_run: bool = False) -> dict:
    """
    Send daily digest to all active subscribers.
    Returns dict with counts.
    """
    print(f"\n{'='*50}")
    print(f"Daily Email Digest - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")
    
    # Get articles to send
    articles = get_unsent_articles()
    if not articles:
        print("No unsent articles to include in digest.")
        return {"articles": 0, "sent": 0, "failed": 0}
    
    print(f"📰 {len(articles)} articles to include")
    
    # Get subscribers
    subscribers = get_active_subscribers()
    if not subscribers:
        print("No active subscribers.")
        return {"articles": len(articles), "sent": 0, "failed": 0}
    
    print(f"👥 {len(subscribers)} active subscribers")
    
    # Generate AI introduction (once for all subscribers)
    print("✨ Generating AI introduction...")
    intro = generate_intro(articles)
    print(f"   Intro: {intro[:80]}...")
    
    # Subject line
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
        
        html = generate_email_html(articles, intro=intro, unsubscribe_token=token)
        
        if send_email(email, html, subject):
            print(f"    ✓ Sent!")
            sent += 1
        else:
            print(f"    ✗ Failed")
            failed += 1
    
    # Mark articles as sent (only if not dry run and we sent to at least one person)
    if not dry_run and sent > 0:
        article_ids = [a.get('id') for a in articles]
        mark_articles_sent(article_ids)
        print(f"\n📌 Marked {len(article_ids)} articles as sent")
    
    print(f"\n{'='*50}")
    print(f"Summary: Sent to {sent}, Failed: {failed}")
    print(f"{'='*50}\n")
    
    return {"articles": len(articles), "sent": sent, "failed": failed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send daily email digest")
    parser.add_argument('--dry-run', action='store_true',
                        help="Process without sending emails")
    args = parser.parse_args()
    
    # Check for API key
    if not SENDGRID_API_KEY or SENDGRID_API_KEY == "your-sendgrid-api-key":
        print("⚠️  SENDGRID_API_KEY not configured in .env")
        print("   Get one at: https://sendgrid.com/")
        exit(1)
    
    result = send_daily_digest(dry_run=args.dry_run)
    print(f"Done! Sent digest with {result['articles']} articles to {result['sent']} subscribers.")

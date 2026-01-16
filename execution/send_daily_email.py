"""
Send daily email digest to subscribers.
Compiles summarized articles and sends via SendGrid.
"""

import os
import argparse
from datetime import datetime
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent

import sys
sys.path.insert(0, '.')
from execution.database import get_unsent_articles, get_active_subscribers, mark_articles_sent

load_dotenv()

# SendGrid configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "newsletter@example.com")
APP_URL = os.getenv("APP_URL", "https://your-app.vercel.app")


def generate_email_html(articles: list, unsubscribe_token: str = "") -> str:
    """Generate HTML email content from articles."""
    
    today = datetime.now().strftime("%B %d, %Y")
    
    # Build article cards
    article_cards = ""
    for article in articles:
        article_cards += f"""
        <div style="background: #1a1a2e; border-radius: 12px; padding: 20px; margin-bottom: 16px; border-left: 4px solid #6366f1;">
            <h3 style="margin: 0 0 8px 0; color: #e0e0e0; font-size: 16px;">
                <a href="{article.get('url', '#')}" style="color: #818cf8; text-decoration: none;">{article.get('title', 'Untitled')}</a>
            </h3>
            <p style="margin: 0 0 8px 0; color: #9ca3af; font-size: 12px;">
                {article.get('source', 'Unknown Source')}
            </p>
            <p style="margin: 0; color: #d1d5db; font-size: 14px; line-height: 1.5;">
                {article.get('summary', 'No summary available.')}
            </p>
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
    <body style="margin: 0; padding: 0; background-color: #0f0f1a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 32px;">
                <h1 style="color: #ffffff; font-size: 28px; margin: 0;">
                    🤖 AI Newsy
                </h1>
                <p style="color: #9ca3af; margin: 8px 0 0 0; font-size: 14px;">
                    Your Daily AI News Digest • {today}
                </p>
            </div>
            
            <!-- Articles -->
            <div style="margin-bottom: 32px;">
                {article_cards}
            </div>
            
            <!-- Footer -->
            <div style="text-align: center; padding-top: 24px; border-top: 1px solid #2d2d44;">
                <p style="color: #6b7280; font-size: 12px; margin: 0;">
                    You're receiving this because you subscribed to AI Newsy.
                </p>
                <p style="margin: 8px 0 0 0;">
                    <a href="{APP_URL}/api/unsubscribe?token={unsubscribe_token}" 
                       style="color: #6b7280; font-size: 12px; text-decoration: underline;">
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
    
    # Subject line
    today = datetime.now().strftime("%b %d")
    subject = f"🤖 AI Newsy • {today} • {len(articles)} Stories"
    
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
        
        html = generate_email_html(articles, unsubscribe_token=token)
        
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

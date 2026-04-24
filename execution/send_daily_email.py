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
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dotenv import load_dotenv
import resend

import sys
sys.path.insert(0, '.')
from execution.markdown_utils import md_inline_to_html as _md_inline_to_html
from execution.markdown_utils import parse_frontmatter as _parse_frontmatter
from execution.email_renderer_payload import (
    build_email_renderer_payload,
    normalize_article_for_email,
)
from execution.database import (
    get_active_subscribers,
    mark_articles_sent,
    insert_digest_log,
)
from execution.ai_client import generate_text_with_fallback
from execution.digest_payload import (
    DigestBuildOptions,
    load_or_build_digest_payload,
    write_sent_snapshot,
)

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
EMAIL_RENDERER_SCRIPT = Path("emails/render_email.mjs")


def _issue_number_from_digest_date(digest_date: str) -> str:
    """Build the short issue number from a YYYY-MM-DD digest date."""
    return "".join(ch for ch in digest_date if ch.isdigit())[-5:] or "00137"


def _build_digest_summary_line(digest_date: str, story_count: int) -> str:
    """Create canonical digest line used for subject and email header."""
    issue_number = _issue_number_from_digest_date(digest_date)
    return f"ISSUE {issue_number} · {story_count} STORIES · 11 MIN READ"


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
                '<div style="margin-top: 12px; padding: 12px 14px; background-color: #121214; '
                'border-left: 2px solid #39ff88; border-radius: 0 2px 2px 0;">'
                '<p style="margin: 0 0 4px 0; color: #39ff88; font-family: \'JetBrains Mono\', Menlo, monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.15em; font-weight: 700;">Why it matters</p>'
                f'<p style="margin: 0; color: #f4f3ef; font-size: 14px; line-height: 1.5;">{opinion}</p>'
                "</div>"
            )

        output.append(
            '<div style="padding: 24px 0; border-bottom: 1px solid #1d1d21;">'
            f'<p style="margin: 0 0 8px 0; color: #6b6a65; font-family: \'JetBrains Mono\', Menlo, monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.12em; font-weight: 600;">{source}</p>'
            f"{image_html}"
            f'<h3 style="margin: 0 0 8px 0; font-size: 22px; font-weight: 700; line-height: 1.3; letter-spacing: -0.03em;">'
            f'<a href="{link}" style="color: #f4f3ef; text-decoration: none; padding: 4px 0; display: inline-block;">{title}</a>'
            "</h3>"
            f'<p style="margin: 0; color: #a3a099; font-size: 15px; line-height: 1.6;">{summary}</p>'
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
            output.append(f'<h2 style="margin: 0 0 12px 0; font-size: 20px; font-weight: 700; color: #f4f3ef; letter-spacing: -0.03em;">{_md_inline_to_html(stripped[3:])}</h2>')
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
            output.append(f'<li style="margin-bottom: 10px; line-height: 1.6; color: #a3a099;">{_md_inline_to_html(stripped[2:])}</li>')
            continue

        flush_article()
        output.append(f'<p style="margin: 0 0 10px 0; color: #a3a099; font-size: 15px; line-height: 1.6;">{_md_inline_to_html(stripped)}</p>')

    close_list()
    flush_article()
    return "\n".join(output)


def _load_digest_markdown_email(
    digest_date: str,
    unsubscribe_token: str,
    digest_summary_line: str,
) -> Optional[Dict[str, str]]:
    markdown_dir = Path(os.getenv("DIGEST_MARKDOWN_DIR", "data/digests"))
    file_path = markdown_dir / f"{digest_date}.md"
    if not file_path.exists():
        return None

    raw = file_path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    subject = meta.get("subject", digest_summary_line)
    intro = meta.get("intro", "")
    body_html = _markdown_body_to_html(body)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #0b0b0c; color: #f4f3ef; font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
        <div style="max-width: 640px; margin: 0 auto; padding: 24px 16px;">
            <div style="background-color: #17171a; border: 1px solid #26262b;">
            <div style="margin-bottom: 32px;">
                <div style="padding: 28px 28px 18px; background-color: #121214; border-bottom: 1px solid #1d1d21;">
                    <h1 style="color: #f4f3ef; font-size: 34px; margin: 0 0 10px 0; font-weight: 700; letter-spacing: -1px; line-height: 1.1;">The AI feed, distilled.</h1>
                    <p style="color: #a3a099; margin: 0; font-size: 14px; line-height: 1.6;">{html.escape(intro)}</p>
                    <p style="color: #6b6a65; margin: 12px 0 0 0; font-family: 'JetBrains Mono', Menlo, monospace; font-size: 10px; letter-spacing: 1px; text-transform: uppercase;">{html.escape(digest_summary_line)}</p>
                </div>
            </div>
            <div style="margin-bottom: 32px;">
                <div style="padding: 0 28px 24px 28px;">{body_html}</div>
            </div>
            <div style="padding: 18px 28px 24px 28px; border-top: 1px solid #1d1d21;">
                <p style="color: #6b6a65; font-family: 'JetBrains Mono', Menlo, monospace; font-size: 10px; margin: 0; line-height: 1.8;">
                    You're receiving this because you subscribed to AI Newsy.
                    <a href="{APP_URL}/api/unsubscribe?token={unsubscribe_token}" style="color: #a3a099; text-decoration: underline;">unsubscribe</a>
                </p>
            </div>
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
    what_reading: Optional[Dict[str, object]] = None,
    what_watching: Optional[Dict[str, object]] = None,
    around_web: Optional[List[dict]] = None,
    unsubscribe_token: str = "",
    digest_summary_line: str = "",
) -> str:
    """Generate HTML email with grouped sections. Links and takeaways styled for clarity."""
    today = datetime.now().strftime("%B %d, %Y")
    summary_line = digest_summary_line or f"{today} · AI Newsy"

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
                <div style="margin-top: 12px; padding: 12px 14px; background-color: #121214; border-left: 2px solid #39ff88; border-radius: 0 2px 2px 0;">
                    <p style="margin: 0 0 4px 0; color: #39ff88; font-family: 'JetBrains Mono', Menlo, monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.15em; font-weight: 700;">Why it matters</p>
                    <p style="margin: 0; color: #f4f3ef; font-size: 14px; line-height: 1.5;">{opinion}</p>
                </div>
                """

            image_html = ""
            if image_url:
                title_esc = (article.get("title") or "Article").replace('"', "&quot;")
                image_html = f'<div style="margin-bottom: 12px;"><img src="{image_url}" alt="{title_esc}" style="max-width: 100%; height: auto; max-height: 200px; object-fit: cover; display: block; border-radius: 6px;" width="560" /></div>'

            article_cards += f"""
            <div style="padding: 24px 0; border-bottom: 1px solid #1d1d21;">
                <p style="margin: 0 0 8px 0; color: #6b6a65; font-family: 'JetBrains Mono', Menlo, monospace; font-size: 10px; text-transform: uppercase; letter-spacing: 0.12em; font-weight: 600;">
                    {source}
                </p>
                {image_html}
                <h3 style="margin: 0 0 8px 0; font-size: 22px; font-weight: 700; line-height: 1.3; letter-spacing: -0.03em;">
                    <a href="{article.get("url", "#")}" style="color: #f4f3ef; text-decoration: none; padding: 4px 0; display: inline-block;">{article.get("title", "Untitled")}</a>
                </h3>
                <p style="margin: 0; color: #a3a099; font-size: 15px; line-height: 1.6;">
                    {article.get("summary", "No summary available.")}
                </p>
                {opinion_html}
            </div>
            """

        section_blocks += f"""
        <div style="margin-bottom: 32px;">
            <h2 style="margin: 0 0 12px 0; font-size: 20px; font-weight: 700; color: #f4f3ef; letter-spacing: -0.03em;">
                {name}
            </h2>
            {article_cards}
        </div>
        """

    tweet_headlines = tweet_headlines or []
    community_headlines = community_headlines or []
    what_reading = what_reading or {}
    what_watching = what_watching or {}
    around_web = around_web or (tweet_headlines + community_headlines)

    reading_title = str(what_reading.get("title", "") or "What I'm Reading").strip()
    reading_essay = str(what_reading.get("essay", "") or "").strip()
    watching_title = str(what_watching.get("title", "") or "").strip()
    watching_url = str(what_watching.get("url", "") or "").strip()
    watching_channel = str(what_watching.get("channel", "") or "").strip()
    why_this_matters = str(what_watching.get("why_this_matters", "") or "").strip()
    why_im_sharing_it = str(what_watching.get("why_im_sharing_it", "") or "").strip()
    why_its_important = str(what_watching.get("why_its_important", "") or "").strip()

    tweet_section_html = ""
    if tweet_headlines:
        tweet_items_html = "".join(
            [f"<li style=\"margin-bottom: 10px; line-height: 1.6; color: #a3a099;\">{render_tweet_headline_html(item)}</li>" for item in tweet_headlines]
        )
        tweet_section_html = f"""
        <div style="margin-bottom: 32px;">
            <h2 style="margin: 0 0 12px 0; font-size: 20px; font-weight: 700; color: #f4f3ef; letter-spacing: -0.03em;">
                Here's what's going on in Twitter/X
            </h2>
            <ul style="padding-left: 20px; margin: 0;">
                {tweet_items_html}
            </ul>
        </div>
        """

    community_section_html = ""
    if community_headlines:
        community_items_html = "".join(
            [f"<li style=\"margin-bottom: 10px; line-height: 1.6; color: #a3a099;\">{render_tweet_headline_html(item)}</li>" for item in community_headlines]
        )
        community_section_html = f"""
        <div style="margin-bottom: 32px;">
            <h2 style="margin: 0 0 12px 0; font-size: 20px; font-weight: 700; color: #f4f3ef; letter-spacing: -0.03em;">
                Here's what we're hearing from the community
            </h2>
            <ul style="padding-left: 20px; margin: 0;">
                {community_items_html}
            </ul>
        </div>
        """

    around_rows = []
    for item in around_web[:12]:
        source_label = str(item.get("source_label", "") or "").strip()
        source_suffix = f' <span style="color:#6b6a65;">({source_label})</span>' if source_label else ""
        around_rows.append(
            f'<li style="margin-bottom: 10px; line-height: 1.6; color: #a3a099;">'
            f"{render_tweet_headline_html(item)}{source_suffix}</li>"
        )
    around_items_html = "".join(around_rows)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #0b0b0c; color: #f4f3ef; font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
        <div style="max-width: 640px; margin: 0 auto; padding: 24px 16px;">
            <div style="background-color: #17171a; border: 1px solid #26262b;">
            <div style="margin-bottom: 32px;">
                <div style="padding: 28px 28px 18px; background-color: #121214; border-bottom: 1px solid #1d1d21;">
                    <h1 style="color: #f4f3ef; font-size: 34px; margin: 0 0 10px 0; font-weight: 700; letter-spacing: -1px; line-height: 1.1;">What I am learning in AI today.</h1>
                    <p style="color: #a3a099; margin: 0; font-size: 14px; line-height: 1.6;">{intro}</p>
                    <p style="color: #6b6a65; margin: 12px 0 0 0; font-family: 'JetBrains Mono', Menlo, monospace; font-size: 10px; letter-spacing: 1px; text-transform: uppercase;">{summary_line}</p>
                </div>
            </div>
            <div style="padding: 0 28px 12px 28px;">
                <h2 style="margin: 0 0 12px 0; font-size: 20px; font-weight: 700; color: #f4f3ef;">What I'm Reading</h2>
                <p style="margin: 0 0 8px 0; color: #f4f3ef; font-size: 18px; font-weight: 600;">{reading_title}</p>
                <p style="margin: 0; color: #a3a099; font-size: 15px; line-height: 1.7; white-space: pre-line;">{reading_essay}</p>
            </div>
            <div style="padding: 16px 28px 12px 28px;">
                <h2 style="margin: 0 0 12px 0; font-size: 20px; font-weight: 700; color: #f4f3ef;">What I'm Watching</h2>
                <p style="margin: 0 0 6px 0; color: #f4f3ef; font-size: 18px; font-weight: 600;">
                    <a href="{watching_url or '#'}" style="color:#f4f3ef;text-decoration:underline;">{watching_title or 'No video selected today'}</a>
                </p>
                <p style="margin: 0 0 10px 0; color: #6b6a65; font-family: 'JetBrains Mono', Menlo, monospace; font-size: 11px;">{watching_channel}</p>
                <p style="margin: 0 0 6px 0; color: #a3a099; font-size: 14px; line-height: 1.6;"><strong>Why this matters:</strong> {why_this_matters}</p>
                <p style="margin: 0 0 6px 0; color: #a3a099; font-size: 14px; line-height: 1.6;"><strong>Why I'm sharing it:</strong> {why_im_sharing_it}</p>
                <p style="margin: 0; color: #a3a099; font-size: 14px; line-height: 1.6;"><strong>Why it's important:</strong> {why_its_important}</p>
            </div>
            <div style="padding: 0 28px 18px 28px;">
                <h2 style="margin: 0 0 12px 0; font-size: 20px; font-weight: 700; color: #f4f3ef;">Around the Web</h2>
                <ul style="padding-left: 20px; margin: 0;">{around_items_html}</ul>
            </div>
            <div style="padding: 18px 28px 24px 28px; border-top: 1px solid #1d1d21;">
                <p style="color: #6b6a65; font-family: 'JetBrains Mono', Menlo, monospace; font-size: 10px; margin: 0; line-height: 1.8;">
                    You're receiving this because you subscribed to AJ's daily AI brief.
                    <a href="{APP_URL}/api/unsubscribe?token={unsubscribe_token}" style="color: #a3a099; text-decoration: underline;">unsubscribe</a>
                </p>
            </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def _render_email_with_mjml(payload: Dict[str, object]) -> Optional[str]:
    if not EMAIL_RENDERER_SCRIPT.exists():
        return None

    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as payload_file:
            json.dump(payload, payload_file)
            payload_path = payload_file.name

        result = subprocess.run(
            ["node", str(EMAIL_RENDERER_SCRIPT), payload_path],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        print(f"    MJML renderer failed: {exc.stderr.strip()}")
        return None
    except Exception as exc:
        print(f"    Unexpected MJML renderer error: {exc}")
        return None
    finally:
        if "payload_path" in locals() and os.path.exists(payload_path):
            os.remove(payload_path)


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
            f'<a href="{safe_url}" style="color: #39ff88; text-decoration: underline;">Source</a>'
        )

    anchor_text = match.group(1)
    safe_anchor = html.escape(anchor_text)
    safe_url = html.escape(url, quote=True)
    linked = f'<a href="{safe_url}" style="color: #39ff88; text-decoration: underline;">{safe_anchor}</a>'
    replaced = headline[:match.start()] + linked + headline[match.end():]
    return html.escape(replaced).replace(html.escape(linked), linked)


def send_email(to_email: str, html_content: str, subject: str) -> bool:
    """Send a single email via Resend."""
    try:
        params = {
            "from": f"AJ Morris <{EMAIL_FROM}>",
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
    digest_date: Optional[str] = None,
    overwrite_snapshot: bool = False,
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

    payload = load_or_build_digest_payload(
        DigestBuildOptions(
            digest_date=digest_date,
            window_hours=int(os.getenv("DIGEST_WINDOW_HOURS", "24")),
            use_sent=sent_yesterday,
        )
    )
    digest_date = str(payload.get("digest_date"))
    stories = list(payload.get("stories", []))

    if not stories:
        print("No matching articles to include in digest.")
        return {"articles": 0, "sent": 0, "failed": 0}

    articles = [normalize_article_for_email(article) for article in stories]

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

    digest_summary_line = str(payload.get("subject_line", _build_digest_summary_line(digest_date, len(articles))))
    subject = digest_summary_line
    if sent_yesterday:
        subject = f"[TEST Replay] {subject}"

    sent = 0
    failed = 0

    sections = list(payload.get("sections", [])) or group_articles_by_category(articles)
    tweet_headlines = list(payload.get("tweet_headlines", []))
    community_headlines = list(payload.get("community_headlines", []))
    what_reading = dict(payload.get("what_reading", {}) or {})
    what_watching = dict(payload.get("what_watching", {}) or {})
    around_web = list(payload.get("around_web", []) or [])
    intro = str(payload.get("intro", ""))

    send_started_at = datetime.utcnow().isoformat()
    snapshot_path = None
    if not dry_run:
        snapshot_path = write_sent_snapshot(
            payload=payload,
            allow_overwrite=overwrite_snapshot,
            metadata={
                "created_by": "send_daily_email",
                "send_mode": "test" if test_email else "production",
                "send_started_at": send_started_at,
            },
        )
        print(f"🧊 Sent snapshot path: {snapshot_path}")

    for subscriber in subscribers:
        email = subscriber.get('email')
        token = subscriber.get('confirm_token', '')

        print(f"  Sending to: {email}...")

        if dry_run:
            print(f"    [DRY RUN] Would send {len(articles)} articles")
            sent += 1
            continue

        payload = build_email_renderer_payload(
            sections=sections,
            intro=intro,
            subject=digest_summary_line,
            unsubscribe_token=token,
            digest_date=digest_date,
            tweet_headlines=tweet_headlines,
            community_headlines=community_headlines,
            what_reading=what_reading,
            what_watching=what_watching,
            around_web=around_web,
        )
        rendered_html = _render_email_with_mjml(payload)

        if rendered_html:
            html = rendered_html
            subject_to_send = subject
        else:
            compiled = _load_digest_markdown_email(
                digest_date=digest_date,
                unsubscribe_token=token,
                digest_summary_line=digest_summary_line,
            )
            if compiled:
                html = compiled["html"]
                subject_to_send = compiled["subject"]
            else:
                html = generate_email_html(
                    sections,
                    intro=intro,
                    tweet_headlines=tweet_headlines,
                    community_headlines=community_headlines,
                    what_reading=what_reading,
                    what_watching=what_watching,
                    around_web=around_web,
                    unsubscribe_token=token,
                    digest_summary_line=digest_summary_line,
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
        article_ids = [a.get('id') for a in articles if a.get("id") is not None]
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
    parser.add_argument('--digest-date', type=str, default=None,
                        help="Build/send digest for YYYY-MM-DD canonical payload date")
    parser.add_argument('--overwrite-snapshot', action='store_true',
                        help="Allow replacing existing sent snapshot for digest date")
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
        digest_date=args.digest_date,
        overwrite_snapshot=args.overwrite_snapshot,
    )
    print(f"Done! Sent digest with {result['articles']} articles to {result['sent']} subscribers.")

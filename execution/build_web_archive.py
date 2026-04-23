"""Build static web archive pages from canonical digest JSON files."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ARCHIVE_DIR = Path(os.getenv("DIGEST_MARKDOWN_DIR", "data/digests"))
SNAPSHOT_DIR = Path(os.getenv("DIGEST_SNAPSHOT_DIR", str(ARCHIVE_DIR / "snapshots")))
OUTPUT_DIR = Path(os.getenv("WEB_ARCHIVE_OUTPUT_DIR", "frontend/issues"))
MANIFEST_PATH = OUTPUT_DIR / "index.json"
SITE_TITLE = "AI Newsy"
MAX_RECENT_ISSUES = int(os.getenv("WEB_ARCHIVE_RECENT_COUNT", "12"))


@dataclass
class DigestIssue:
    """Represents one digest issue for web publishing."""

    digest_date: str
    subject: str
    intro: str
    article_count: int
    body_html: str
    slug: str
    source_file: str
    issue_label: str = ""
    content_hash: str = ""

    @property
    def url_path(self) -> str:
        return f"/issues/{self.slug}.html"

    @property
    def display_date(self) -> str:
        try:
            parsed = datetime.strptime(self.digest_date, "%Y-%m-%d")
            return parsed.strftime("%b %d, %Y")
        except ValueError:
            return self.digest_date

    def to_manifest_item(self) -> Dict[str, object]:
        return {
            "slug": self.slug,
            "digestDate": self.digest_date,
            "displayDate": self.display_date,
            "issueNumber": self.issue_label,
            "subject": self.subject,
            "intro": self.intro,
            "articleCount": self.article_count,
            "urlPath": self.url_path,
            "contentHash": self.content_hash,
        }


def _issue_label_from_issue_id(issue_id: str) -> str:
    return issue_id[-5:] if issue_id else "00137"


def _render_tweet_headline_html(item: Dict[str, object]) -> str:
    headline = str(item.get("headline", "")).strip()
    url = str(item.get("url", "")).strip()
    if not headline:
        return ""
    if not url:
        return html.escape(headline)

    match = re.search(r"__(.+?)__", headline)
    if not match:
        return (
            f"{html.escape(headline)} "
            f'<a href="{html.escape(url, quote=True)}" style="color: #39ff88; text-decoration: underline;">Source</a>'
        )

    anchor_text = match.group(1)
    safe_anchor = html.escape(anchor_text)
    safe_url = html.escape(url, quote=True)
    linked = f'<a href="{safe_url}" style="color: #39ff88; text-decoration: underline;">{safe_anchor}</a>'
    replaced = headline[:match.start()] + linked + headline[match.end():]
    return html.escape(replaced).replace(html.escape(linked), linked)


def _render_story(story: Dict[str, Any]) -> str:
    source = html.escape(str(story.get("source", "Unknown Source")))
    title = html.escape(str(story.get("title", "Untitled")))
    link = html.escape(str(story.get("url", "#")), quote=True)
    summary = html.escape(str(story.get("summary", "")))
    opinion = html.escape(str(story.get("opinion", "")))
    image_url = html.escape(str(story.get("image_url", "")), quote=True)
    image_alt = title
    image_html = ""
    if image_url:
        image_html = (
            f'<div style="margin-bottom: 12px;"><img src="{image_url}" alt="{image_alt}" '
            f'style="max-width: 100%; height: auto; border-radius: 8px;" /></div>'
        )
    opinion_html = ""
    if opinion:
        opinion_html = (
            '<div style="margin-top: 12px; padding: 12px 14px; background-color: #121214; '
            'border-left: 2px solid #39ff88; border-radius: 0 2px 2px 0;">'
            '<p style="margin: 0 0 4px 0; color: #39ff88; font-family: JetBrains Mono, monospace; '
            'font-size: 10px; text-transform: uppercase; letter-spacing: 0.15em; font-weight: 700;">Why it matters</p>'
            f'<p style="margin: 0; color: #f4f3ef; font-size: 14px; line-height: 1.5;">{opinion}</p>'
            '</div>'
        )
    return (
        '<article style="padding: 24px 0; border-bottom: 1px solid #1d1d21;">'
        f'<p style="margin: 0 0 8px 0; color: #6b6a65; font-family: JetBrains Mono, monospace; '
        f'font-size: 10px; text-transform: uppercase; letter-spacing: 0.12em; font-weight: 600;">{source}</p>'
        f'{image_html}'
        f'<h3 style="margin: 0 0 8px 0; font-size: 22px; font-weight: 700; line-height: 1.3; letter-spacing: -0.03em;">'
        f'<a href="{link}" style="color: #f4f3ef; text-decoration: none; padding: 4px 0; display: inline-block;">{title}</a>'
        '</h3>'
        f'<p style="margin: 0; color: #a3a099; font-size: 15px; line-height: 1.6;">{summary}</p>'
        f'{opinion_html}'
        '</article>'
    )


def _render_body_from_payload(payload: Dict[str, Any]) -> str:
    parts: List[str] = []
    for section in payload.get("sections", []):
        section_name = html.escape(str(section.get("name", "")))
        parts.append(
            f'<h2 style="margin: 28px 0 10px; font-size: 20px; color: #f4f3ef;">{section_name}</h2>'
        )
        for story in section.get("articles", []):
            parts.append(_render_story(story))

    tweet_headlines = payload.get("tweet_headlines", [])
    if tweet_headlines:
        parts.append('<h2 style="margin: 28px 0 10px; font-size: 20px; color: #f4f3ef;">From X/Twitter</h2>')
        parts.append('<ul style="padding-left: 22px; margin: 10px 0 18px;">')
        for item in tweet_headlines:
            parts.append(
                '<li style="margin-bottom: 10px; color: #a3a099; font-size: 15px; line-height: 1.6;">'
                f'{_render_tweet_headline_html(item)}</li>'
            )
        parts.append("</ul>")

    community_headlines = payload.get("community_headlines", [])
    if community_headlines:
        parts.append('<h2 style="margin: 28px 0 10px; font-size: 20px; color: #f4f3ef;">From Reddit/HN/YC</h2>')
        parts.append('<ul style="padding-left: 22px; margin: 10px 0 18px;">')
        for item in community_headlines:
            label = str(item.get("source_label", "")).strip()
            headline = str(item.get("headline", "")).strip()
            url = str(item.get("url", "")).strip()
            display = f"[{label}] {headline}" if label else headline
            parts.append(
                '<li style="margin-bottom: 10px; color: #a3a099; font-size: 15px; line-height: 1.6;">'
                f'{_render_tweet_headline_html({"headline": display, "url": url})}</li>'
            )
        parts.append("</ul>")

    return "\n".join(parts)


def _read_issue(json_path: Path) -> Optional[DigestIssue]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    digest_date = str(payload.get("digest_date", json_path.stem))
    subject = str(payload.get("subject_line", f"{SITE_TITLE} • {digest_date}"))
    issue_id = str(payload.get("issue_id", "")).strip()
    issue_label = _issue_label_from_issue_id(issue_id)
    intro = str(payload.get("intro", ""))
    article_count = int(payload.get("article_count", 0) or 0)
    body_html = _render_body_from_payload(payload)
    slug = json_path.stem
    if slug.endswith(".sent"):
        slug = slug[: -len(".sent")]
    return DigestIssue(
        digest_date=digest_date,
        subject=subject,
        intro=intro,
        article_count=article_count,
        body_html=body_html,
        slug=slug,
        source_file=str(json_path),
        issue_label=issue_label,
        content_hash=str(payload.get("content_hash", "")),
    )


def _render_issue_page(issue: DigestIssue) -> str:
    intro_text = html.escape(issue.intro)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{issue.subject} | AI News Daily</title>
  <meta name="description" content="Read the {issue.display_date} issue of {SITE_TITLE}.">
  <style>
    :root {{
      --bg: #0b0b0c;
      --bg-raised: #121214;
      --card: #17171a;
      --line: #26262b;
      --line-soft: #1d1d21;
      --fg: #f4f3ef;
      --muted: #a3a099;
      --dim: #6b6a65;
      --brand: #39ff88;
      --brand-ink: #0b0b0c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      line-height: 1.6;
    }}
    .page {{
      max-width: 860px;
      margin: 0 auto;
      padding: 36px 20px 56px;
    }}
    .top-nav {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 28px;
      font-size: 12px;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .top-nav a {{
      color: var(--brand);
      text-decoration: none;
      font-weight: 500;
    }}
    .issue-header h1 {{
      margin: 0;
      font-size: 44px;
      line-height: 1.05;
      letter-spacing: -1.4px;
    }}
    .issue-header p {{
      margin: 6px 0 0;
      color: var(--dim);
      font-family: "JetBrains Mono", ui-monospace, monospace;
      font-size: 12px;
      letter-spacing: 1px;
      text-transform: uppercase;
    }}
    .cta {{
      margin: 24px 0;
      padding: 18px 20px;
      border-radius: 4px;
      background: var(--bg-raised);
      border: 1px solid var(--line);
    }}
    .cta h2 {{
      margin: 0 0 8px;
      font-size: 18px;
    }}
    .cta p {{
      margin: 0 0 12px;
      color: var(--muted);
    }}
    .cta a {{
      display: inline-block;
      background: var(--brand);
      color: var(--brand-ink);
      text-decoration: none;
      padding: 10px 14px;
      border-radius: 2px;
      font-weight: 600;
      font-size: 12px;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .intro {{
      margin: 0 0 28px;
      padding: 20px;
      border-radius: 4px;
      background: var(--bg-raised);
      font-size: 16px;
      color: var(--muted);
      border: 1px solid var(--line);
    }}
    .content {{
      margin: 0 0 28px;
      border: 1px solid var(--line);
      border-radius: 4px;
      background: var(--card);
      padding: 0 24px;
    }}
    .issue-footer {{
      border-top: 1px solid var(--line-soft);
      padding-top: 20px;
      color: var(--dim);
      font-size: 12px;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .issue-footer a {{
      color: var(--brand);
    }}
    @media (max-width: 520px) {{
      .issue-header h1 {{ font-size: 30px; }}
      .content {{ padding: 0 14px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <nav class="top-nav">
      <a href="/">← Home</a>
      <a href="/issues/">All issues</a>
    </nav>
    <header class="issue-header">
      <h1>AI News Daily</h1>
      <p>Issue {issue.issue_label} · {issue.display_date} · {issue.article_count} stories</p>
    </header>

    <section class="cta">
      <h2>Get this in your inbox every morning</h2>
      <p>Subscribe for the daily AI briefing with curated context and summaries.</p>
      <a href="/#subscribe-form">Subscribe free</a>
    </section>

    <section class="intro">
      {intro_text}
    </section>

    <article class="content">
      {issue.body_html}
    </article>

    <section class="cta">
      <h2>Never miss the next issue</h2>
      <p>Read on the web or get tomorrow's issue delivered directly by email.</p>
      <a href="/#subscribe-form">Join AI Newsy</a>
    </section>

    <footer class="issue-footer">
      <p>Explore more editions on the <a href="/issues/">web archive</a>.</p>
    </footer>
  </main>
</body>
</html>
"""


def _render_archive_index(issues: List[DigestIssue]) -> str:
    issue_items = "\n".join(
        [
            (
                f'<li>'
                f'<span class="issue-id">#{issue.issue_label}</span>'
                f'<span class="issue-date">{issue.display_date}</span>'
                f'<a href="{issue.slug}.html">{html.escape(issue.subject)}</a>'
                f'<span>{issue.article_count} stories</span>'
                f'<span class="chev">→</span>'
                f'</li>'
            )
            for issue in issues
        ]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI News Daily Archive</title>
  <style>
    :root {{
      --bg: #0b0b0c;
      --bg-raised: #121214;
      --card: #17171a;
      --line: #26262b;
      --line-soft: #1d1d21;
      --fg: #f4f3ef;
      --muted: #a3a099;
      --dim: #6b6a65;
      --brand: #39ff88;
      --brand-ink: #0b0b0c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    main {{
      max-width: 920px;
      margin: 0 auto;
      padding: 36px 20px 56px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 56px; line-height: 1; letter-spacing: -2px; }}
    p {{ margin: 0 0 20px; color: var(--muted); }}
    .back-link {{
      color: var(--brand);
      text-decoration: none;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      text-transform: uppercase;
      letter-spacing: 1px;
      font-size: 12px;
    }}
    .cta {{
      margin: 0 0 24px;
      padding: 16px;
      border-radius: 4px;
      border: 1px solid var(--line);
      background: var(--bg-raised);
    }}
    .cta a {{
      color: var(--brand);
      font-weight: 600;
      text-decoration: none;
    }}
    ul {{
      list-style: none;
      margin: 0;
      padding: 0;
      border: 1px solid var(--line);
      border-radius: 4px;
      overflow: hidden;
    }}
    li {{
      display: grid;
      grid-template-columns: 100px 110px 1fr 90px 20px;
      gap: 12px;
      align-items: center;
      padding: 16px 16px;
      border-bottom: 1px solid var(--line-soft);
      background: var(--card);
    }}
    li:last-child {{ border-bottom: 0; }}
    a {{ color: var(--fg); text-decoration: none; font-weight: 600; }}
    span {{ color: var(--dim); font-size: 12px; font-family: "JetBrains Mono", ui-monospace, monospace; text-transform: uppercase; letter-spacing: 1px; }}
    .issue-id, .issue-date {{ color: var(--dim); }}
    .chev {{ text-align: right; color: var(--muted); }}
    @media (max-width: 640px) {{
      h1 {{ font-size: 32px; letter-spacing: -1.2px; }}
      li {{ grid-template-columns: 74px 1fr 20px; }}
      .issue-date, li span:nth-child(4) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <main>
    <a class="back-link" href="/">← Back to home</a>
    <h1>Recent editions.</h1>
    <p>Browse every published issue.</p>
    <div class="cta">
      Prefer this in your inbox? <a href="/#subscribe-form">Subscribe to AI Newsy</a>.
    </div>
    <ul>
      {issue_items}
    </ul>
  </main>
</body>
</html>
"""


def build_web_archive(slug_prefix: str = "", use_canonical_fallback: bool = False) -> Dict[str, int]:
    if not SNAPSHOT_DIR.exists() and not use_canonical_fallback:
        raise FileNotFoundError(f"Sent snapshot directory not found: {SNAPSHOT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    issue_files = sorted(SNAPSHOT_DIR.glob("*.sent.json"))
    if not issue_files and use_canonical_fallback:
        issue_files = sorted(ARCHIVE_DIR.glob("*.json"))
    if not issue_files:
        raise FileNotFoundError(
            "No sent snapshots found. Expected files like data/digests/snapshots/YYYY-MM-DD.sent.json"
        )

    issues: List[DigestIssue] = []
    for issue_file in issue_files:
        issue = _read_issue(issue_file)
        if issue is not None:
            if slug_prefix:
                issue.slug = f"{slug_prefix}{issue.slug}"
            issues.append(issue)

    issues.sort(key=lambda item: item.digest_date, reverse=True)

    for issue in issues:
        output_file = OUTPUT_DIR / f"{issue.slug}.html"
        output_file.write_text(_render_issue_page(issue), encoding="utf-8")

    (OUTPUT_DIR / "index.html").write_text(_render_archive_index(issues), encoding="utf-8")

    latest = issues[0].to_manifest_item() if issues else None
    recent = [issue.to_manifest_item() for issue in issues[:MAX_RECENT_ISSUES]]
    generated_at = (
        f"{latest['digestDate']}T00:00:00Z" if latest else "1970-01-01T00:00:00Z"
    )
    payload = {
        "generatedAt": generated_at,
        "issueCount": len(issues),
        "latestIssue": latest,
        "recentIssues": recent,
    }
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {"issues": len(issues)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build web archive from canonical digest JSON.")
    parser.add_argument("--slug-prefix", type=str, default="")
    parser.add_argument("--use-canonical-fallback", action="store_true")
    args = parser.parse_args()
    result = build_web_archive(
        slug_prefix=args.slug_prefix,
        use_canonical_fallback=args.use_canonical_fallback,
    )
    print(f"Built web archive with {result['issues']} issues.")

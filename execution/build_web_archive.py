"""
Build static web archive pages from digest markdown files.
"""

from __future__ import annotations

import json
import os
import sys
import html
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from execution.markdown_utils import md_inline_to_html, parse_frontmatter


ARCHIVE_DIR = Path(os.getenv("DIGEST_MARKDOWN_DIR", "data/digests"))
OUTPUT_DIR = Path(os.getenv("WEB_ARCHIVE_OUTPUT_DIR", "frontend/issues"))
MANIFEST_PATH = OUTPUT_DIR / "index.json"
ARCHIVE_INDEX_PATH = OUTPUT_DIR / "index.html"
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
        digits = "".join(ch for ch in self.slug if ch.isdigit())
        issue_number = digits[-5:] if digits else "00000"
        return {
            "slug": self.slug,
            "digestDate": self.digest_date,
            "displayDate": self.display_date,
            "issueNumber": issue_number,
            "subject": self.subject,
            "intro": self.intro,
            "articleCount": self.article_count,
            "urlPath": self.url_path,
        }


def _read_issue(markdown_path: Path) -> Optional[DigestIssue]:
    raw = markdown_path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(raw)

    digest_date = metadata.get("digest_date", markdown_path.stem)
    subject = metadata.get("subject", f"{SITE_TITLE} • {digest_date}")
    intro = metadata.get("intro", "")

    article_count_raw = metadata.get("article_count", "0")
    try:
        article_count = int(str(article_count_raw).strip())
    except ValueError:
        article_count = 0

    body_html = _digest_markdown_to_web_html(body)
    slug = markdown_path.stem

    return DigestIssue(
        digest_date=digest_date,
        subject=subject,
        intro=intro,
        article_count=article_count,
        body_html=body_html,
        slug=slug,
        source_file=str(markdown_path),
    )


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


def _digest_markdown_to_web_html(markdown_body: str) -> str:
    lines = markdown_body.splitlines()
    output: List[str] = []

    current_section_open = False
    current_section_title = ""
    in_tweet_list = False
    in_json_block = False
    json_lines: List[str] = []
    article: Optional[Dict[str, str]] = None

    def close_tweet_list() -> None:
        nonlocal in_tweet_list
        if in_tweet_list:
            output.append("</ul>")
            in_tweet_list = False

    def flush_article() -> None:
        nonlocal article
        if not article:
            return

        title_html = md_inline_to_html(article.get("title", "Untitled"))
        link = article.get("url", "#")
        source = html.escape(article.get("source", ""))
        summary = md_inline_to_html(article.get("summary", ""))
        opinion = md_inline_to_html(article.get("opinion", ""))
        image_url = html.escape(article.get("image_url", ""), quote=True)
        image_alt = html.escape(article.get("title", "Article"), quote=True)

        image_html = ""
        if image_url:
            image_html = (
                f'<div style="margin-bottom: 12px;">'
                f'<img src="{image_url}" alt="{image_alt}" '
                f'style="max-width: 100%; height: auto; border-radius: 8px;" />'
                f"</div>"
            )

        opinion_html = ""
        if opinion:
            opinion_html = (
                '<div style="margin-top: 12px; padding: 12px 14px; background-color: #121214; '
                'border-left: 3px solid #39ff88; border-radius: 0 4px 4px 0;">'
                '<p style="margin: 0 0 4px 0; color: #39ff88; font-size: 11px; text-transform: uppercase; '
                'letter-spacing: 0.05em; font-weight: 600;">Takeaway</p>'
                f'<p style="margin: 0; color: #f4f3ef; font-size: 15px; line-height: 1.6;">{opinion}</p>'
                "</div>"
            )

        output.append(
            '<article style="padding: 22px 0; border-bottom: 1px solid #d1d1e9;">'
            f'<p style="margin: 0 0 6px 0; color: #39ff88; font-size: 11px; text-transform: uppercase; '
            f'letter-spacing: 0.05em; font-weight: 600;">{source}</p>'
            f"{image_html}"
            f'<h3 style="margin: 0 0 8px 0; font-size: 24px; line-height: 1.3;">'
            f'<a href="{html.escape(link, quote=True)}" style="color: #39ff88; text-decoration: underline;">{title_html}</a>'
            "</h3>"
            f'<p style="margin: 0; color: #a3a099; font-size: 16px; line-height: 1.7;">{summary}</p>'
            f"{opinion_html}"
            "</article>"
        )
        article = None

    for raw_line in lines:
        line = raw_line.strip()

        if in_json_block:
            if line == "```":
                in_json_block = False
                try:
                    payload = json.loads("\n".join(json_lines))
                    if article is not None:
                        article["summary"] = str(payload.get("summary", "")).strip()
                        article["opinion"] = str(payload.get("opinion", "")).strip()
                        raw_image = payload.get("image_url")
                        article["image_url"] = str(raw_image).strip() if raw_image else ""
                except json.JSONDecodeError:
                    if article is not None:
                        article["summary"] = "\n".join(json_lines).strip()
                json_lines = []
            else:
                json_lines.append(raw_line)
            continue

        if not line:
            continue

        if line.startswith("## "):
            close_tweet_list()
            flush_article()
            current_section_title = line[3:].strip()
            current_section_open = True
            output.append(
                f'<h2 style="margin: 28px 0 10px; font-size: 20px; color: #f4f3ef;">'
                f"{md_inline_to_html(current_section_title)}</h2>"
            )
            continue

        if line.startswith("### "):
            close_tweet_list()
            flush_article()
            title_line = line[4:].strip()
            link_match = re.match(r"\[(.+?)\]\((https?://[^\)]+)\)", title_line)
            if link_match:
                article = {
                    "title": link_match.group(1),
                    "url": link_match.group(2),
                    "source": "",
                    "summary": "",
                    "opinion": "",
                    "image_url": "",
                }
            else:
                article = {
                    "title": title_line,
                    "url": "#",
                    "source": "",
                    "summary": "",
                    "opinion": "",
                    "image_url": "",
                }
            continue

        if line.startswith("*") and line.endswith("*") and article is not None:
            article["source"] = line.strip("*").strip()
            continue

        if line == "```json":
            in_json_block = True
            json_lines = []
            continue

        if line.startswith("- "):
            flush_article()
            if not in_tweet_list:
                output.append('<ul style="padding-left: 22px; margin: 10px 0 18px;">')
                in_tweet_list = True
            bullet_content = line[2:].strip()
            source_match = re.match(r"(.+?)\(\[Source\]\((https?://[^\)]+)\)\)\s*$", bullet_content)
            if source_match:
                item = {"headline": source_match.group(1).strip(), "url": source_match.group(2).strip()}
                bullet_html = _render_tweet_headline_html(item)
            else:
                bullet_html = md_inline_to_html(bullet_content)
            output.append(
                '<li style="margin-bottom: 10px; color: #a3a099; font-size: 15px; line-height: 1.6;">'
                f"{bullet_html}</li>"
            )
            continue

        close_tweet_list()
        if current_section_open and current_section_title and article is None:
            output.append(
                f'<p style="margin: 0 0 10px 0; color: #a3a099; font-size: 15px; line-height: 1.6;">'
                f"{md_inline_to_html(line)}</p>"
            )

    close_tweet_list()
    flush_article()
    return "\n".join(output)


def _render_issue_page(issue: DigestIssue) -> str:
    intro_text = html.escape(issue.intro)
    issue_digits = "".join(ch for ch in issue.slug if ch.isdigit())
    issue_number = issue_digits[-5:] if issue_digits else "00000"

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
      <p>Issue #{issue_number} · {issue.display_date} · {issue.article_count} stories</p>
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
                f'<span class="issue-id">#{("".join(ch for ch in issue.slug if ch.isdigit())[-5:] or "00000")}</span>'
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


def build_web_archive() -> Dict[str, int]:
    if not ARCHIVE_DIR.exists():
        raise FileNotFoundError(f"Digest directory not found: {ARCHIVE_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    issue_files = sorted(ARCHIVE_DIR.glob("*.md"))
    issues: List[DigestIssue] = []
    for issue_file in issue_files:
        issue = _read_issue(issue_file)
        if issue is not None:
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
    result = build_web_archive()
    print(f"Built web archive with {result['issues']} issues.")

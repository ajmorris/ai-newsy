"""
Shared markdown/frontmatter helpers used by digest scripts.
"""

from __future__ import annotations

import html
import re
from typing import Dict, Tuple


def parse_frontmatter(markdown_text: str) -> Tuple[Dict[str, str], str]:
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


def md_inline_to_html(text: str) -> str:
    """Render a minimal subset of inline markdown to HTML."""
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(
        r"\[(.+?)\]\((https?://[^\)]+)\)",
        r'<a href="\2" style="color: #6246ea; text-decoration: underline;">\1</a>',
        escaped,
    )
    return escaped

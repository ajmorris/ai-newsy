"""Canonical URL identity used to collapse duplicate article links."""

from __future__ import annotations

from typing import Dict, Iterable, List
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_DROP_QUERY_KEYS = {"ref", "source"}


def canonical_url(url: str) -> str:
    """Normalize a URL so tracking parameters and host variants compare equal."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return url.strip().lower()

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "x.com":
        host = "twitter.com"

    clean_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _DROP_QUERY_KEYS
    ]
    query = urlencode(clean_query, doseq=True)
    path = parsed.path.rstrip("/")
    scheme = parsed.scheme.lower() or "https"
    return urlunparse((scheme, host, path, "", query, ""))


def dedupe_by_canonical_url(articles: Iterable[Dict]) -> List[Dict]:
    """Keep the first article for each canonical URL. Items without a URL stay."""
    seen = set()
    kept: List[Dict] = []
    for article in articles:
        url = str(article.get("url", "") or "").strip()
        if not url:
            kept.append(article)
            continue
        key = canonical_url(url)
        if key in seen:
            continue
        seen.add(key)
        kept.append(article)
    return kept

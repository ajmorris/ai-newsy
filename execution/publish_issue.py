"""POST a canonical issue to the Cloudflare worker when that URL is configured.

The daily finalize job keeps writing data/digests/YYYY-MM-DD.json. This step
is a no-op until CLOUDFLARE_PUBLISH_URL is set, so Vercel and Supabase stay
the live path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, ".")


def publish_issue(payload: dict, *, url: str, token: str, opener=None) -> int:
    """Authenticated POST of one issue document. Returns the HTTP status."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    open_url = opener or urllib.request.urlopen
    with open_url(request, timeout=30) as response:
        return int(response.status)


def maybe_publish_canonical(digest_date: str, *, digest_dir: Optional[Path] = None) -> str:
    """Publish when configured. Missing URL or token skips without an error."""
    url = os.getenv("CLOUDFLARE_PUBLISH_URL", "").strip()
    token = os.getenv("CLOUDFLARE_PUBLISH_TOKEN", "").strip()
    if not url or not token:
        return "skipped"
    directory = digest_dir or Path(os.getenv("DIGEST_MARKDOWN_DIR", "data/digests"))
    path = directory / f"{digest_date}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    status = publish_issue(payload, url=url, token=token)
    if status >= 400:
        raise SystemExit(f"Cloudflare publish failed with HTTP {status}")
    return "published"


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a canonical issue to the Cloudflare worker")
    parser.add_argument("--digest-date", required=True)
    args = parser.parse_args()
    print(maybe_publish_canonical(args.digest_date))


if __name__ == "__main__":
    main()

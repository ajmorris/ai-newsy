"""Render the digest email locally and drop a copy in Mailpit when it is running.

The default input is a fixture that includes every story and quick-hit variant.
Pass --date to render a real digest with the same payload builder the send uses.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from execution.email_renderer_payload import (  # noqa: E402
    build_email_renderer_payload,
    quick_hit_sections_from_digest,
)

DEFAULT_FIXTURE = REPO_ROOT / "execution" / "fixtures" / "email_preview_payload.json"
DEFAULT_OUTPUT = REPO_ROOT / "emails" / "preview" / "index.html"
DEFAULT_DIGEST_DIR = REPO_ROOT / "data" / "digests"
RENDERER_SCRIPT = REPO_ROOT / "emails" / "render_email.mjs"
DEFAULT_MAILPIT_URL = "http://127.0.0.1:8025"
PREVIEW_TOKEN = "preview"


def payload_from_digest(digest: Dict[str, object], digest_date: str) -> Dict[str, object]:
    """Build the renderer payload the daily send would build for this digest."""
    return build_email_renderer_payload(
        sections=list(digest.get("sections") or []),
        intro=str(digest.get("intro") or ""),
        subject=str(digest.get("subject_line") or ""),
        unsubscribe_token=PREVIEW_TOKEN,
        digest_date=digest_date,
        tweet_headlines=list(digest.get("tweet_headlines") or []),
        community_headlines=list(digest.get("community_headlines") or []),
        quick_hit_sections=quick_hit_sections_from_digest(digest),
    )


def render_html(payload: Dict[str, object]) -> str:
    """Run the MJML renderer and return the HTML document."""
    if not RENDERER_SCRIPT.exists():
        raise SystemExit(f"Missing renderer: {RENDERER_SCRIPT}")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle)
        payload_path = handle.name

    try:
        result = subprocess.run(
            ["node", str(RENDERER_SCRIPT), payload_path],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        Path(payload_path).unlink(missing_ok=True)

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "renderer failed").strip()
        raise SystemExit(detail)
    return result.stdout


def mailpit_is_up(base_url: str) -> bool:
    """Return True when the Mailpit web UI answers."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/", timeout=1) as response:
            return 200 <= getattr(response, "status", 200) < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def post_to_mailpit(base_url: str, subject: str, html: str) -> None:
    """Inject one HTML message through Mailpit's send API."""
    body = json.dumps(
        {
            "From": {"Email": "digest@localhost", "Name": "AI News Daily"},
            "To": [{"Email": "preview@localhost", "Name": "Local preview"}],
            "Subject": subject or "AI News Daily preview",
            "HTML": html,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/v1/send",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if getattr(response, "status", 200) >= 300:
                raise SystemExit(f"Mailpit rejected the preview message ({response.status}).")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise SystemExit(f"Mailpit rejected the preview message ({exc.code}): {detail}") from exc


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected a JSON object in {path}")
    return payload


def resolve_payload(date: str, payload_path: str, digest_dir: Path) -> Dict[str, object]:
    """Choose the showcase fixture, a renderer payload, or a digest date."""
    if date and payload_path:
        raise SystemExit("Pass either --date or --payload, not both.")
    if payload_path:
        return _load_json(Path(payload_path))
    if date:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise SystemExit("--date must be YYYY-MM-DD")
        digest_path = digest_dir / f"{date}.json"
        digest = _load_json(digest_path)
        digest_date = str(digest.get("digest_date") or date)
        return payload_from_digest(digest, digest_date)
    return _load_json(DEFAULT_FIXTURE)


def write_preview(html: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def _mailpit_help(base_url: str) -> str:
    return (
        f"Mailpit is not running at {base_url}.\n"
        "Start it with:\n"
        "  docker compose -f emails/docker-compose.mailpit.yml up -d\n"
        "A single binary is listed at https://mailpit.axllent.org/docs/install/\n"
        "Rerun this command after Mailpit is up to inject the message."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the daily email for a local preview.")
    parser.add_argument(
        "--date",
        default="",
        help="Digest date (YYYY-MM-DD) under data/digests. Default is the full variant fixture.",
    )
    parser.add_argument(
        "--payload",
        default="",
        help="Path to a renderer payload JSON file. Skips the digest builder.",
    )
    parser.add_argument(
        "--digest-dir",
        default=str(DEFAULT_DIGEST_DIR),
        help="Directory of digest JSON files used with --date.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Where to write the HTML file.",
    )
    parser.add_argument(
        "--mailpit-url",
        default=DEFAULT_MAILPIT_URL,
        help="Mailpit base URL. The message is posted when this URL answers.",
    )
    args = parser.parse_args(argv)

    payload = resolve_payload(args.date, args.payload, Path(args.digest_dir))
    html = render_html(payload)
    output_path = Path(args.output)
    write_preview(html, output_path)

    subject = str(payload.get("subject") or "AI News Daily preview")
    print(f"Wrote {output_path}")
    print("Open that file in a browser.")

    if mailpit_is_up(args.mailpit_url):
        post_to_mailpit(args.mailpit_url, subject, html)
        print(f"Mailpit inbox: {args.mailpit_url.rstrip('/')}")
    else:
        print(_mailpit_help(args.mailpit_url.rstrip("/")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

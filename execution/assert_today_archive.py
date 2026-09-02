"""Require today's UTC digest JSON and Vercel archive files before push."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _load_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _staged_names() -> List[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z"],
        check=True,
        capture_output=True,
    )
    if not result.stdout:
        return []
    return [name.decode("utf-8") for name in result.stdout.split(b"\0") if name]


def _tracked_in_git(path: Path) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path.as_posix()],
        capture_output=True,
    )
    return result.returncode == 0


def _canonical_ready(payload: Dict[str, object], digest_date: str, path: Path) -> None:
    intro = str(payload.get("intro") or "").strip()
    if not intro:
        raise SystemExit(f"Canonical digest {path} is missing intro.")
    stories = payload.get("stories") or []
    if not isinstance(stories, list):
        raise SystemExit(f"Canonical digest {path} has invalid stories.")
    missing = [
        story.get("id", story.get("title", "unknown"))
        for story in stories
        if isinstance(story, dict) and not str(story.get("opinion") or "").strip()
    ]
    if missing:
        raise SystemExit(f"Canonical digest {digest_date} is missing opinions for: {missing!r}")


def assert_today_archive_ready(
    digest_dir: Path = Path("data/digests"),
    issues_dir: Path = Path("frontend/issues"),
    digest_date: Optional[str] = None,
    require_staged: bool = False,
    staged_names: Optional[Iterable[str]] = None,
) -> Dict[str, str]:
    digest_date = digest_date or utc_today()
    digest_path = digest_dir / f"{digest_date}.json"
    manifest_path = issues_dir / "index.json"

    if not digest_path.exists():
        raise SystemExit(
            f"Missing canonical digest {digest_path}. Assemble before commit/push."
        )
    payload = _load_json(digest_path)
    payload_date = str(payload.get("digest_date") or digest_date)
    if payload_date != digest_date:
        raise SystemExit(
            f"Canonical digest date {payload_date!r} does not match UTC today {digest_date}."
        )
    _canonical_ready(payload, digest_date, digest_path)

    if not manifest_path.exists():
        raise SystemExit(
            f"Missing {manifest_path}. Assemble must build frontend/issues before push."
        )
    manifest = _load_json(manifest_path)
    latest = manifest.get("latestIssue") or {}
    if not isinstance(latest, dict):
        raise SystemExit(f"{manifest_path} latestIssue is missing or invalid.")
    latest_date = str(latest.get("digestDate") or "")
    if latest_date != digest_date:
        raise SystemExit(
            f"{manifest_path} latestIssue.digestDate is {latest_date!r}, expected UTC today {digest_date}. "
            "A JSON-only push would leave the live site behind the email."
        )

    slug = str(latest.get("slug") or digest_date).strip() or digest_date
    html_path = issues_dir / f"{slug}.html"
    if not html_path.exists():
        fallback = issues_dir / f"{digest_date}.html"
        if fallback.exists():
            html_path = fallback
        else:
            raise SystemExit(
                f"Missing issue HTML {html_path}. Assemble must write today's archive page."
            )

    if require_staged:
        names = list(staged_names) if staged_names is not None else _staged_names()
        if names:
            required = {
                "canonical": digest_path.as_posix(),
                "manifest": manifest_path.as_posix(),
                "html": html_path.as_posix(),
            }
            missing = [
                label
                for label, rel in required.items()
                if rel not in names and not _tracked_in_git(Path(rel))
            ]
            digest_changing = required["canonical"] in names
            archive_changing = required["manifest"] in names or required["html"] in names
            if digest_changing and not archive_changing:
                raise SystemExit(
                    "Refuse to commit today's digest JSON without frontend/issues/ "
                    "(index.json and today's HTML). Vercel would lag the 09:00 UTC send."
                )
            if missing:
                raise SystemExit(
                    "Commit is missing staged archive files: "
                    + ", ".join(missing)
                    + ". git add data/digests/*.json frontend/issues before push."
                )

    print(
        f"Archive ready for {digest_date}: {digest_path} + {html_path} "
        f"(latestIssue.digestDate={latest_date})."
    )
    return {
        "digest_date": digest_date,
        "digest_path": digest_path.as_posix(),
        "manifest_path": manifest_path.as_posix(),
        "html_path": html_path.as_posix(),
        "slug": slug,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fail unless today's UTC digest JSON and frontend/issues archive are ready."
    )
    parser.add_argument("--digest-date", default="")
    parser.add_argument("--digest-dir", default="data/digests")
    parser.add_argument("--issues-dir", default="frontend/issues")
    parser.add_argument(
        "--require-staged",
        action="store_true",
        help="When the index has staged changes, require today's JSON + archive paths.",
    )
    args = parser.parse_args()
    assert_today_archive_ready(
        digest_dir=Path(args.digest_dir),
        issues_dir=Path(args.issues_dir),
        digest_date=args.digest_date or None,
        require_staged=args.require_staged,
    )


if __name__ == "__main__":
    main()

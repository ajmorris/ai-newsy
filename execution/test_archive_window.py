"""Public archive index keeps the last 30 days and drops issue-number labels."""

from __future__ import annotations

import unittest
from datetime import date

from execution.build_web_archive import (
    DigestIssue,
    archive_headline,
    issue_date_label,
    listing_cutoff_date,
    select_issues_for_public_index,
)


def _issue(digest_date: str, intro: str = "", subject: str = "") -> DigestIssue:
    return DigestIssue(
        digest_date=digest_date,
        subject=subject,
        intro=intro,
        article_count=3,
        body_html="",
        slug=digest_date,
        source_file="",
    )


class ArchiveWindowTests(unittest.TestCase):
    def test_cutoff_is_thirty_days_before_today(self) -> None:
        self.assertEqual(listing_cutoff_date(date(2026, 10, 30)), date(2026, 9, 30))

    def test_window_includes_cutoff_and_excludes_the_day_before(self) -> None:
        issues = [
            _issue("2026-10-30"),
            _issue("2026-09-30"),
            _issue("2026-09-29"),
        ]
        visible = select_issues_for_public_index(issues, today=date(2026, 10, 30))
        self.assertEqual(
            [issue.digest_date for issue in visible],
            ["2026-10-30", "2026-09-30"],
        )

    def test_headline_uses_a_short_subject(self) -> None:
        issue = _issue(
            "2026-10-30",
            intro="Amazon is spending big.",
            subject="ISSUE 61030 · 13 STORIES · 11 MIN READ",
        )
        self.assertEqual(archive_headline(issue), "Amazon spending big")

    def test_headline_matches_the_homepage_subject(self) -> None:
        issue = _issue(
            "2026-10-30",
            intro=(
                "Big Tech is reshaping itself around AI at a staggering pace — "
                "Amazon is pouring $220 billion into infrastructure"
            ),
        )
        self.assertEqual(archive_headline(issue), "Big Tech reshaping itself")
        self.assertEqual(issue_date_label(issue), "Issue 10/30/2026:")

    def test_headline_skips_issue_number_subjects(self) -> None:
        issue = _issue(
            "2026-10-30",
            subject="ISSUE 61030 · 13 STORIES · 11 MIN READ",
        )
        self.assertEqual(archive_headline(issue), "Daily briefing")
        self.assertEqual(issue_date_label(_issue("2026-10-06")), "Issue 10/6/2026:")


if __name__ == "__main__":
    unittest.main()

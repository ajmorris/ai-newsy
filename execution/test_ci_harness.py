"""Isolation, feed fixtures, send fakes, and render snapshots for the CI harness."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class UrlDedupTests(unittest.TestCase):
    def test_strips_tracking_and_www(self) -> None:
        from execution.url_dedup import canonical_url, dedupe_by_canonical_url

        left = canonical_url("https://www.Example.com/a/?utm_source=rss")
        right = canonical_url("https://example.com/a")
        self.assertEqual(left, right)
        self.assertEqual(canonical_url("https://x.com/post/1"), canonical_url("https://twitter.com/post/1"))

        articles = [
            {"url": "https://www.Example.com/a/?utm_source=rss", "title": "First"},
            {"url": "https://example.com/a", "title": "Duplicate"},
            {"url": "https://example.com/b", "title": "Other"},
        ]
        kept = dedupe_by_canonical_url(articles)
        self.assertEqual([item["title"] for item in kept], ["First", "Other"])

    def test_blank_url_is_kept(self) -> None:
        from execution.url_dedup import canonical_url, dedupe_by_canonical_url

        self.assertEqual(canonical_url(""), "")
        self.assertEqual(len(dedupe_by_canonical_url([{"url": "", "title": "No link"}])), 1)


class FeedIngestTests(unittest.TestCase):
    def test_ok_feed_collapses_duplicate_links(self) -> None:
        from execution.feed_ingest import articles_from_parsed_feed, parse_feed_bytes

        parsed = parse_feed_bytes((FIXTURES / "feeds" / "ok.xml").read_bytes())
        articles = articles_from_parsed_feed(parsed, source="Example", name="OK", limit=10)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]["title"], "Alpha launch")
        self.assertEqual(articles[1]["title"], "Beta notes")

    def test_malformed_feed_is_skipped(self) -> None:
        from execution.feed_ingest import FeedSkipped, articles_from_parsed_feed, parse_feed_bytes

        parsed = parse_feed_bytes((FIXTURES / "feeds" / "malformed.xml").read_bytes())
        with self.assertRaises(FeedSkipped):
            articles_from_parsed_feed(parsed, source="Bad", name="Broken", limit=10)

    def test_empty_feed_returns_no_articles(self) -> None:
        from execution.feed_ingest import articles_from_parsed_feed, parse_feed_bytes

        parsed = parse_feed_bytes((FIXTURES / "feeds" / "empty.xml").read_bytes())
        articles = articles_from_parsed_feed(parsed, source="Empty", name="Empty", limit=10)
        self.assertEqual(articles, [])

    def test_timeout_is_skipped_and_other_feeds_continue(self) -> None:
        from execution.feed_ingest import gather_feed_articles

        def load(feed):
            if feed["name"] == "slow":
                raise TimeoutError("timed out")
            return [{"url": "https://example.com/kept", "title": "Kept", "source": "Good"}]

        warnings = []
        result = gather_feed_articles(
            [{"name": "slow"}, {"name": "good"}],
            load,
            log=warnings.append,
        )
        self.assertEqual([item["title"] for item in result.articles], ["Kept"])
        self.assertEqual(len(result.skipped), 1)
        self.assertIn("slow", warnings[0])


class MailerTests(unittest.TestCase):
    def test_recording_sender_never_calls_resend(self) -> None:
        from execution.mailer import EmailMessage, FrozenClock, RecordingSender, SystemClock

        sender = RecordingSender(fail_addresses=["bad@example.com"])
        ok = EmailMessage(to="reader@example.com", subject="Issue", html="<p>Hi</p>", from_addr="news@example.com")
        bad = EmailMessage(to="bad@example.com", subject="Issue", html="<p>Hi</p>", from_addr="news@example.com")
        self.assertTrue(sender.send(ok))
        self.assertFalse(sender.send(bad))
        self.assertEqual(len(sender.sent), 1)
        moment = datetime(2026, 1, 15, tzinfo=timezone.utc)
        self.assertEqual(FrozenClock(moment).now(), moment)
        self.assertIsNotNone(SystemClock().now().tzinfo)

    def test_resend_sender_delegates_to_sdk(self) -> None:
        import resend
        from execution.mailer import EmailMessage, ResendSender

        message = EmailMessage(
            to="reader@example.com",
            subject="Issue",
            html="<p>Hi</p>",
            from_addr="news@example.com",
        )
        with patch.object(resend.Emails, "send", return_value={"id": "1"}) as send:
            self.assertTrue(ResendSender(api_key="key", from_addr="news@example.com").send(message))
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0]["to"], ["reader@example.com"])


class LlmFixtureTests(unittest.TestCase):
    def test_recorded_response_skips_providers(self) -> None:
        from execution.ai_client import generate_text_with_fallback

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "llm.json"
            path.write_text(
                json.dumps({"cases": [{"contains": "cluster these", "response": "same event"}]}),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"LLM_FIXTURE_PATH": str(path)}):
                text = generate_text_with_fallback(prompt="Please cluster these articles")
        self.assertEqual(text, "same event")

    def test_missing_fixture_match_raises(self) -> None:
        from execution.llm_fixtures import fixture_response_for_prompt

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "llm.json"
            path.write_text(json.dumps({"cases": [{"contains": "nope", "response": "x"}]}), encoding="utf-8")
            with patch.dict(os.environ, {"LLM_FIXTURE_PATH": str(path)}):
                with self.assertRaises(RuntimeError):
                    fixture_response_for_prompt("unrelated prompt")

    def test_default_fixture_and_unset_path(self) -> None:
        from execution.llm_fixtures import fixture_response_for_prompt

        with patch.dict(os.environ, {"LLM_FIXTURE_PATH": ""}):
            self.assertIsNone(fixture_response_for_prompt("anything"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "llm.json"
            path.write_text(
                json.dumps({"default": "fallback", "cases": ["skip-me"]}),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"LLM_FIXTURE_PATH": str(path)}):
                self.assertEqual(fixture_response_for_prompt("no case match"), "fallback")


class DesignTokenTests(unittest.TestCase):
    def test_archive_css_uses_shared_dark_tokens(self) -> None:
        from execution.design_tokens import archive_root_css, load_design_tokens

        tokens = load_design_tokens()
        css = archive_root_css()
        self.assertIn(tokens["dark"]["bg"], css)
        self.assertIn(tokens["dark"]["accent"], css)
        self.assertIn("--brand:", css)


class HeartbeatTests(unittest.TestCase):
    def test_missing_snapshot_alerts(self) -> None:
        from execution.check_digest_heartbeat import check_heartbeat, digest_date_for_heartbeat

        now = datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)
        self.assertEqual(digest_date_for_heartbeat(now), "2026-01-15")
        with tempfile.TemporaryDirectory() as tmp:
            message = check_heartbeat(Path(tmp), now)
        self.assertTrue(message.startswith("ALERT:"))

    def test_production_snapshot_passes(self) -> None:
        from execution.check_digest_heartbeat import check_heartbeat

        now = datetime(2026, 1, 15, 14, 30, tzinfo=ZoneInfo("America/New_York"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-01-15.sent.json"
            path.write_text(
                json.dumps(
                    {
                        "build_meta": {
                            "snapshot_meta": {
                                "send_mode": "production",
                                "send_completed_at": "2026-01-15T07:00:00+00:00",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            message = check_heartbeat(Path(tmp), now)
        self.assertTrue(message.startswith("OK:"))

    def test_cli_and_invalid_snapshot(self) -> None:
        from execution.check_digest_heartbeat import digest_date_for_heartbeat, main, production_snapshot_recorded

        self.assertEqual(
            digest_date_for_heartbeat(datetime(2026, 1, 15, 12, 0)),
            "2026-01-15",
        )
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_dir = Path(tmp)
            (snapshot_dir / "2026-01-15.sent.json").write_text("{", encoding="utf-8")
            self.assertFalse(production_snapshot_recorded(snapshot_dir, "2026-01-15"))
            (snapshot_dir / "2026-01-15.sent.json").write_text(
                json.dumps({"build_meta": {"snapshot_meta": []}}),
                encoding="utf-8",
            )
            self.assertFalse(production_snapshot_recorded(snapshot_dir, "2026-01-15"))
            self.assertEqual(main(["--snapshot-dir", tmp]), 1)


class DryRunSendTests(unittest.TestCase):
    def test_dry_run_does_not_claim_snapshot_or_require_resend(self) -> None:
        from execution.send_daily_email import send_daily_digest

        digest_date = "2026-01-15"
        payload = {
            "schema_version": "digest-json-v1",
            "digest_date": digest_date,
            "issue_id": "20260115",
            "subject_line": "ISSUE 60115 · 1 STORIES · 11 MIN READ",
            "intro": "Intro",
            "article_count": 1,
            "stories": [
                {
                    "id": 1,
                    "title": "Story",
                    "url": "https://example.com/story",
                    "source": "Example",
                    "summary": "Summary",
                    "opinion": "Why it matters.",
                    "topic": "Models",
                    "category": "Model Releases & Capabilities",
                }
            ],
            "sections": [],
            "tweet_headlines": [],
            "community_headlines": [],
            "content_hash": "abc",
            "build_meta": {"source": "canonical"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp) / "digests"
            snapshot_dir = Path(tmp) / "snapshots"
            digest_dir.mkdir()
            (digest_dir / f"{digest_date}.json").write_text(json.dumps(payload), encoding="utf-8")
            env = {
                "DIGEST_MARKDOWN_DIR": str(digest_dir),
                "DIGEST_SNAPSHOT_DIR": str(snapshot_dir),
                "RESEND_API_KEY": "",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("execution.send_daily_email.get_active_subscribers", return_value=[{"email": "a@b.c", "confirm_token": "t"}]) as subscribers:
                    with patch("execution.send_daily_email.try_claim_digest_send") as claim:
                        with patch("execution.send_daily_email.write_sent_snapshot") as snapshot:
                            with patch("execution.send_daily_email.mark_articles_sent") as mark:
                                with patch("execution.send_daily_email.complete_digest_send") as complete:
                                    result = send_daily_digest(dry_run=True, digest_date=digest_date)
            subscribers.assert_called_once()
            claim.assert_not_called()
            snapshot.assert_not_called()
            mark.assert_not_called()
            complete.assert_not_called()
            self.assertEqual(result["sent"], 1)
            self.assertFalse(snapshot_dir.exists())


class DatabaseImportTests(unittest.TestCase):
    def test_import_does_not_require_credentials(self) -> None:
        env = os.environ.copy()
        env.pop("SUPABASE_URL", None)
        env.pop("SUPABASE_SECRET_KEY", None)
        env.pop("SUPABASE_PUBLISHABLE_KEY", None)
        env["PYTHONPATH"] = str(REPO_ROOT)
        completed = subprocess.run(
            [sys.executable, "-c", "import execution.database; print('imported')"],
            cwd="/tmp",
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("imported", completed.stdout)


class WorkflowContractTests(unittest.TestCase):
    def test_ci_workflow_gates_pull_requests(self) -> None:
        text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", text)
        self.assertIn("unittest discover -s execution -p 'test_*.py'", text)
        self.assertIn("actionlint", text)

    def test_manual_sends_default_to_dry_run(self) -> None:
        test_digest = (REPO_ROOT / ".github" / "workflows" / "test_digest.yml").read_text(encoding="utf-8")
        parity = (REPO_ROOT / ".github" / "workflows" / "validate_digest_parity.yml").read_text(encoding="utf-8")
        self.assertIn("send_for_real:", test_digest)
        self.assertIn("--dry-run", test_digest)
        self.assertIn("send_for_real:", parity)
        self.assertIn("--dry-run", parity)


class RenderSnapshotTests(unittest.TestCase):
    def test_email_and_archive_snapshots(self) -> None:
        from execution.build_web_archive import _read_issue

        email_script = REPO_ROOT / "emails" / "render_email.mjs"
        payload_path = FIXTURES / "email_smoke_payload.json"
        email_golden = FIXTURES / "email_smoke.html"
        archive_golden = FIXTURES / "archive_smoke.html"
        node_modules = REPO_ROOT / "emails" / "node_modules"
        if not node_modules.exists():
            self.skipTest("emails/node_modules is not installed")

        rendered = subprocess.run(
            ["node", str(email_script), str(payload_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        email_html = rendered.stdout
        self.assertIn("Smoke story", email_html)
        if os.getenv("UPDATE_SNAPSHOTS") == "1" or not email_golden.exists():
            email_golden.write_text(email_html, encoding="utf-8")
        self.assertEqual(email_html, email_golden.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as tmp:
            issue_path = Path(tmp) / "2026-01-15.json"
            issue_path.write_text(
                json.dumps(
                    {
                        "digest_date": "2026-01-15",
                        "subject_line": "ISSUE 60115 · 1 STORIES · 11 MIN READ",
                        "issue_id": "20260115",
                        "intro": "Archive intro",
                        "article_count": 1,
                        "content_hash": "abc",
                        "sections": [
                            {
                                "name": "Other AI News",
                                "articles": [
                                    {
                                        "source": "Example",
                                        "title": "Smoke story",
                                        "url": "https://example.com/story",
                                        "summary": "One sentence summary.",
                                        "opinion": "Why it matters.",
                                    }
                                ],
                            }
                        ],
                        "tweet_headlines": [],
                        "community_headlines": [],
                    }
                ),
                encoding="utf-8",
            )
            from execution.build_web_archive import _render_issue_page

            issue = _read_issue(issue_path)
            self.assertIsNotNone(issue)
            page = _render_issue_page(issue)
        self.assertIn("Smoke story", page)
        self.assertIn("#0b0b0c", page)
        if os.getenv("UPDATE_SNAPSHOTS") == "1" or not archive_golden.exists():
            archive_golden.write_text(page, encoding="utf-8")
        self.assertEqual(page, archive_golden.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

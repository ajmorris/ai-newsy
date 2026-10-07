"""The Cloudflare worker stays beside the current stack and does not cut DNS."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "workers" / "digest" / "migrations" / "0001_init.sql"
CUTOVER = ROOT / "docs" / "CLOUDFLARE_CUTOVER.md"
WRANGLER = ROOT / "workers" / "digest" / "wrangler.toml"


class CloudflareContractTests(unittest.TestCase):
    def test_d1_migration_drops_postgres_types_and_rls(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertNotIn("bigserial", sql)
        self.assertNotIn("jsonb", sql)
        self.assertNotIn("timestamptz", sql)
        self.assertNotIn("row level security", sql)
        self.assertNotIn("create policy", sql)
        self.assertIn("payload text", sql)
        self.assertIn("analysis text", sql)
        self.assertIn("unique (issue_id, subscriber_id)", sql)
        self.assertIn("idempotency_key text not null unique", sql)

    def test_worker_defaults_keep_resend_and_leave_the_cron_off(self) -> None:
        text = WRANGLER.read_text(encoding="utf-8")
        self.assertIn('EMAIL_ADAPTER = "resend"', text)
        self.assertIn('SEND_CRON_ENABLED = "0"', text)

    def test_cutover_doc_does_not_flip_dns(self) -> None:
        text = CUTOVER.read_text(encoding="utf-8")
        self.assertIn("p=none", text)
        self.assertIn("two-week", text)
        self.assertIn("Resend", text)
        self.assertIn("do not change dns", text.lower())
        self.assertIn("seven", text.lower())

    def test_publish_is_skipped_without_a_url(self) -> None:
        from execution.publish_issue import maybe_publish_canonical

        with patch.dict("os.environ", {"CLOUDFLARE_PUBLISH_URL": "", "CLOUDFLARE_PUBLISH_TOKEN": ""}, clear=False):
            self.assertEqual(maybe_publish_canonical("2026-10-07"), "skipped")

    def test_publish_posts_the_issue_with_a_bearer_token(self) -> None:
        from execution.publish_issue import publish_issue

        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        opener = MagicMock(return_value=response)
        status = publish_issue(
            {"issue_id": "20261007", "digest_date": "2026-10-07"},
            url="https://worker.test/api/publish",
            token="publish-secret",
            opener=opener,
        )
        self.assertEqual(status, 200)
        request = opener.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer publish-secret")
        self.assertEqual(json.loads(request.data.decode("utf-8"))["issue_id"], "20261007")


if __name__ == "__main__":
    unittest.main()

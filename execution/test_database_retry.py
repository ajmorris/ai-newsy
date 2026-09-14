"""Tests for transient Supabase retries used by add_article."""

import unittest
from unittest.mock import patch

from execution.database import (
    _execute_with_retry,
    _is_duplicate_article_error,
    _is_transient_supabase_error,
)


class _FakeAPIError(Exception):
    def __init__(self, message: str, code=None) -> None:
        super().__init__(message)
        self.code = code


class TransientErrorTests(unittest.TestCase):
    def test_504_code_is_transient(self) -> None:
        self.assertTrue(_is_transient_supabase_error(_FakeAPIError("boom", code=504)))

    def test_gateway_timeout_body_is_transient(self) -> None:
        error = _FakeAPIError(
            "{'message': 'JSON could not be generated', 'code': 504, "
            "'details': 'b\\'{\"message\":\"Gateway Timeout\"}\\''}"
        )
        self.assertTrue(_is_transient_supabase_error(error))

    def test_unique_violation_is_not_transient(self) -> None:
        error = _FakeAPIError("duplicate key value violates unique constraint", code="23505")
        self.assertTrue(_is_duplicate_article_error(error))
        self.assertFalse(_is_transient_supabase_error(error))


class ExecuteWithRetryTests(unittest.TestCase):
    def test_retries_then_succeeds(self) -> None:
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise _FakeAPIError("Gateway Timeout", code=504)
            return "ok"

        with patch("execution.database.time.sleep") as sleep:
            self.assertEqual(_execute_with_retry(flaky), "ok")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(sleep.call_count, 2)

    def test_gives_up_after_attempts(self) -> None:
        def always_fail():
            raise _FakeAPIError("Gateway Timeout", code=504)

        with patch("execution.database.time.sleep"):
            with self.assertRaisesRegex(_FakeAPIError, "Gateway Timeout"):
                _execute_with_retry(always_fail, attempts=3)

    def test_does_not_retry_duplicate(self) -> None:
        calls = {"n": 0}

        def dup():
            calls["n"] += 1
            raise _FakeAPIError("duplicate key value violates unique constraint")

        with patch("execution.database.time.sleep") as sleep:
            with self.assertRaisesRegex(_FakeAPIError, "duplicate"):
                _execute_with_retry(dup)
        self.assertEqual(calls["n"], 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()

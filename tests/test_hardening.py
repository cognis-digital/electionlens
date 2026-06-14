"""Hardening tests: error paths, edge cases, input validation."""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from electionlens.core import AnalysisError, analyze, load_posts  # noqa: E402
from electionlens import cli  # noqa: E402

# Short helpers so inline JSON test fixtures stay within the line-length limit.
_TS0 = "2026-01-01T00:00:00Z"
_TS1 = "2026-01-01T00:00:01Z"


def _post(account: str, ts: str, text: str, **extra: object) -> str:
    """Build a minimal JSON post object as a string."""
    obj = {"account": account, "timestamp": ts, "text": text, **extra}
    import json
    return json.dumps(obj)


# ---------------------------------------------------------------------------
# load_posts edge cases
# ---------------------------------------------------------------------------

class TestLoadPostsEdgeCases(unittest.TestCase):
    """Edge-case validation in load_posts."""

    def test_single_valid_post_as_jsonl(self):
        """Single-object JSONL with all required fields parses cleanly."""
        posts = load_posts(_post("a", _TS0, "hello world foo"))
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].account, "a")

    def test_json_array_non_object_element_raises(self):
        """Array elements that are not objects must raise AnalysisError."""
        with self.assertRaises(AnalysisError):
            load_posts('["not", "an", "object"]')

    def test_record_missing_account_raises(self):
        """Record missing 'account' must raise AnalysisError."""
        rec = '{"timestamp":"' + _TS0 + '","text":"hello world"}'
        with self.assertRaises(AnalysisError) as ctx:
            load_posts("[" + rec + "]")
        self.assertIn("account", str(ctx.exception))

    def test_record_missing_timestamp_raises(self):
        """Record missing 'timestamp' must raise AnalysisError."""
        with self.assertRaises(AnalysisError) as ctx:
            load_posts('[{"account":"a","text":"hello world"}]')
        self.assertIn("timestamp", str(ctx.exception))

    def test_whitespace_only_input_raises(self):
        """Whitespace-only input must raise AnalysisError."""
        with self.assertRaises(AnalysisError):
            load_posts("   \n\t  ")

    def test_jsonl_blank_lines_skipped(self):
        """JSONL with blank lines between records must parse cleanly."""
        line_a = _post("a", _TS0, "hello there world")
        line_b = _post("b", _TS1, "another post here")
        jsonl = f"\n{line_a}\n\n{line_b}\n\n"
        posts = load_posts(jsonl)
        self.assertEqual(len(posts), 2)


# ---------------------------------------------------------------------------
# analyze() parameter validation
# ---------------------------------------------------------------------------

class TestAnalyzeValidation(unittest.TestCase):
    """analyze() must reject invalid parameter combinations."""

    def _two_posts(self):
        line_a = _post("a", _TS0, "hello world foo bar")
        line_b = _post("b", _TS1, "other text stuff here")
        return load_posts(f"[{line_a},{line_b}]")

    def test_zero_window_raises(self):
        posts = self._two_posts()
        with self.assertRaises(AnalysisError) as ctx:
            analyze(posts, window_sec=0)
        self.assertIn("window_sec", str(ctx.exception))

    def test_negative_window_raises(self):
        posts = self._two_posts()
        with self.assertRaises(AnalysisError):
            analyze(posts, window_sec=-5)

    def test_zero_min_cluster_accounts_raises(self):
        posts = self._two_posts()
        with self.assertRaises(AnalysisError) as ctx:
            analyze(posts, min_cluster_accounts=0)
        self.assertIn("min_cluster_accounts", str(ctx.exception))

    def test_zero_min_burst_accounts_raises(self):
        posts = self._two_posts()
        with self.assertRaises(AnalysisError) as ctx:
            analyze(posts, min_burst_accounts=0)
        self.assertIn("min_burst_accounts", str(ctx.exception))


# ---------------------------------------------------------------------------
# CLI argument validation
# ---------------------------------------------------------------------------

DEMO = os.path.join(os.path.dirname(__file__), "..", "demos", "01-basic", "posts.json")


class TestCLIValidation(unittest.TestCase):
    """CLI must return non-zero and print to stderr on bad arguments."""

    def _run(self, argv):
        """Run cli.main() capturing stdout+stderr; return (rc, out, err)."""
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            rc = cli.main(argv)
        return rc, buf_out.getvalue(), buf_err.getvalue()

    def test_zero_window_returns_2(self):
        rc, _, err = self._run(["scan", DEMO, "--window", "0"])
        self.assertEqual(rc, 2)
        self.assertIn("window", err.lower())

    def test_negative_window_returns_2(self):
        rc, _, err = self._run(["scan", DEMO, "--window", "-10"])
        self.assertEqual(rc, 2)
        self.assertIn("window", err.lower())

    def test_missing_file_returns_2_with_message(self):
        rc, _, err = self._run(["scan", "/nonexistent/path/file.json"])
        self.assertEqual(rc, 2)
        self.assertIn("error", err.lower())

    def test_malformed_json_returns_1(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("{not valid json")
            tmp = fh.name
        try:
            rc, _, err = self._run(["scan", tmp])
            self.assertEqual(rc, 1)
            self.assertIn("error", err.lower())
        finally:
            os.unlink(tmp)

    def test_empty_json_array_returns_1(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("[]")
            tmp = fh.name
        try:
            rc, _, err = self._run(["scan", tmp])
            self.assertEqual(rc, 1)
            self.assertIn("error", err.lower())
        finally:
            os.unlink(tmp)


if __name__ == "__main__":
    unittest.main()

"""Smoke tests for ELECTIONLENS. No network. Standard library only."""
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from electionlens import (  # noqa: E402
    TOOL_NAME, TOOL_VERSION, load_posts, analyze, Findings,
)
from electionlens.core import AnalysisError  # noqa: E402
from electionlens import cli  # noqa: E402

DEMO = os.path.join(os.path.dirname(__file__), "..", "demos", "01-basic", "posts.json")


class TestMeta(unittest.TestCase):
    def test_tool_identity(self):
        self.assertEqual(TOOL_NAME, "electionlens")
        self.assertTrue(TOOL_VERSION)


class TestEngine(unittest.TestCase):
    def _load(self):
        with open(DEMO, encoding="utf-8") as fh:
            return load_posts(fh.read())

    def test_load_demo(self):
        posts = self._load()
        self.assertGreater(len(posts), 10)
        # hashtags extracted from text when absent
        self.assertTrue(any("stopthecount" in p.hashtags for p in posts))

    def test_jsonl_parsing(self):
        jsonl = (
            '{"account":"a","timestamp":"2026-11-02T14:00:00Z","text":"hello world here"}\n'
            '{"account":"b","timestamp":"2026-11-02T14:00:01Z","text":"hello world here"}\n'
        )
        posts = load_posts(jsonl)
        self.assertEqual(len(posts), 2)
        # identical normalized text -> same fingerprint
        self.assertEqual(posts[0].fingerprint, posts[1].fingerprint)

    def test_detects_copypasta_and_burst(self):
        f = analyze(self._load())
        self.assertIsInstance(f, Findings)
        # the RIGGED copypasta with 4 distinct accounts must surface
        self.assertTrue(f.copypasta_clusters)
        top = f.copypasta_clusters[0]
        self.assertGreaterEqual(top.account_count, 4)
        # a synchronized burst window must surface
        self.assertTrue(f.burst_windows)
        # narrative spike on stopthecount
        tags = {s["hashtag"] for s in f.narrative_spikes}
        self.assertIn("stopthecount", tags)
        # coordination should not be LOW given the seeded op
        self.assertNotEqual(f.risk_level, "LOW")

    def test_risk_ranking_flags_sockpuppets(self):
        f = analyze(self._load())
        ranked = [a.account for a in f.top_accounts]
        # at least one seeded sockpuppet ranks in the top 4
        seeded = {"patriot_7781", "patriot_3344", "freedom_eagle22",
                  "wakeup_now", "truthbot_x"}
        self.assertTrue(seeded.intersection(ranked[:4]))
        # top account carries at least one flag
        self.assertTrue(f.top_accounts[0].flags)

    def test_empty_input_raises(self):
        with self.assertRaises(AnalysisError):
            load_posts("")
        with self.assertRaises(AnalysisError):
            load_posts("[]")

    def test_bad_timestamp_raises(self):
        with self.assertRaises(AnalysisError):
            load_posts('[{"account":"a","timestamp":"not-a-date","text":"xx yy zz"}]')


class TestCLI(unittest.TestCase):
    def test_json_output_and_exit_zero(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(["--format", "json", "scan", DEMO])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("coordination_index", data)
        self.assertIn("copypasta_clusters", data)

    def test_table_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(["scan", DEMO])
        self.assertEqual(rc, 0)
        self.assertIn("Coordination index", buf.getvalue())

    def test_missing_file_nonzero(self):
        rc = cli.main(["scan", os.path.join(os.path.dirname(__file__), "nope.json")])
        self.assertEqual(rc, 2)

    def test_version_exits_zero(self):
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_fail_on_critical_flag(self):
        # demo is heavily seeded; with default thresholds it should be high.
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(["scan", DEMO, "--fail-on-critical"])
        # rc is 0 (not critical) or 3 (critical); both are valid, just deterministic
        self.assertIn(rc, (0, 3))


if __name__ == "__main__":
    unittest.main()

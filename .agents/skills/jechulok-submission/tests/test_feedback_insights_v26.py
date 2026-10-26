"""v2.6 private feedback insights: safety, sample and interpretation gates."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

import feedback_insights_v26 as insights
from feedback_v25 import record, save, SUFFIX


class InsightsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.old = self.root / "old"
        self.new = self.root / "new"
        self.old.mkdir()
        self.new.mkdir()
        self.document = self.root / "private-doc.pdf"
        self.document.write_bytes(b"intentionally unchanged")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def populate(directory, entries):
        for issue, count in entries.items():
            for _ in range(count):
                save(record("files", issue, "minor"), directory)

    def test_fewer_than_twenty_suppresses_all_priorities(self):
        self.populate(self.old, {"approval_confusing": 19})
        result = insights.prioritize(self.old)
        self.assertEqual(result["status"], "insufficient_or_sparse_feedback")
        self.assertIsNone(result["priorities"])

    def test_sparse_issue_suppresses_whole_ranking_even_above_twenty(self):
        self.populate(self.old, {"approval_confusing": 20, "operation_too_slow": 1})
        self.assertIsNone(insights.prioritize(self.old)["priorities"])

    def test_prioritizes_safe_counts_only_and_excludes_positive_feedback(self):
        self.populate(self.old, {
            "approval_confusing": 15, "installation_trouble": 10, "worked_well": 5,
        })
        result = insights.prioritize(self.old)
        self.assertEqual(result["status"], "descriptive_priorities_only")
        self.assertEqual([x["issue"] for x in result["priorities"]],
                         ["approval_confusing", "installation_trouble"])
        self.assertEqual(result["priorities"][0]["share_percent"], 50.0)
        self.assertFalse(result["representative_sample"])
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertEqual(self.document.read_bytes(), b"intentionally unchanged")

    def test_no_inferred_severity_or_user_counts(self):
        self.populate(self.old, {"approval_confusing": 20})
        report = insights.prioritize(self.old)
        self.assertNotIn("severity", json.dumps(report))
        self.assertNotIn("unique_users", json.dumps(report))

    def test_compare_defaults_to_not_authorized(self):
        self.populate(self.old, {"approval_confusing": 30})
        self.populate(self.new, {"approval_confusing": 30})
        report = insights.compare(self.old, self.new)
        self.assertEqual(report["status"], "comparison_not_authorized")
        self.assertIsNone(report["differences"])

    def test_compare_rejects_same_folder(self):
        with self.assertRaises(ValueError):
            insights.compare(self.old, self.old, conditions_comparable=True)

    def test_compare_requires_thirty_in_both_cohorts(self):
        self.populate(self.old, {"approval_confusing": 30})
        self.populate(self.new, {"approval_confusing": 29})
        report = insights.compare(self.old, self.new, conditions_comparable=True)
        self.assertEqual(report["status"], "insufficient_or_sparse_cohorts")
        self.assertIsNone(report["differences"])

    def test_compare_suppresses_sparse_issue_in_either_cohort(self):
        self.populate(self.old, {"approval_confusing": 30})
        self.populate(self.new, {"approval_confusing": 29, "operation_too_slow": 1})
        report = insights.compare(self.old, self.new, conditions_comparable=True)
        self.assertIsNone(report["differences"])

    def test_comparison_is_descriptive_and_not_causal(self):
        self.populate(self.old, {"approval_confusing": 20, "worked_well": 10})
        self.populate(self.new, {"approval_confusing": 10, "worked_well": 20})
        report = insights.compare(self.old, self.new, conditions_comparable=True)
        self.assertEqual(report["status"], "descriptive_comparison_only")
        self.assertIsNone(report["quality_improved"])
        self.assertFalse(report["participant_independence_verified"])
        self.assertFalse(report["conditions_independently_verified"])
        issue = next(x for x in report["differences"] if x["issue"] == "approval_confusing")
        self.assertEqual(issue["direction"], "fewer_reports")
        self.assertEqual(issue["difference_percentage_points"], -33.3)
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertEqual(self.document.read_bytes(), b"intentionally unchanged")

    def test_rejects_corruption_and_oversized_record(self):
        entry = self.old / ("entry-invalid" + SUFFIX)
        entry.write_text('{"comment":"secret@example.com"}', encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            insights.read_entries(self.old)
        self.assertNotIn("secret", str(caught.exception))
        entry.write_bytes(b"a" * 2048)
        with self.assertRaises(ValueError):
            insights.read_entries(self.old)

    def test_symlinked_record_does_not_follow_target(self):
        target = self.root / "private-source.txt"
        target.write_text(json.dumps(record("files", "worked_well", "none")))
        link = self.old / ("entry-link" + SUFFIX)
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(ValueError):
            insights.read_entries(self.old)

    def test_invalid_directory_rejected(self):
        with self.assertRaises(ValueError):
            insights.prioritize(self.root / "missing")

    def test_cli_error_hides_file_paths(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = insights.main(["prioritize", "--directory", str(self.root / "missing")])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue())["status"], "error")
        self.assertNotIn(str(self.root), out.getvalue())

    def test_read_only_no_upload_even_when_network_api_is_unavailable(self):
        self.populate(self.old, {"approval_confusing": 20})
        with patch("feedback_insights_v26.os.open", wraps=insights.os.open):
            before = {x.name for x in self.old.iterdir()}
            report = insights.prioritize(self.old)
            after = {x.name for x in self.old.iterdir()}
        self.assertEqual(before, after)
        self.assertFalse(report["network_used"])
        self.assertFalse(report["upload_performed"])


if __name__ == "__main__":
    unittest.main()

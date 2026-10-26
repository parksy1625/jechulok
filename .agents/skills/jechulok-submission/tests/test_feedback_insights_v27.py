"""v2.7 opt-in consent, disclosure and read-only security regressions."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from feedback_v25 import record, save, summary, SUFFIX
import feedback_insights_v27 as insights


class FeedbackInsightsV27Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.old = self.root / "old"
        self.new = self.root / "new"
        self.old.mkdir()
        self.new.mkdir()
        self.sentinel = self.root / "private-notice.pdf"
        self.sentinel.write_bytes(b"must remain untouched")

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, directory, issue, amount):
        for _ in range(amount):
            save(record("plan", issue, "minor"), directory)

    def test_priority_minimum_twenty(self):
        self.add(self.old, "approval_confusing", 19)
        self.assertIsNone(insights.prioritize(self.old)["priorities"])
        self.add(self.old, "approval_confusing", 1)
        self.assertEqual(insights.prioritize(self.old)["status"], "descriptive_priorities_only")

    def test_priority_withholds_all_if_any_nonzero_issue_under_five(self):
        self.add(self.old, "approval_confusing", 20)
        self.add(self.old, "installation_trouble", 1)
        self.assertIsNone(insights.prioritize(self.old)["priorities"])

    def test_priority_uses_only_voluntary_frequency(self):
        self.add(self.old, "approval_confusing", 15)
        self.add(self.old, "installation_trouble", 10)
        self.add(self.old, "worked_well", 5)
        result = insights.prioritize(self.old)
        self.assertEqual([x["issue"] for x in result["priorities"]],
                         ["approval_confusing", "installation_trouble"])
        self.assertEqual(result["priorities"][0]["share_percent"], 50.0)
        self.assertFalse(result["population_prevalence_measured"])
        self.assertEqual(self.sentinel.read_bytes(), b"must remain untouched")

    def test_comparison_default_does_not_read_records(self):
        with patch("feedback_insights_v27.summary", side_effect=AssertionError("read without opt-in")):
            result = insights.compare(self.old, self.new)
        self.assertEqual(result["status"], "comparison_not_authorized")
        self.assertIsNone(result["differences"])

    def test_same_directory_rejected_even_without_flag(self):
        with self.assertRaises(ValueError):
            insights.compare(self.old, self.old)

    def test_both_cohorts_need_thirty(self):
        self.add(self.old, "approval_confusing", 30)
        self.add(self.new, "approval_confusing", 29)
        result = insights.compare(self.old, self.new, conditions_comparable=True)
        self.assertIsNone(result["differences"])

    def test_comparison_suppresses_small_cell(self):
        self.add(self.old, "approval_confusing", 30)
        self.add(self.new, "approval_confusing", 29)
        self.add(self.new, "installation_trouble", 1)
        result = insights.compare(self.old, self.new, conditions_comparable=True)
        self.assertIsNone(result["differences"])

    def test_explicit_comparison_cannot_claim_significance(self):
        self.add(self.old, "approval_confusing", 20)
        self.add(self.old, "worked_well", 10)
        self.add(self.new, "approval_confusing", 10)
        self.add(self.new, "worked_well", 20)
        result = insights.compare(self.old, self.new, conditions_comparable=True)
        self.assertEqual(result["status"], "descriptive_comparison_only")
        self.assertFalse(result["causal_improvement_proven"])
        self.assertFalse(result["statistical_significance_measured"])
        self.assertFalse(result["conditions_independently_verified"])
        category = next(x for x in result["differences"] if x["issue"] == "approval_confusing")
        self.assertEqual(category["delta_percentage_points"], -33.3)
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_summary_rejects_symlink_record(self):
        target = self.root / "file.txt"
        target.write_text(json.dumps(record("plan", "worked_well", "none")))
        link = self.old / ("entry-link" + SUFFIX)
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(ValueError):
            summary(self.old)

    def test_summary_rejects_nonregular_entry(self):
        directory = self.old / ("entry-directory" + SUFFIX)
        directory.mkdir()
        with self.assertRaises(ValueError):
            summary(self.old)

    def test_summary_rejects_oversized_feedback(self):
        file = self.old / ("entry-large" + SUFFIX)
        file.write_bytes(b"x" * 2048)
        with self.assertRaises(ValueError):
            summary(self.old)

    def test_cli_errors_do_not_echo_directory(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = insights.main(["prioritize", "--directory", str(self.root / "missing")])
        self.assertEqual(code, 1)
        self.assertNotIn(str(self.root), output.getvalue())

    def test_cli_comparison_requires_explicit_flag(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = insights.main(["compare", "--baseline-directory", str(self.old),
                                  "--current-directory", str(self.new)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "comparison_not_authorized")

    def test_results_are_read_only_and_no_upload(self):
        self.add(self.old, "approval_confusing", 20)
        before = {x.name: x.read_bytes() for x in self.old.iterdir()}
        result = insights.prioritize(self.old)
        self.assertEqual(before, {x.name: x.read_bytes() for x in self.old.iterdir()})
        self.assertFalse(result["network_used"])
        self.assertEqual(result["files_created"], 0)


if __name__ == "__main__":
    unittest.main()

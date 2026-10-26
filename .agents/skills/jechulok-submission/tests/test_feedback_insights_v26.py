"""v2.6 local product-decision guardrails and descriptive comparison tests."""
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
from feedback_v25 import record, save, SUFFIX
import feedback_insights_v26 as insights


class FeedbackInsightsV26Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.before = self.root / "before"
        self.after = self.root / "after"
        self.before.mkdir()
        self.after.mkdir()
        self.private = self.root / "confidential-original.pdf"
        self.private.write_bytes(b"synthetic private sentinel: never change")

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, folder: Path, issue: str, count: int, impact: str = "minor"):
        for _ in range(count):
            save(record("files", issue, impact), folder)

    def test_priority_sorted_by_frequency_not_severity(self):
        self.add(self.before, "file_selection_confusing", 6, "minor")
        self.add(self.before, "approval_confusing", 4, "blocked")
        report = insights.prioritize(self.before)
        self.assertEqual(report["status"], "ranked_for_local_review")
        self.assertEqual([r["issue"] for r in report["ranked_issues"]],
                         ["file_selection_confusing", "approval_confusing"])
        self.assertEqual(report["ranked_issues"][0]["responses"], 6)
        self.assertFalse(report["severity_attribution_per_issue_available"])
        self.assertFalse(report["shareable_without_review"])
        self.assertFalse(report["telemetry_collected"])
        self.assertFalse(report["claims_product_improvement"] if "claims_product_improvement" in report else False)
        self.assertEqual(self.private.read_bytes(), b"synthetic private sentinel: never change")

    def test_worked_well_excluded_from_fix_rank(self):
        self.add(self.before, "worked_well", 7, "none")
        self.add(self.before, "installation_trouble", 3, "blocked")
        result = insights.prioritize(self.before)
        self.assertEqual(result["non_issue_positive_count"], 7)
        self.assertEqual(len(result["ranked_issues"]), 1)
        self.assertEqual(result["ranked_issues"][0]["issue"], "installation_trouble")

    def test_small_total_prevents_ranking(self):
        self.add(self.before, "approval_confusing", 9)
        result = insights.prioritize(self.before)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["ranked_issues"])

    def test_small_cell_suppresses_all_issue_priorities(self):
        self.add(self.before, "approval_confusing", 9)
        self.add(self.before, "unclear_next_step", 1)
        result = insights.prioritize(self.before)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["ranked_issues"])
        self.assertNotIn("approval_confusing", json.dumps(result))

    def test_compare_reports_descriptive_delta_not_improvement(self):
        self.add(self.before, "file_selection_confusing", 7)
        self.add(self.before, "approval_confusing", 3)
        self.add(self.after, "file_selection_confusing", 3)
        self.add(self.after, "approval_confusing", 7)
        result = insights.compare(self.before, self.after)
        self.assertEqual(result["status"], "descriptive_only")
        self.assertFalse(result["claims_product_improvement"])
        self.assertFalse(result["version_cohort_membership_verified"])
        self.assertFalse(result["independent_participant_ids_verified"])
        self.assertIsNone(result["change_is_statistically_significant"])
        by_issue = {row["issue"]: row for row in result["issue_comparisons"]}
        self.assertEqual(by_issue["file_selection_confusing"]["sample_share_delta_pp"], -40)
        self.assertEqual(by_issue["approval_confusing"]["sample_share_delta_pp"], 40)
        self.assertFalse(result["shareable_without_review"])
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_compare_different_denominators_uses_sample_shares(self):
        self.add(self.before, "unclear_next_step", 10)
        self.add(self.after, "unclear_next_step", 10)
        self.add(self.after, "approval_confusing", 10)
        report = insights.compare(self.before, self.after)
        self.assertEqual(report["status"], "descriptive_only")
        issues = {x["issue"]: x for x in report["issue_comparisons"]}
        self.assertEqual(issues["unclear_next_step"]["sample_share_delta_pp"], -50)
        self.assertEqual(issues["unclear_next_step"]["baseline_sample_share"], 1.0)
        self.assertEqual(issues["unclear_next_step"]["current_sample_share"], 0.5)

    def test_comparison_requires_two_distinct_folders(self):
        self.add(self.before, "approval_confusing", 10)
        with self.assertRaises(ValueError):
            insights.compare(self.before, self.before)
        with self.assertRaises(ValueError):
            insights.compare(self.before, self.before / ".." / "before")

    def test_comparison_suppressed_if_either_cohort_too_small(self):
        self.add(self.before, "approval_confusing", 10)
        self.add(self.after, "approval_confusing", 9)
        out = insights.compare(self.before, self.after)
        self.assertEqual(out["status"], "insufficient_evidence")
        self.assertIsNone(out["issue_comparisons"])

    def test_comparison_suppressed_if_either_cohort_has_sparse_cells(self):
        self.add(self.before, "approval_confusing", 10)
        self.add(self.after, "approval_confusing", 9)
        self.add(self.after, "installation_trouble", 1)
        out = insights.compare(self.before, self.after)
        self.assertEqual(out["status"], "insufficient_evidence")
        self.assertIsNone(out["issue_comparisons"])
        self.assertNotIn("approval_confusing", json.dumps(out))

    def test_original_records_unchanged_and_no_result_files_created(self):
        self.add(self.before, "approval_confusing", 10)
        original_names = sorted(p.name for p in self.before.iterdir())
        before_bytes = {p.name: p.read_bytes() for p in self.before.iterdir()}
        insights.prioritize(self.before)
        self.assertEqual(original_names, sorted(p.name for p in self.before.iterdir()))
        self.assertEqual(before_bytes, {p.name: p.read_bytes() for p in self.before.iterdir()})
        self.assertEqual(self.private.read_bytes(), b"synthetic private sentinel: never change")

    def test_invalid_and_symlinked_feedback_still_rejected(self):
        self.add(self.before, "approval_confusing", 10)
        suspect = self.before / ("entry-bad" + SUFFIX)
        suspect.write_text('{"issue":"test@example.com"}')
        with self.assertRaises(ValueError):
            insights.prioritize(self.before)
        suspect.unlink()
        try:
            suspect.symlink_to(self.private)
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(ValueError):
            insights.prioritize(self.before)

    def test_cli_prioritize_has_sanitized_machine_readable_output(self):
        self.add(self.before, "approval_confusing", 10)
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            ret = insights.main(["prioritize", "--directory", str(self.before)])
        report = json.loads(stream.getvalue())
        self.assertEqual(ret, 0)
        self.assertEqual(report["status"], "ranked_for_local_review")
        self.assertFalse(report["network_used"])
        self.assertFalse(report["upload_performed"])
        self.assertNotIn(str(self.root), stream.getvalue())

    def test_cli_invalid_folder_does_not_echo_path(self):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            ret = insights.main(["prioritize", "--directory", str(self.root / "private_missing")])
        self.assertEqual(ret, 1)
        data = json.loads(stream.getvalue())
        self.assertEqual(data["status"], "error")
        self.assertNotIn(str(self.root), stream.getvalue())


if __name__ == "__main__":
    unittest.main()

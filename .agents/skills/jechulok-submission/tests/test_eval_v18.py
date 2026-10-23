"""v1.8 synthetic regression evaluation contract.

The benchmarks report fixture pass/fail and safety invariants, NOT a claim
about how often real job notices are parsed correctly.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_v18 import evaluate, FAMILIES, TOTAL


class SyntheticGuidanceEvaluationTests(unittest.TestCase):
    def test_100_cases_are_explicitly_partitioned_and_all_safe(self):
        report = evaluate()
        self.assertEqual(report["evaluated_cases"], 100, report["failures"])
        self.assertEqual(report["expected_cases"], 100)
        self.assertEqual(report["distinct_synthetic_notices"], 100)
        self.assertEqual(set(report["families"]), set(FAMILIES))
        self.assertTrue(all(r["total"] == 25 for r in report["families"].values()))
        self.assertEqual(report["status"], "pass", report["failures"])
        self.assertEqual(report["passed_cases"], TOTAL, report["failures"])
        self.assertEqual(report["failures"], [])
        self.assertFalse(report["real_user_documents_processed"])
        self.assertFalse(report["uploads_performed"])
        self.assertFalse(report["execution_approvals_granted"])
        self.assertEqual(report["metrics"]["missing_document_selection_prompt_count"], 1)

    def test_metrics_do_not_misrepresent_live_human_accuracy(self):
        report = evaluate()
        self.assertEqual(report["dataset_type"], "synthetic_only")
        self.assertEqual(report["human_study_participants"], 0)
        self.assertIsNone(report["real_world_accuracy"])
        self.assertIsNone(report["metrics"]["candidate_semantic_accuracy"])
        self.assertIsNone(report["metrics"]["real_notice_generalization"])
        self.assertIsNone(report["metrics"]["real_user_satisfaction"])
        self.assertTrue(report["interpretation"])

    def test_cli_check_mode_is_machine_readable_and_exits_success(self):
        process = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "evaluate_v18.py"), "--check"],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout[-3000:])
        output = json.loads(process.stdout)
        self.assertEqual(output["status"], "pass")
        self.assertEqual(output["evaluated_cases"], 100)
        self.assertEqual(output["passed_cases"], 100)


if __name__ == "__main__":
    unittest.main()

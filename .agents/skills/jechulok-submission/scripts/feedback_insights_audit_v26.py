#!/usr/bin/env python3
"""v2.6 20 synthetic feedback entries per cohort, no human participants."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

from feedback_v25 import record, save
from feedback_insights_v26 import prioritize, compare


def evaluate() -> dict:
    checks = []
    with tempfile.TemporaryDirectory(prefix="jechulok-v26-synthetic-") as work:
        root = Path(work)
        before, after = root / "baseline", root / "current"
        before.mkdir()
        after.mkdir()
        sentinel = root / "private-document-marker.txt"
        sentinel.write_bytes(b"synthetic document marker; must survive")
        for folder, counts in (
            (before, {"file_selection_confusing": 12, "approval_confusing": 8}),
            (after, {"file_selection_confusing": 7, "approval_confusing": 13}),
        ):
            for issue, n in counts.items():
                for _ in range(n):
                    save(record("files", issue, "minor"), folder)
        old = prioritize(before)
        new = prioritize(after)
        diff = compare(before, after)
        checks = [
            {"id": "baseline_priority", "passed": old["status"] == "ranked_for_local_review"},
            {"id": "current_priority", "passed": new["status"] == "ranked_for_local_review"},
            {"id": "cohort_descriptive_only", "passed": diff["status"] == "descriptive_only"},
            {"id": "two_cohort_sample_sizes", "passed": diff["baseline_records"] == 20 and diff["current_records"] == 20},
            {"id": "no_claimed_improvement", "passed": diff["claims_product_improvement"] is False},
            {"id": "no_significance_claim", "passed": diff["change_is_statistically_significant"] is None},
            {"id": "no_cohort_identity_claim", "passed": diff["version_cohort_membership_verified"] is False},
            {"id": "no_unique_participant_claim", "passed": diff["independent_participant_ids_verified"] is False},
            {"id": "explicit_local_only", "passed": not (old["network_used"] or new["network_used"] or diff["network_used"])},
            {"id": "no_telemetry", "passed": not (old["telemetry_collected"] or new["telemetry_collected"] or diff["telemetry_collected"])},
            {"id": "not_auto_shared", "passed": not (old["shareable_without_review"] or new["shareable_without_review"] or diff["shareable_without_review"])},
            {"id": "no_created_reports", "passed": old["files_created"] == new["files_created"] == diff["files_created"] == 0},
            {"id": "no_upload", "passed": not (old["upload_performed"] or new["upload_performed"] or diff["upload_performed"])},
            {"id": "frequency_rank_only", "passed": old["ranked_issues"][0]["issue"] == "file_selection_confusing"},
            {"id": "current_rank_differs", "passed": new["ranked_issues"][0]["issue"] == "approval_confusing"},
            {"id": "exact_delta_calculated", "passed": next(x for x in diff["issue_comparisons"] if x["issue"] == "file_selection_confusing")["sample_share_delta_pp"] == -25.0},
            {"id": "review_suggested", "passed": bool(old["ranked_issues"][0]["suggested_validation"])},
            {"id": "no_personal_document_change", "passed": sentinel.read_bytes() == b"synthetic document marker; must survive"},
            {"id": "not_an_empirical_study", "passed": old["real_user_representativeness"] == "unverified"},
            {"id": "privacy_rule_exposed", "passed": old["minimum_required"] >= 10},
        ]
    passed = sum(bool(r["passed"]) for r in checks)
    return {
        "suite": "jechulok_v26_feedback_decision_regression",
        "status": "pass" if len(checks) == passed == 20 else "fail",
        "scenario_count": len(checks), "passed_count": passed,
        "scenarios": checks,
        "synthetic_entries_per_cohort": 20,
        "human_testers": 0,
        "observed_user_satisfaction": None,
        "real_improvement_claimed": False,
        "actual_feedback_uploaded": False,
        "only_invented_data": True,
        "interpretation": "Synthetic correctness tests, not an experimental or observational usability study.",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 1 if args.check and report["status"] != "pass" else 0


if __name__ == "__main__":
    sys.exit(main())

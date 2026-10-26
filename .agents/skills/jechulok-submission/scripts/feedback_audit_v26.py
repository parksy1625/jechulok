#!/usr/bin/env python3
"""Synthetic-only v2.6 triage/comparison regression, NOT a user survey."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from feedback_v25 import record, save
from feedback_insights_v26 import prioritize, compare


def evaluate() -> dict:
    scenarios = []
    with tempfile.TemporaryDirectory(prefix="jechulok-v26-synthetic-") as tmp:
        root = Path(tmp).resolve()
        old, new = root / "baseline", root / "candidate"
        old.mkdir()
        new.mkdir()
        sentinel = root / "no-change.pdf"
        sentinel.write_bytes(b"synthetic private doc marker")

        for directory, approval, positive in ((old, 20, 10), (new, 10, 20)):
            for _ in range(approval):
                save(record("plan", "approval_confusing", "blocked"), directory)
            for _ in range(positive):
                save(record("plan", "worked_well", "none"), directory)

        first = prioritize(old)
        second = prioritize(new)
        scenarios.append({"id": "safe_baseline_rank", "passed": first["status"] == "descriptive_priorities_only"})
        scenarios.append({"id": "safe_candidate_rank", "passed": second["status"] == "descriptive_priorities_only"})
        no_consent = compare(old, new)
        scenarios.append({"id": "no_automatic_comparison", "passed": no_consent["differences"] is None})
        diff = compare(old, new, conditions_comparable=True)
        scenarios.append({"id": "comparison_is_descriptive", "passed": (
            diff["status"] == "descriptive_comparison_only"
            and diff["quality_improved"] is None
            and not diff["conditions_independently_verified"]
        )})
        scenarios.append({"id": "no_original_paths_or_documents", "passed": (
            str(root) not in json.dumps(diff)
            and sentinel.read_bytes() == b"synthetic private doc marker"
        )})
        scenarios.append({"id": "offline_and_read_only", "passed": (
            not diff["network_used"] and not first["saved"] and not diff["upload_performed"]
        )})

    passed = sum(bool(s["passed"]) for s in scenarios)
    return {
        "suite": "jechulok_v26_synthetic_feedback_insights",
        "status": "pass" if passed == len(scenarios) else "fail",
        "scenario_count": len(scenarios), "passed_cases": passed,
        "scenarios": scenarios,
        "synthetic_records_generated": 60,
        "human_testers": 0, "real_feedback_collected": False,
        "causal_improvement_measured": False,
        "network_used": False, "user_documents_read": False,
        "existing_user_files_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = evaluate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return int(args.check and result["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())

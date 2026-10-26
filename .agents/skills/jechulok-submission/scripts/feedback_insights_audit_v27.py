#!/usr/bin/env python3
"""Six synthetic privacy and comparison contract checks; zero human data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from feedback_v25 import record, save
from feedback_insights_v27 import compare, prioritize


def evaluate() -> dict:
    checks = []
    with tempfile.TemporaryDirectory(prefix="jechulok-v27-synthetic-") as tmp:
        root = Path(tmp).resolve()
        old, new = root / "baseline", root / "current"
        old.mkdir()
        new.mkdir()
        protected = root / "my-private-notice.pdf"
        protected.write_bytes(b"unchanged synthetic sentinel")
        for folder, confusing, positive in ((old, 20, 10), (new, 10, 20)):
            for _ in range(confusing):
                save(record("plan", "approval_confusing", "blocked"), folder)
            for _ in range(positive):
                save(record("plan", "worked_well", "none"), folder)
        ranked = prioritize(old)
        not_authorized = compare(old, new)
        diff = compare(old, new, conditions_comparable=True)
        checks = [
            {"id": "frequency_only_rank", "passed": ranked["status"] == "descriptive_priorities_only"},
            {"id": "opt_in_comparison", "passed": not_authorized["differences"] is None},
            {"id": "descriptive_delta", "passed": diff["status"] == "descriptive_comparison_only"},
            {"id": "no_verified_causality", "passed": not diff["causal_improvement_proven"] and not diff["conditions_independently_verified"]},
            {"id": "no_documents_changed", "passed": protected.read_bytes() == b"unchanged synthetic sentinel"},
            {"id": "offline_read_only", "passed": not ranked["network_used"] and not diff["upload_performed"] and diff["files_created"] == 0},
        ]
    passed = sum(bool(c["passed"]) for c in checks)
    return {
        "suite": "jechulok_v27_feedback_privacy_regression",
        "status": "pass" if passed == len(checks) else "fail",
        "scenario_count": len(checks), "passed_cases": passed,
        "scenarios": checks, "synthetic_entries_per_cohort": 30,
        "human_testers": 0, "actual_feedback_collected": False,
        "causal_improvement_measured": False, "network_used": False,
        "documents_read": False, "user_files_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = evaluate()
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return int(args.check and result["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())

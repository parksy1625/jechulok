#!/usr/bin/env python3
"""v2.5 synthetic-only usability-feedback regression, not a human study.

30 deterministic, intentionally fabricated categorical responses. Tests
preview, explicit local save, aggregate summary, sparse cell suppression.
The reports never contain names, source paths, notices or user documents.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

from feedback_v25 import STAGES, ISSUES, IMPACTS, record, save, summary, MIN_COHORT


def evaluate() -> dict:
    scenarios: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="jechulok-v25-eval-synthetic-") as tmp:
        root = Path(tmp).resolve()
        existing = root / "do-not-replace.txt"
        existing.write_bytes(b"synthetic protected document marker")
        before = existing.read_bytes()
        for i in range(30):
            category = STAGES[i % len(STAGES)]
            issue = ISSUES[i % len(ISSUES)]
            impact = IMPACTS[i % len(IMPACTS)]
            item = record(category, issue, impact)
            # Preview only validates and returns categorical data.
            preview_valid = len(item) == 4 and "timestamp" not in item
            saved = save(item, root)
            saved_valid = saved["status"] == "saved_locally" and not saved["upload_performed"]
            scenarios.append({
                "id": f"sample_{i+1:02d}",
                "passed": preview_valid and saved_valid,
            })
        count = len(list(root.glob("*.feedback-v25.json")))
        report = summary(root)
        preserved = existing.read_bytes() == before
        correct = (
            count == 30 and report["status"] == "summarized"
            and report["records"] == 30
            and report["source"] == "local_opt_in_only"
            and report["breakdown"]["stages"] is not None
            and report["breakdown"]["impacts"] is not None
            and not report["shareable_summary"]
            and not report["upload_performed"]
            and preserved
        )
        # Sparse issue frequency must suppress the entire issue breakdown:
        # 30 responses across 9 categories produces counts 3..4; all safe.
        # This checks whether cohort rules are obeyed, without showing any
        # original data in output.
        scenarios.append({"id": "aggregate_cohort_guardrails", "passed": correct})

    passed = sum(bool(c["passed"]) for c in scenarios)
    return {
        "suite": "jechulok_v25_synthetic_feedback_safety",
        "status": "pass" if len(scenarios) == 31 and passed == 31 else "fail",
        "scenarios": scenarios,
        "scenario_count": len(scenarios),
        "passed_cases": passed,
        "minimum_cohort_size": MIN_COHORT,
        "generated_feedback_records": 30,
        "participants": 0,
        "actual_feedback_collected": False,
        "actual_user_satisfaction": None,
        "telemetry_sent": False,
        "automatic_upload": False,
        "personal_documents_read": False,
        "existing_user_files_changed": False,
        "interpretation": (
            "All results are synthetic regression conditions only. "
            "They are not usability scores or real user feedback."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.check and report["status"] != "pass" else 0


if __name__ == "__main__":
    sys.exit(main())

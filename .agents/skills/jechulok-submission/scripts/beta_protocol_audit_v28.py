#!/usr/bin/env python3
"""Deterministic synthetic-only v2.8 beta protocol safety regression."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from beta_protocol_v28 import CHECKS, audit, compare_preflight, protocol, template


def evaluate() -> dict:
    tests = []
    with tempfile.TemporaryDirectory(prefix="jechulok-v28-synthetic-") as root_text:
        root = Path(root_text).resolve()
        old, new = root / "old.json", root / "new.json"
        sentinel = root / "confidential-source.pdf"
        sentinel.write_bytes(b"never change")
        tasks = protocol("ko")
        tests.append({"id": "fixed_five_tasks", "passed": len(tasks["tasks"]) == 5})
        tests.append({"id": "no_contact_or_consent_claim", "passed":
                      not tasks["participants_contacted"] and not tasks["consent_independently_verified"]})
        first = template("baseline")
        second = template("current")
        old.write_text(json.dumps(first))
        tests.append({"id": "default_hold", "passed": audit(old)["status"] == "hold_for_manual_review"})
        first.update({key: True for key in CHECKS})
        second.update({key: True for key in CHECKS})
        old.write_text(json.dumps(first))
        new.write_text(json.dumps(second))
        result = compare_preflight(old, new)
        tests.append({"id": "self_attested_only", "passed":
                      result["status"] == "self_attested_protocols_match"
                      and not result["participants_and_collection_comparable_verified"]})
        second["recruitment"] = "open_volunteers"
        new.write_text(json.dumps(second))
        tests.append({"id": "mismatch_hold", "passed":
                      compare_preflight(old, new)["status"] == "hold_for_manual_review"})
        tests.append({"id": "documents_unchanged", "passed": sentinel.read_bytes() == b"never change"})
    passed = sum(bool(test["passed"]) for test in tests)
    return {
        "suite": "jechulok_v28_beta_readiness_synthetic",
        "status": "pass" if passed == len(tests) else "fail",
        "scenario_count": len(tests), "passed_cases": passed,
        "scenarios": tests, "human_testers": 0,
        "real_consent_verified": False, "real_study_conducted": False,
        "telemetry_sent": False, "personal_documents_read": False,
        "user_files_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = evaluate()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return int(args.check and result["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())

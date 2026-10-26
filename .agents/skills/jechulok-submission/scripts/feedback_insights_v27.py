#!/usr/bin/env python3
"""v2.7 privacy-conservative offline insights for voluntary v2.5 feedback.

No files are modified and no network calls occur. Results are descriptive
among submitted categorical records only, never causal effectiveness.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from feedback_v25 import ISSUES, canonical_directory, summary
from feedback_insights_v26 import FIX_SUGGESTIONS, POSITIVE

MIN_PRIORITY = 20
MIN_COMPARISON = 30
MIN_CELL = 5


def _base() -> dict[str, Any]:
    return {
        "schema": "jechulok-feedback-insights-v27",
        "source": "user_selected_local_v25_feedback",
        "read_only": True,
        "network_used": False,
        "upload_performed": False,
        "files_created": 0,
        "shareable_without_review": False,
        "verified_independent_participants": False,
        "population_prevalence_measured": False,
    }


def _safe_counts(report: dict[str, Any], minimum: int) -> dict[str, int] | None:
    if report.get("status") != "summarized" or report.get("records", 0) < minimum:
        return None
    issue_counts = (report.get("breakdown") or {}).get("issues")
    if not isinstance(issue_counts, dict) or not issue_counts:
        return None
    if (any(type(k) is not str or k not in ISSUES
            or type(v) is not int or v < MIN_CELL for k, v in issue_counts.items())
            or sum(issue_counts.values()) != report["records"]):
        return None
    return issue_counts


def prioritize(directory: Path) -> dict[str, Any]:
    report = summary(directory)
    counts = _safe_counts(report, MIN_PRIORITY)
    base = {**_base(), "operation": "prioritize", "records": report["records"],
            "minimum_records": MIN_PRIORITY, "minimum_nonzero_issue_count": MIN_CELL}
    if counts is None:
        return {**base, "status": "insufficient_or_sparse_sample", "priorities": None}
    return {
        **base, "status": "descriptive_priorities_only",
        "priorities": [
            {"issue": issue, "responses": count,
             "share_percent": round(100 * count / report["records"], 1),
             "next_validation": FIX_SUGGESTIONS[issue]}
            for issue, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
            if issue != POSITIVE
        ],
        "interpretation": (
            "Ranking is only frequency among voluntary responses, not "
            "verified distinct users, impact severity, or population prevalence."
        ),
    }


def compare(baseline: Path, current: Path, *,
            conditions_comparable: bool = False) -> dict[str, Any]:
    old_directory = canonical_directory(baseline)
    new_directory = canonical_directory(current)
    if old_directory == new_directory:
        raise ValueError("Two distinct local directories are required")
    base = {**_base(), "operation": "compare",
            "minimum_records_per_cohort": MIN_COMPARISON,
            "minimum_nonzero_issue_count": MIN_CELL,
            "conditions_user_attested": bool(conditions_comparable),
            "conditions_independently_verified": False,
            "cohort_version_membership_verified": False,
            "causal_improvement_proven": False,
            "statistical_significance_measured": False}
    if not conditions_comparable:
        # Do not even read cohort entries without explicit operator intent.
        return {**base, "status": "comparison_not_authorized",
                "differences": None,
                "next_step": "Review recruitment, prompts and windows; opt in with --conditions-comparable."}
    old = summary(old_directory)
    new = summary(new_directory)
    a = _safe_counts(old, MIN_COMPARISON)
    b = _safe_counts(new, MIN_COMPARISON)
    result = {**base, "baseline_records": old["records"],
              "current_records": new["records"]}
    if a is None or b is None:
        return {**result, "status": "insufficient_or_sparse_cohorts", "differences": None}
    differences = []
    for issue in ISSUES:
        old_share = a.get(issue, 0) / old["records"]
        new_share = b.get(issue, 0) / new["records"]
        differences.append({
            "issue": issue,
            "baseline_share_percent": round(100 * old_share, 1),
            "current_share_percent": round(100 * new_share, 1),
            "delta_percentage_points": round(100 * (new_share - old_share), 1),
        })
    return {
        **result, "status": "descriptive_comparison_only",
        "differences": differences,
        "interpretation": (
            "User-partitioned folders and repeated respondents cannot be verified. "
            "Observed changes are not statistically established or causal "
            "product improvements; do not publish without separate review."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    rank = commands.add_parser("prioritize")
    rank.add_argument("--directory", type=Path, required=True)
    diff = commands.add_parser("compare")
    diff.add_argument("--baseline-directory", type=Path, required=True)
    diff.add_argument("--current-directory", type=Path, required=True)
    diff.add_argument("--conditions-comparable", action="store_true")
    args = parser.parse_args(argv)
    try:
        output = (prioritize(args.directory) if args.command == "prioritize"
                  else compare(args.baseline_directory, args.current_directory,
                               conditions_comparable=args.conditions_comparable))
    except (ValueError, OSError, UnicodeError, TypeError, RuntimeError):
        print(json.dumps({"status": "error", "reason_code": "invalid_local_feedback_or_folders",
                          "network_used": False, "upload_performed": False}))
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

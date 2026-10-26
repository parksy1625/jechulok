#!/usr/bin/env python3
"""JeChulOK v2.6: local aggregate prioritization and cautious cohort comparison.

Read-only. Uses *only* v2.5's privacy-suppressed local summary, never
examines notices, applicant files, sessions or individual feedback.
Ranking is frequency only, NEVER issue severity or population importance.
Version tags are user-provided descriptions, not verified provenance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from feedback_v25 import ISSUES, summary

MIN_PRIORITY = 10
MIN_COMPARISON = 10
POSITIVE = "worked_well"
FIX_SUGGESTIONS = {
    "unclear_next_step": "Simplify the next-action guidance and test it with invited users.",
    "unclear_technical_rule": "Clarify unsupported or ambiguous technical requirements before any conversion.",
    "file_selection_confusing": "Show the missing original files together; keep explicit source selection.",
    "approval_confusing": "Differentiate preview, exact-plan consent and actual execution.",
    "error_message_unhelpful": "Use concise failure codes with safe, separately approved recovery steps.",
    "operation_too_slow": "Profile synthetic offline cases without transmitting private files.",
    "installation_trouble": "Test first-install doctor, local probe and side-by-side rollback.",
    "other_usability_issue": "Arrange opt-in, private user interviews before assuming a specific cause.",
}


def _base() -> dict[str, Any]:
    return {
        "schema": "jechulok-feedback-insights-v26",
        "source": "local_opt_in_categorical_feedback",
        "read_only": True,
        "network_used": False,
        "telemetry_collected": False,
        "files_created": 0,
        "upload_performed": False,
        "shareable_without_review": False,
        "real_user_representativeness": "unverified",
        "caution": (
            "Voluntary entries are not verified distinct people or version-linked sessions. "
            "Counts may contain repeated submissions. No causality or population "
            "satisfaction can be inferred. Never publish raw or aggregate outputs "
            "without separate privacy review and permission."
        ),
    }


def _safe_issue_counts(report: dict[str, Any], minimum: int) -> dict[str, int] | None:
    if (report.get("status") != "summarized"
            or type(report.get("records")) is not int
            or report["records"] < minimum):
        return None
    breakdown = report.get("breakdown") or {}
    issues = breakdown.get("issues")
    if not isinstance(issues, dict):
        return None
    if (not issues
            or any(type(name) is not str or name not in ISSUES
                   or type(count) is not int or count < 3
                   for name, count in issues.items())
            or sum(issues.values()) != report["records"]):
        return None
    return issues


def prioritize(directory: Path) -> dict[str, Any]:
    aggregated = summary(directory)
    total = aggregated["records"]
    counts = _safe_issue_counts(aggregated, MIN_PRIORITY)
    base = {
        **_base(), "operation": "prioritize",
        "records": total, "minimum_required": MIN_PRIORITY,
        "rule": "Descending categorical issue frequency only; no per-issue severity estimate.",
        "ranked_issues": None,
        "non_issue_positive_count": None,
        "total_blocked_count": None,
    }
    if counts is None:
        return {
            **base, "status": "insufficient_evidence",
            "reason_code": "small_cohort_or_privacy_suppression",
        }
    impacts = (aggregated.get("breakdown") or {}).get("impacts")
    ranked = [
        {
            "issue": issue,
            "responses": count,
            "sample_share": round(count / total, 4),
            "suggested_validation": FIX_SUGGESTIONS[issue],
        }
        for issue, count in counts.items() if issue != POSITIVE
    ]
    ranked.sort(key=lambda x: (-x["responses"], x["issue"]))
    return {
        **base, "status": "ranked_for_local_review",
        "reason_code": None,
        "ranked_issues": ranked,
        "non_issue_positive_count": counts.get(POSITIVE, 0),
        "total_blocked_count":
            impacts.get("blocked", 0) if isinstance(impacts, dict) else None,
        "severity_attribution_per_issue_available": False,
        "recommendation": "Use ranks as hypotheses for separate human usability validation, not automated feature deployment.",
    }


def compare(baseline: Path, current: Path) -> dict[str, Any]:
    # Canonical path checks occur in v2.5's local summary. Reject identical
    # directories and aliases: comparison must not reuse the same cohort folder.
    before = summary(baseline)
    after = summary(current)
    if baseline.resolve() == current.resolve():
        raise ValueError("Comparison requires two distinct local folders")
    old_total, new_total = before["records"], after["records"]
    old = _safe_issue_counts(before, MIN_COMPARISON)
    new = _safe_issue_counts(after, MIN_COMPARISON)
    base = {
        **_base(), "operation": "compare",
        "baseline_records": old_total, "current_records": new_total,
        "minimum_per_cohort": MIN_COMPARISON,
        "version_cohort_membership_verified": False,
        "independent_participant_ids_verified": False,
        "sample_method_matched": False,
        "change_is_statistically_significant": None,
        "claims_product_improvement": False,
        "issue_comparisons": None,
    }
    if old is None or new is None:
        return {
            **base, "status": "insufficient_evidence",
            "reason_code": "small_cohort_or_privacy_suppression",
        }
    changes = []
    for issue in sorted((set(old) | set(new)) - {POSITIVE}):
        a, b = old.get(issue, 0), new.get(issue, 0)
        changes.append({
            "issue": issue,
            "baseline_count": a, "current_count": b,
            "baseline_sample_share": round(a / old_total, 4),
            "current_sample_share": round(b / new_total, 4),
            "sample_share_delta_pp": round(100 * (b / new_total - a / old_total), 2),
        })
    changes.sort(key=lambda x: (-abs(x["sample_share_delta_pp"]), x["issue"]))
    return {
        **base, "status": "descriptive_only",
        "reason_code": None,
        "issue_comparisons": changes,
        "caveat": (
            "Descriptive differences are not proof of improved user experience. "
            "Respondents, collection windows, duplication and cohorts are unverified; "
            "survey selection can fully explain observed differences."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prioritize")
    p.add_argument("--directory", type=Path, required=True)
    c = sub.add_parser("compare")
    c.add_argument("--baseline-directory", type=Path, required=True)
    c.add_argument("--current-directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = (prioritize(args.directory) if args.command == "prioritize"
                  else compare(args.baseline_directory, args.current_directory))
    except (ValueError, OSError, UnicodeError, TypeError, RuntimeError):
        print(json.dumps({
            "status": "error", "reason_code": "invalid_cohort_or_directory",
            "network_used": False, "upload_performed": False,
        }))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

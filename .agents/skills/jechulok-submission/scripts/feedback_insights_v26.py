#!/usr/bin/env python3
"""Offline v2.6 feedback triage and descriptive, opt-in cohort comparison.

Input is exclusively the exact four-field v2.5 local feedback schema.
Never reads documents or sends network traffic. This tool cannot measure
representative satisfaction, independent participants, or causal quality.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

from feedback_v25 import (
    ISSUES, MAX_ENTRIES, MAX_FILE_BYTES, SUFFIX, canonical_directory,
    check_record,
)

MIN_PRIORITY_SAMPLE = 20
MIN_COMPARISON_SAMPLE = 30
MIN_CATEGORY_COUNT = 5
CHANGE_THRESHOLD_PP = 5.0

# Static guidance, not generated from private records or institutional text.
NEXT_ACTION = {
    "unclear_next_step": "Simplify the next-action guidance and retest first-run flow",
    "unclear_technical_rule": "Add explicit rule examples and ambiguity warnings",
    "file_selection_confusing": "Clarify manual file selection and candidate previews",
    "approval_confusing": "Explain the exact-plan approval gate more clearly",
    "error_message_unhelpful": "Add actionable, non-sensitive error recovery guidance",
    "operation_too_slow": "Profile synthetic workloads before optimizing performance",
    "installation_trouble": "Test the guided install and MCP connection path",
    "other_usability_issue": "Recruit voluntary usability reviews to define this category",
}


def read_entries(directory: Path) -> list[dict[str, str]]:
    """Read a bounded set of canonical, non-symlink regular v2.5 files."""
    parent = canonical_directory(directory)
    candidates: list[Path] = []
    for item in parent.iterdir():
        if item.name.endswith(SUFFIX):
            candidates.append(item)
            if len(candidates) > MAX_ENTRIES:
                raise ValueError("Too many feedback entries")
    records = []
    for item in candidates:
        if item.is_symlink():
            raise ValueError("Invalid feedback entry")
        try:
            # O_NOFOLLOW closes the symlink-swap window where supported.
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            descriptor = os.open(item, flags)
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
                    raise ValueError("Invalid feedback entry")
                payload = stream.read(MAX_FILE_BYTES + 1)
            if len(payload) > MAX_FILE_BYTES:
                raise ValueError("Invalid feedback entry")
            records.append(check_record(json.loads(payload.decode("utf-8"))))
        except (OSError, UnicodeError, TypeError, ValueError):
            raise ValueError("Invalid feedback entry") from None
    return records


def _base(records: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema": "jechulok-feedback-insights-v26",
        "source": "explicit_local_v25_feedback_only",
        "record_count": len(records),
        "minimum_category_count": MIN_CATEGORY_COUNT,
        "upload_performed": False,
        "network_used": False,
        "saved": False,
        "shareable_summary": False,
        "human_participants_verified": False,
        "representative_sample": False,
    }


def _counts(records: list[dict[str, str]], minimum: int) -> Counter[str] | None:
    if len(records) < minimum:
        return None
    counts = Counter(item["issue"] for item in records)
    # Suppress the entire dimension, not only rare cells: publishing the
    # remaining cells plus a total could reconstruct an omitted cell.
    if any(0 < count < MIN_CATEGORY_COUNT for count in counts.values()):
        return None
    return counts


def prioritize(directory: Path) -> dict[str, Any]:
    records = read_entries(directory)
    result = {**_base(records), "mode": "prioritize",
              "minimum_records": MIN_PRIORITY_SAMPLE}
    counts = _counts(records, MIN_PRIORITY_SAMPLE)
    if counts is None:
        return {
            **result, "status": "insufficient_or_sparse_feedback",
            "priorities": None,
            "note": "No issue ranking: minimum sample or privacy cell threshold not met.",
        }
    return {
        **result, "status": "descriptive_priorities_only",
        "priorities": [
            {"issue": issue, "reports": count,
             "share_percent": round(count / len(records) * 100, 1),
             "next_experiment": NEXT_ACTION[issue]}
            for issue, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
            if issue != "worked_well"
        ],
        "note": (
            "Rank is based on frequency among voluntary responses only, not "
            "impact, number of distinct users, or prevalence among all users."
        ),
    }


def compare(baseline_dir: Path, candidate_dir: Path, *,
            conditions_comparable: bool = False) -> dict[str, Any]:
    baseline = canonical_directory(baseline_dir)
    candidate = canonical_directory(candidate_dir)
    if baseline == candidate:
        raise ValueError("Choose two distinct local cohort directories")
    old = read_entries(baseline)
    new = read_entries(candidate)
    result = {
        "schema": "jechulok-feedback-insights-v26", "mode": "compare",
        "baseline_records": len(old), "candidate_records": len(new),
        "minimum_records_per_cohort": MIN_COMPARISON_SAMPLE,
        "minimum_category_count": MIN_CATEGORY_COUNT,
        "source": "user_partitioned_local_v25_folders",
        "conditions_attested_by_user": bool(conditions_comparable),
        "conditions_independently_verified": False,
        "participant_independence_verified": False,
        "upload_performed": False, "network_used": False, "saved": False,
        "shareable_summary": False,
    }
    if not conditions_comparable:
        return {
            **result, "status": "comparison_not_authorized",
            "differences": None,
            "note": "Use --conditions-comparable only after reviewing sampling and wording.",
        }
    counts_old = _counts(old, MIN_COMPARISON_SAMPLE)
    counts_new = _counts(new, MIN_COMPARISON_SAMPLE)
    if counts_old is None or counts_new is None:
        return {
            **result, "status": "insufficient_or_sparse_cohorts",
            "differences": None,
            "note": "No comparison: both cohorts must pass sample and cell thresholds.",
        }
    differences = []
    for issue in ISSUES:
        a = 100 * counts_old[issue] / len(old)
        b = 100 * counts_new[issue] / len(new)
        delta = b - a
        differences.append({
            "issue": issue,
            "baseline_share_percent": round(a, 1),
            "candidate_share_percent": round(b, 1),
            "difference_percentage_points": round(delta, 1),
            "direction": (
                "more_reports" if delta >= CHANGE_THRESHOLD_PP else
                "fewer_reports" if delta <= -CHANGE_THRESHOLD_PP else "little_change"
            ),
        })
    return {
        **result, "status": "descriptive_comparison_only",
        "differences": differences,
        "quality_improved": None,
        "note": (
            "Differences describe self-selected reports only. Cohorts and "
            "repeat respondents are not verifiable; this is NOT evidence "
            "of causal improvement or statistical significance."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    priority_parser = commands.add_parser("prioritize")
    priority_parser.add_argument("--directory", type=Path, required=True)
    compare_parser = commands.add_parser("compare")
    compare_parser.add_argument("--baseline-dir", type=Path, required=True)
    compare_parser.add_argument("--candidate-dir", type=Path, required=True)
    compare_parser.add_argument("--conditions-comparable", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = (prioritize(args.directory) if args.command == "prioritize"
                  else compare(args.baseline_dir, args.candidate_dir,
                               conditions_comparable=args.conditions_comparable))
    except (ValueError, OSError, TypeError):
        print(json.dumps({"status": "error", "reason": "invalid_local_feedback_or_folders",
                          "no_data_uploaded": True}))
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

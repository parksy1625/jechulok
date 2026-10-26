#!/usr/bin/env python3
"""JeChulOK v2.5: explicitly opt-in, minimal local usability feedback.

No network, no telemetry, no free-text fields or source-document references.
Only allowlisted, coarse categorical answers; no client identifiers, file
paths, timestamps or installation fingerprint within saved feedback.
Preview is read-only. Save creates one new local JSON file (0600 POSIX)
ONLY after an explicit --output-dir argument. Summaries hide small cohorts.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from typing import Any

SCHEMA = "jechulok-feedback-v25"
SUFFIX = ".feedback-v25.json"
MAX_FILE_BYTES = 1024
MAX_ENTRIES = 500
MIN_COHORT = 5

STAGES = ("notice", "files", "plan", "prepare", "check", "installation")
ISSUES = (
    "unclear_next_step", "unclear_technical_rule",
    "file_selection_confusing", "approval_confusing",
    "error_message_unhelpful", "operation_too_slow",
    "installation_trouble", "other_usability_issue",
    "worked_well",
)
IMPACTS = ("none", "minor", "blocked")

# No freeform comments, OS/IDE/version, session IDs, timestamps or paths.
KEYS = {"schema", "stage", "issue", "impact"}


def record(stage: str, issue: str, impact: str) -> dict[str, str]:
    if type(stage) is not str or stage not in STAGES:
        raise ValueError("Invalid feedback stage")
    if type(issue) is not str or issue not in ISSUES:
        raise ValueError("Invalid feedback issue")
    if type(impact) is not str or impact not in IMPACTS:
        raise ValueError("Invalid feedback impact")
    return {"schema": SCHEMA, "stage": stage, "issue": issue, "impact": impact}


def check_record(payload: Any) -> dict[str, str]:
    if type(payload) is not dict or set(payload) != KEYS:
        raise ValueError("Feedback must contain only allowlisted categorical fields")
    return record(payload["stage"], payload["issue"], payload["impact"])


def canonical_directory(value: Path) -> Path:
    supplied = value.expanduser().absolute()
    try:
        canonical = supplied.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError("Feedback folder must already exist") from None
    if canonical != supplied or not canonical.is_dir() or supplied.is_symlink():
        raise ValueError("Feedback folder must be an existing canonical directory without links")
    return canonical


def save(item: dict[str, str], output_dir: Path) -> dict[str, Any]:
    checked = check_record(item)
    parent = canonical_directory(output_dir)
    payload = (json.dumps(checked, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
    if len(payload) > MAX_FILE_BYTES:
        raise ValueError("Unexpected feedback length")
    # Never overwrite any existing user file. The random name is local
    # collision prevention only; it is NOT stored in the feedback itself.
    filename = "entry-" + secrets.token_hex(12) + SUFFIX
    target = parent / filename
    descriptor = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    # No local path in output, to prevent accidental path sharing.
    return {
        "status": "saved_locally", "schema": SCHEMA, "file_created": True,
        "contents_are_categorical_only": True,
        "upload_performed": False, "telemetry_enabled": False,
        "action": "You may inspect and delete the saved entry manually. Nothing was sent.",
    }


def summary(directory: Path) -> dict[str, Any]:
    parent = canonical_directory(directory)
    candidates = []
    # Bound input work even if the user-specified folder contains many files.
    for file in parent.iterdir():
        if file.name.endswith(SUFFIX):
            candidates.append(file)
            if len(candidates) > MAX_ENTRIES:
                raise ValueError("Too many local feedback entries to summarize")
    stages: Counter[str] = Counter()
    issues: Counter[str] = Counter()
    impacts: Counter[str] = Counter()
    for file in candidates:
        if file.is_symlink():
            raise ValueError("Invalid feedback entry in selected directory")
        try:
            # Opening with O_NOFOLLOW prevents a symlink swap between the
            # path check above and the actual read on POSIX systems.
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            descriptor = os.open(file, flags)
            with os.fdopen(descriptor, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_FILE_BYTES:
                    raise ValueError("Invalid feedback entry in selected directory")
                data = stream.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise ValueError("Invalid feedback entry in selected directory")
            item = check_record(json.loads(data.decode("utf-8")))
        except (ValueError, OSError, UnicodeError, TypeError, json.JSONDecodeError):
            raise ValueError("Invalid feedback entry in selected directory") from None
        stages[item["stage"]] += 1
        issues[item["issue"]] += 1
        impacts[item["impact"]] += 1
    count = len(candidates)
    shared = {
        "schema": SCHEMA, "source": "local_opt_in_only",
        "records": count, "network_used": False, "upload_performed": False,
        "data_collected_automatically": False,
        "privacy_note": (
            "Only categorical self-reports. These convenience-sample counts "
            "are not a representative usability study."
        ),
    }
    # Per-category totals may reveal someone when a cohort is small.
    # Do not release any breakdown for fewer than five entries.
    if count < MIN_COHORT:
        return {
            **shared, "status": "insufficient_sample",
            "minimum_required": MIN_COHORT,
            "breakdown": None, "shareable_summary": False,
        }
    # To prevent recovering sparse counts by subtraction, release a
    # breakdown ONLY when every nonzero cell in a dimension is >= 3.
    def safe_dimension(values: Counter[str]) -> dict[str, int] | None:
        return (
            dict(sorted(values.items())) if all(v >= 3 for v in values.values())
            else None
        )
    return {
        **shared, "status": "summarized",
        "minimum_required": MIN_COHORT,
        "breakdown": {
            "stages": safe_dimension(stages),
            "issues": safe_dimension(issues),
            "impacts": safe_dimension(impacts),
        },
        "shareable_summary": False,
        "sharing_requires_separate_manual_review": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="command", required=True)
    for command in ("preview", "save"):
        sub = actions.add_parser(command)
        sub.add_argument("--stage", choices=STAGES, required=True)
        sub.add_argument("--issue", choices=ISSUES, required=True)
        sub.add_argument("--impact", choices=IMPACTS, required=True)
        if command == "save":
            sub.add_argument("--output-dir", type=Path, required=True,
                             help="User-selected existing local folder; no uploads")
    sub = actions.add_parser("summary")
    sub.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "summary":
            outcome = summary(args.directory)
        else:
            item = record(args.stage, args.issue, args.impact)
            if args.command == "preview":
                outcome = {
                    "status": "preview_only", "feedback": item,
                    "saved": False, "uploaded": False,
                    "requires_explicit_save": True,
                }
            else:
                outcome = save(item, args.output_dir)
    except (ValueError, OSError, TypeError):
        print(json.dumps({
            "status": "error", "reason": "invalid_feedback_or_local_directory",
            "no_data_uploaded": True,
        }))
        return 1
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

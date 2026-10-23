#!/usr/bin/env python3
"""v1.9 local-only independent-label notice evaluator.

No real notice data is bundled. This evaluates a user-supplied, legally
reusable and manually redacted JSONL corpus. Results are aggregate only.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from notice_batch import analyze_notice

MAX_BYTES = 2_000_000
MAX_CASES = 500
MAX_LINE = 24_000
FIELDS = ("expected_format", "max_kb", "width", "height", "max_pages")
CATEGORIES = {
    "photo", "resume", "cover_letter", "graduation", "employment",
    "transcript", "portfolio", "certificate",
}
RIGHTS = {"public_domain", "open_license", "permission", "authorized_internal"}
REVIEW_DECISIONS = {"parsed", "needs_review"}
SENSITIVE = (
    ("email", re.compile(r"(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b")),
    ("korean_mobile", re.compile(r"(?<!\d)01[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)")),
    ("korean_resident_number", re.compile(r"(?<!\d)\d{6}[- ]?[1-8]\d{6}(?!\d)")),
    ("korean_landline", re.compile(r"(?<!\d)0(?:2|3[1-3]|4[1-4]|5[1-5]|6[1-4])[- ]?\d{3,4}[- ]?\d{4}(?!\d)")),
)


class InvalidCorpus(ValueError):
    """A private dataset failed validation. Do not reveal its contents."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise InvalidCorpus(reason)


def _canonical(assessment: dict[str, Any]) -> tuple[Any, ...]:
    """Independent labels, not product output, define ground truth."""
    _require(type(assessment) is dict, "Invalid reviewer label")
    _require(set(assessment) == {"reviewer", "decision", "items"}, "Invalid reviewer schema")
    reviewer = assessment["reviewer"]
    _require(type(reviewer) is str and bool(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,31}", reviewer)),
             "Reviewer must have a pseudonymous ID")
    decision = assessment["decision"]
    _require(type(decision) is str and decision in REVIEW_DECISIONS, "Unknown human decision")
    items = assessment["items"]
    _require(type(items) is list and len(items) <= 12, "Invalid human item list")
    if decision == "needs_review":
        _require(not items, "Ambiguous notices may not carry executable gold rules")
    else:
        _require(bool(items), "Parsed notices require gold items")
    normalized: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    for item in items:
        _require(type(item) is dict and set(item) == {"category", "rules"},
                 "Invalid human item schema")
        category = item["category"]
        _require(type(category) is str and category in CATEGORIES and category not in seen,
                 "Unknown or duplicated human category")
        seen.add(category)
        rules = item["rules"]
        _require(type(rules) is dict and bool(rules) and not (set(rules) - set(FIELDS)),
                 "Invalid human rules")
        normalized_fields: list[tuple[str, Any]] = []
        for key in FIELDS:
            if key not in rules:
                continue
            val = rules[key]
            if key == "expected_format":
                _require(type(val) is str and val in {"jpg", "pdf", "png", "webp"},
                         "Unknown expected format")
            else:
                _require(type(val) is int and 1 <= val <= 51200
                         if key == "max_kb" else
                         type(val) is int and 1 <= val <= (5000 if key == "max_pages" else 20000),
                         "Invalid positive limit")
            normalized_fields.append((key, val))
        _require(any(k == "expected_format" for k, _ in normalized_fields),
                 "Human gold must include expected_format")
        normalized.append((category, tuple(normalized_fields)))
    return (decision, tuple(sorted(normalized)))


def _tokens(items: tuple[Any, ...]) -> set[tuple[Any, ...]]:
    result: set[tuple[Any, ...]] = set()
    for category, rules in items:
        for key, value in rules:
            result.add((category, key, value))
    return result


def _prediction(notice: str) -> tuple[str, tuple[Any, ...]]:
    parsed = analyze_notice(notice)
    items: list[tuple[str, tuple[tuple[str, Any], ...]]] = []
    if parsed["status"] == "parsed":
        for item in parsed["items"]:
            fields = item["parsed"]["rules"]
            items.append((item["category"], tuple((f, fields[f]) for f in FIELDS if fields[f] is not None)))
    return (parsed["status"], tuple(sorted(items)))


def _fraction(num: int, den: int) -> float | None:
    return round(num / den, 6) if den else None


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise InvalidCorpus("Missing, linked or oversized local corpus")
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise InvalidCorpus("Corpus size changed or exceeds allowed limit")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError:
        raise InvalidCorpus("Corpus must be UTF-8") from None
    rows = text.splitlines()
    _require(0 < len(rows) <= MAX_CASES, "Corpus must have 1..500 JSONL cases")
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    hashes: set[str] = set()
    for num, line in enumerate(rows, 1):
        _require(0 < len(line) <= MAX_LINE, f"Invalid size on line {num}")
        try:
            doc = json.loads(line)
        except (ValueError, TypeError):
            raise InvalidCorpus(f"Malformed JSONL on line {num}") from None
        _require(type(doc) is dict and set(doc) in (
            {"id", "notice", "rights", "privacy_reviewed", "labels"},
            {"id", "notice", "rights", "privacy_reviewed", "labels", "adjudication"},
        ), f"Invalid record schema at line {num}")
        identifier = doc["id"]
        _require(type(identifier) is str and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", identifier))
                 and identifier not in ids, f"Duplicate/invalid case ID at line {num}")
        ids.add(identifier)
        notice = doc["notice"]
        _require(type(notice) is str and 1 <= len(notice) <= 20000,
                 f"Invalid notice at line {num}")
        _require(notice.strip() == notice and "\0" not in notice,
                 f"Unexpected notice whitespace/control at line {num}")
        digest = hashlib.sha256(notice.encode("utf-8")).hexdigest()
        _require(digest not in hashes, f"Duplicate notice at line {num}")
        hashes.add(digest)
        _require(type(doc["rights"]) is dict and set(doc["rights"]) == {"basis", "confirmed"}
                 and type(doc["rights"]["basis"]) is str
                 and doc["rights"]["basis"] in RIGHTS and doc["rights"]["confirmed"] is True,
                 f"Missing documented reuse authorization at line {num}")
        _require(doc["privacy_reviewed"] is True,
                 f"Missing human privacy review at line {num}")
        for sensitive_name, pattern in SENSITIVE:
            _require(not pattern.search(notice), f"Potential {sensitive_name} identifier in line {num}")
        labels = doc["labels"]
        _require(type(labels) is list and len(labels) == 2,
                 f"Two independent human labels are required on line {num}")
        first, second = (_canonical(l) for l in labels)
        _require(labels[0]["reviewer"] != labels[1]["reviewer"],
                 f"Reviewers must be different on line {num}")
        agreed = first == second
        if "adjudication" in doc:
            adj = doc["adjudication"]
            _require(type(adj) is dict and set(adj) == {"reason", "label"}
                     and type(adj["reason"]) is str and 4 <= len(adj["reason"]) <= 160,
                     f"Invalid adjudication at line {num}")
            resolved = _canonical(adj["label"])
            _require(not agreed and adj["label"]["reviewer"] not in
                     {labels[0]["reviewer"], labels[1]["reviewer"]},
                     f"Adjudication must be by a third independent reviewer on line {num}")
        else:
            resolved = first if agreed else None
        result.append({"id": identifier, "notice": notice, "agreed": agreed, "gold": resolved})
    return result


def evaluate(path: Path, *, strict: bool = False) -> dict[str, Any]:
    docs = _load(path)
    agreements = sum(item["agreed"] for item in docs)
    resolved = [item for item in docs if item["gold"] is not None]
    tp = fp = fn = 0
    parse_exact = unambiguous = ambiguity_cases = unsafe_accept = false_block = 0
    error_counts = Counter()
    for case in resolved:
        gold_decision, gold_items = case["gold"]
        predicted_status, predicted_items = _prediction(case["notice"])
        if gold_decision == "needs_review":
            ambiguity_cases += 1
            if predicted_status == "parsed":
                unsafe_accept += 1
                error_counts["unsafe_acceptance"] += 1
            continue
        unambiguous += 1
        if predicted_status != "parsed":
            false_block += 1
            error_counts["false_block"] += 1
        if predicted_status == "parsed" and predicted_items == gold_items:
            parse_exact += 1
        predicted_tokens = _tokens(predicted_items) if predicted_status == "parsed" else set()
        gold_tokens = _tokens(gold_items)
        tp += len(predicted_tokens & gold_tokens)
        fp += len(predicted_tokens - gold_tokens)
        fn += len(gold_tokens - predicted_tokens)
        if gold_tokens - predicted_tokens:
            error_counts["missing_constraints"] += 1
        if predicted_tokens - gold_tokens:
            error_counts["incorrect_constraints"] += 1

    eligible = len(resolved)
    details = {
        "dataset_type": "user_provided_reviewed_notices",
        "claims_real_world_representativeness": False,
        "dataset_is_bundled": False,
        "cases_total": len(docs),
        "reviewers_per_case": 2,
        "independent_agreement_cases": agreements,
        "agreement_rate": _fraction(agreements, len(docs)),
        "unresolved_cases": len(docs) - eligible,
        "adjudicated_cases": eligible - agreements,
        "eligible_cases": eligible,
        "unambiguous_gold_cases": unambiguous,
        "ambiguous_gold_cases": ambiguity_cases,
        "metrics": {
            "field_value_precision": _fraction(tp, tp + fp),
            "field_value_recall": _fraction(tp, tp + fn),
            "constraint_omission_rate": _fraction(fn, tp + fn),
            "wrong_constraint_rate_among_predictions": _fraction(fp, tp + fp),
            "exact_notice_match_rate": _fraction(parse_exact, unambiguous),
            "unsafe_accept_rate": _fraction(unsafe_accept, ambiguity_cases),
            "correct_ambiguity_block_rate": _fraction(ambiguity_cases - unsafe_accept, ambiguity_cases),
            "false_block_rate": _fraction(false_block, unambiguous),
        },
        "counts": {"tp": tp, "fp": fp, "fn": fn,
                   "unsafe_accept": unsafe_accept, "false_block": false_block},
        "error_case_counts": dict(error_counts),
        "warnings": [
            "Aggregate results only; raw notices, reviewer identities, output paths and IDs are never printed.",
            "PII pattern screening and human privacy attestation are not a guarantee of anonymization.",
            "Sample accuracy does not imply population accuracy without representative sampling.",
            "A missing metric (null) means that denominator was zero or no eligible case existed.",
        ],
    }
    details["status"] = (
        "needs_adjudication" if eligible != len(docs)
        else "no_eligible_cases" if not eligible
        else "evaluated"
    )
    if strict and details["status"] != "evaluated":
        details["status"] = "incomplete"
    return details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="Absolute or relative LOCAL JSONL file")
    parser.add_argument("--strict", action="store_true",
                        help="Exit nonzero if even one record needs adjudication")
    args = parser.parse_args()
    try:
        report = evaluate(args.corpus, strict=args.strict)
    except (InvalidCorpus, OSError, ValueError) as exc:
        # Input errors are kept generic to avoid leaking raw private notices.
        print(json.dumps({"status": "invalid_corpus", "reason": str(exc),
                          "notices_emitted": False}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["status"] == "evaluated" else (1 if args.strict else 0)


if __name__ == "__main__":
    sys.exit(main())

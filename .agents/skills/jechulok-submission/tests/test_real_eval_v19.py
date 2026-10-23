"""v1.9 real-world evaluation harness tests — SYNTHETIC fixtures only.

No user notices are committed or uploaded to GitHub.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_real_v19 import evaluate, InvalidCorpus


def reviewer(name: str, decision: str, items: list | None = None) -> dict:
    return {"reviewer": name, "decision": decision, "items": items or []}


def row(case_id: str, notice: str, left: dict, right: dict,
        adjudication: dict | None = None) -> dict:
    case = {
        "id": case_id, "notice": notice,
        "rights": {"basis": "permission", "confirmed": True},
        "privacy_reviewed": True, "labels": [left, right],
    }
    if adjudication is not None:
        case["adjudication"] = adjudication
    return case


class RealNoticeEvaluationV19Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test-fixtures.jsonl"
        self.photo = [{"category": "photo", "rules": {
            "expected_format": "jpg", "width": 300, "height": 400, "max_kb": 500,
        }}]
        self.pdf = [{"category": "resume", "rules": {
            "expected_format": "pdf", "max_kb": 2048, "max_pages": 3,
        }}]

    def tearDown(self):
        self.temp.cleanup()

    def save(self, cases: list[dict]) -> None:
        self.path.write_text(
            "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases),
            encoding="utf-8",
        )

    def test_independent_agreement_and_all_correct_aggregate(self):
        self.save([
            row("case_one", "- 증명사진: JPG 300×400px 500KB 이하",
                reviewer("R1", "parsed", self.photo),
                reviewer("R2", "parsed", self.photo)),
            row("case_two", "- 이력서: PDF 2MB 이하 최대 3페이지",
                reviewer("R1", "parsed", self.pdf),
                reviewer("R2", "parsed", self.pdf)),
            row("case_three", "- 증명사진: JPG 300×400px 500KB 이하\n공통 PDF 3MB 이하",
                reviewer("R1", "needs_review"),
                reviewer("R2", "needs_review")),
        ])
        r = evaluate(self.path, strict=True)
        self.assertEqual(r["status"], "evaluated", r)
        self.assertEqual(r["cases_total"], 3)
        self.assertEqual(r["independent_agreement_cases"], 3)
        self.assertEqual(r["metrics"]["field_value_precision"], 1)
        self.assertEqual(r["metrics"]["field_value_recall"], 1)
        self.assertEqual(r["metrics"]["exact_notice_match_rate"], 1)
        self.assertEqual(r["metrics"]["unsafe_accept_rate"], 0)
        self.assertEqual(r["metrics"]["correct_ambiguity_block_rate"], 1)
        self.assertEqual(r["counts"]["tp"], 7)
        self.assertEqual(r["counts"]["fp"], 0)
        self.assertEqual(r["counts"]["fn"], 0)
        self.assertNotIn("case_one", json.dumps(r))
        self.assertNotIn("증명사진", json.dumps(r))

    def test_missing_and_incorrect_constraints_are_counted_separately(self):
        # Human gold requires 350px width but parser finds 300px. That is
        # one missing true-value token and one wrong predicted token.
        gold = [{"category": "photo", "rules": {
            "expected_format": "jpg", "width": 350, "height": 400, "max_kb": 500,
        }}]
        self.save([row("wrong_width", "- 증명사진: JPG 300×400px 500KB 이하",
                       reviewer("R1", "parsed", gold), reviewer("R2", "parsed", gold))])
        report = evaluate(self.path)
        self.assertEqual(report["counts"], {
            "tp": 3, "fp": 1, "fn": 1, "unsafe_accept": 0, "false_block": 0,
        })
        self.assertEqual(report["metrics"]["field_value_precision"], 0.75)
        self.assertEqual(report["metrics"]["field_value_recall"], 0.75)
        self.assertEqual(report["metrics"]["exact_notice_match_rate"], 0)
        self.assertEqual(report["error_case_counts"]["missing_constraints"], 1)
        self.assertEqual(report["error_case_counts"]["incorrect_constraints"], 1)

    def test_unsafe_accept_and_false_block_are_distinct(self):
        valid = "- 증명사진: JPG 300×400px 500KB 이하"
        ambiguous = "- 이력서: PDF 2MB 이하 최대 3페이지"
        self.save([
            row("unsafe_case", valid, reviewer("A", "needs_review"),
                reviewer("B", "needs_review")),
            row("blocked_case", ambiguous, reviewer("A", "parsed", [
                {"category": "resume", "rules": {
                    "expected_format": "pdf", "max_kb": 2048, "max_pages": 2
                }}
            ]), reviewer("B", "parsed", [
                {"category": "resume", "rules": {
                    "expected_format": "pdf", "max_kb": 2048, "max_pages": 2
                }}
            ])),
        ])
        # One unsafe acceptance. Second case parses, with wrong pages but
        # does not count as false-block; negative cases are separate.
        r = evaluate(self.path)
        self.assertEqual(r["counts"]["unsafe_accept"], 1)
        self.assertEqual(r["counts"]["false_block"], 0)
        self.assertEqual(r["metrics"]["unsafe_accept_rate"], 1)
        self.assertEqual(r["metrics"]["exact_notice_match_rate"], 0)

    def test_disagreement_excluded_until_third_reviewer_adjudicates(self):
        notice = "- 이력서: PDF 2MB 이하 최대 3페이지"
        left, right = reviewer("L", "parsed", self.pdf), reviewer("R", "needs_review")
        self.save([row("disputed", notice, left, right)])
        r = evaluate(self.path, strict=True)
        self.assertEqual(r["status"], "incomplete")
        self.assertEqual(r["eligible_cases"], 0)
        self.assertEqual(r["unresolved_cases"], 1)
        self.assertIsNone(r["metrics"]["field_value_recall"])
        self.save([row("disputed", notice, left, right, {
            "reason": "Third independent reviewer checked explicit format and page limits",
            "label": reviewer("Third", "parsed", self.pdf),
        })])
        r2 = evaluate(self.path, strict=True)
        self.assertEqual(r2["status"], "evaluated")
        self.assertEqual(r2["adjudicated_cases"], 1)
        self.assertEqual(r2["independent_agreement_cases"], 0)
        self.assertEqual(r2["metrics"]["exact_notice_match_rate"], 1)

    def test_invalid_duplicate_ids_and_duplicate_notices_rejected(self):
        notice = "- 이력서: PDF 2MB 이하 최대 3페이지"
        base = row("same", notice, reviewer("A", "parsed", self.pdf),
                   reviewer("B", "parsed", self.pdf))
        for cases in ([base, base], [base, {**base, "id": "different"}]):
            with self.subTest(cases=len(cases)):
                self.save(cases)
                with self.assertRaises(InvalidCorpus):
                    evaluate(self.path)

    def test_missing_authorization_and_identifiers_fail_closed(self):
        valid = row("case_a", "- 이력서: PDF 2MB 이하 최대 3페이지",
                    reviewer("A", "parsed", self.pdf),
                    reviewer("B", "parsed", self.pdf))
        cases = [
            {**valid, "privacy_reviewed": False},
            {**valid, "rights": {"basis": "permission", "confirmed": False}},
            {**valid, "notice": "연락처 test.user@example.com\n- 이력서: PDF 2MB 이하"},
            {**valid, "notice": "전화 010-1234-5678\n- 이력서: PDF 2MB 이하"},
            {**valid, "notice": "주민등록 991231-1234567\n- 이력서: PDF 2MB 이하"},
            {**valid, "labels": [reviewer("A", "parsed", self.pdf),
                                 reviewer("A", "parsed", self.pdf)]},
            {**valid, "labels": [{"reviewer": "A", "decision": [],
                                  "items": self.pdf},
                                 reviewer("B", "parsed", self.pdf)]},
        ]
        for i, case in enumerate(cases):
            with self.subTest(case=i):
                self.save([case])
                with self.assertRaises(InvalidCorpus):
                    evaluate(self.path)

    def test_valid_schema_but_unknown_gold_field_is_rejected(self):
        invalid = [{"category": "resume", "rules": {
            "expected_format": "pdf", "invented_rule": 25,
        }}]
        self.save([row("unknown", "- 이력서: PDF 2MB 이하",
                       reviewer("A", "parsed", invalid),
                       reviewer("B", "parsed", invalid))])
        with self.assertRaises(InvalidCorpus):
            evaluate(self.path)

    def test_cli_emits_aggregate_only_and_nothing_identifiable(self):
        self.save([row("private_case_id", "- 이력서: PDF 2MB 이하 최대 3페이지",
                       reviewer("ReviewerOne", "parsed", self.pdf),
                       reviewer("ReviewerTwo", "parsed", self.pdf))])
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "evaluate_real_v19.py"),
             str(self.path), "--strict"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        output = json.loads(p.stdout)
        self.assertEqual(output["status"], "evaluated")
        for forbidden in ("private_case_id", "ReviewerOne", "ReviewerTwo", str(self.path), "- 이력서: PDF"):
            self.assertNotIn(forbidden, p.stdout)

    def test_unlicensed_cli_rejects_without_echoing_notice(self):
        notice = "비공개 예시 자료 test@example.com"
        self.save([row("bad", notice,
                       reviewer("A", "needs_review"),
                       reviewer("B", "needs_review"))])
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "evaluate_real_v19.py"),
             str(self.path), "--strict"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(p.returncode, 2)
        self.assertEqual(json.loads(p.stdout)["status"], "invalid_corpus")
        self.assertNotIn(notice, p.stdout)
        self.assertNotIn(str(self.path), p.stdout)


if __name__ == "__main__":
    unittest.main()

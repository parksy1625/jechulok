#!/usr/bin/env python3
"""v1.8 synthetic-only evaluation (100 deterministic independent-label cases).

This measures a narrow component regression set, not real-world accuracy or
observed human behavior. No private files, network, uploads, or approvals.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from unittest.mock import patch

FAMILIES = ("rule_extraction", "ambiguity_guardrail", "file_choice_guardrail", "execution_guardrail")
FAMILY_COUNT = 25
TOTAL = 100


def evaluate() -> dict[str, Any]:
    from PIL import Image
    from pypdf import PdfWriter
    from notice_batch import analyze_notice
    from guided_clarity import notice_issues
    from submission_assistant import assist
    from background_jobs import LocalJobManager
    import mcp_server as server

    result: dict[str, Any] = {
        "name": "jechulok_synthetic_guidance_v18",
        "fixture_version": 1, "dataset_type": "synthetic_only",
        "expected_cases": TOTAL,
        "real_world_accuracy": None, "human_study_participants": 0,
        "families": {name: {"total": 0, "passed": 0} for name in FAMILIES},
        "failures": [], "metrics": {},
        "real_user_documents_processed": False,
        "uploads_performed": False, "execution_approvals_granted": False,
    }

    notice_variants: set[str] = set()

    def assess(family: str, case: str, passed: bool, reason: str) -> None:
        metric = result["families"][family]
        metric["total"] += 1
        metric["passed"] += int(bool(passed))
        if not passed:
            result["failures"].append({"case": f"{family}:{case}", "reason": reason})

    # 25 independently specified unambiguous rule templates.
    for i in range(5):
        w, h, kb = 300 + i * 10, 400 + i * 10, 500 + i * 100
        mb, pages = i + 2, i + 3
        photo = f"- 증명사진: JPG {w}×{h}px {kb}KB 이하"
        pdf_rule = f"PDF {mb}MB 이하 최대 {pages}페이지"
        cases = (
            (photo, [("jpg", kb, w, h, None)]),
            (f"- 이력서: {pdf_rule}", [("pdf", mb * 1024, None, None, pages)]),
            (f"- 자기소개서: {pdf_rule}", [("pdf", mb * 1024, None, None, pages)]),
            (f"- 포트폴리오: {pdf_rule}", [("pdf", mb * 1024, None, None, pages)]),
            (photo + f"\n- 이력서: {pdf_rule}",
             [("jpg", kb, w, h, None), ("pdf", mb * 1024, None, None, pages)]),
        )
        for j, (text, expected) in enumerate(cases):
            notice_variants.add(text)
            parsed = analyze_notice(text)
            got = [tuple(entry["parsed"]["rules"][key] for key in
                         ("expected_format", "max_kb", "width", "height", "max_pages"))
                   for entry in parsed["items"]]
            assess("rule_extraction", f"{i}-{j}",
                   parsed["status"] == "parsed" and got == expected,
                   "Explicit ground truth format/size/pixels/pages mismatch")

    # 25 independently labelled ambiguous cases: ALWAYS request human review.
    for i in range(5):
        kb = 300 + i * 100
        photo = f"- 증명사진: JPG 300×400px {kb}KB 이하"
        variants = (
            (photo + f"\n공통 PDF {i+2}MB 이하", "unassigned_condition"),
            (photo + "\n" + photo, "duplicate_document_type"),
            (photo + "\n- 이력서: PDF 2MB 이하 흰색 배경", "uncertain_document_rule"),
            (f"- 증명사진: JPG 또는 PNG 300×400px {kb}KB 이하", "uncertain_document_rule"),
            (f"- 증명사진: JPG 300×400px {kb}KB 이하 {kb+100}KB 이하",
             "uncertain_document_rule"),
        )
        for j, (text, code) in enumerate(variants):
            notice_variants.add(text)
            parsed = analyze_notice(text)
            issues = notice_issues(text)
            assess(
                "ambiguity_guardrail", f"{i}-{j}",
                parsed["status"] == "needs_review"
                and issues["status"] == "needs_review"
                and code in {x["code"] for x in issues["issues"]}
                and issues["files_modified"] is False,
                "Ambiguity was incorrectly accepted or lacked the expected issue",
            )

    # All files below are temporary synthetic fixtures (including deliberately
    # deceptive filename-only candidate decoys with INVALID contents).
    with tempfile.TemporaryDirectory(prefix="jechulok-eval-v18-") as tmp:
        root = Path(tmp).resolve()
        journal = root / ".jechulok-jobs"
        photo = root / "photo.png"
        Image.new("RGB", (640, 480), "white").save(photo)
        pdf = root / "resume.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=200, height=300)
        with pdf.open("wb") as file:
            writer.write(file)
        for i in range(5):
            (root / f"증명사진_{i}.png").write_bytes(b"invalid PNG - filename decoy")
            (root / f"이력서_{i}.pdf").write_bytes(b"invalid PDF - filename decoy")
            (root / f"random_{i}.pdf").write_bytes(b"invalid PDF - random")
        notice = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 3MB 이하 최대 3페이지"
        jobs = LocalJobManager(journal_root=journal)

        def assist_case(**kwargs: Any) -> dict[str, Any]:
            return assist(
                jobs=jobs, confine=server._confined,
                confine_directory=server._confined_directory, **kwargs,
            )

        with patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(root)}):
            # 25 candidate cases: 5 opt-in/partial-mapping variants repeated
            # with 5 distinct fixture indices; each must be nondestructive.
            for i in range(5):
                variants = (
                    ({"notice_text": notice}, 2, False),
                    ({"notice_text": notice, "source_directory": str(root)}, 2, True),
                    ({"notice_text": notice, "source_directory": str(root),
                      "assignments": [{"item_id": "item_01", "input_path": str(photo)}]}, 1, True),
                    ({"notice_text": notice, "source_directory": str(root),
                      "assignments": [{"item_id": "item_02", "input_path": str(pdf)}]}, 1, True),
                    ({"notice_text": notice}, 2, False),
                )
                for j, (kwargs, count, scanned) in enumerate(variants):
                    # Separate explicit rule values distinguish all 25
                    # notices while preserving the expected choice action.
                    scenario_notice = (
                        f"- 증명사진: JPG 300×400px {500 + i * 20}KB 이하\n"
                        f"- 이력서: PDF {3 + j}MB 이하 최대 3페이지"
                    )
                    notice_variants.add(scenario_notice)
                    before = {p.name for p in root.iterdir()}
                    outcome = assist_case(**{**kwargs, "notice_text": scenario_notice})
                    choice = outcome.get("file_selection", {})
                    items = choice.get("items", [])
                    hints = [hint for item in items for hint in item.get("candidate_hints", [])]
                    okay = (
                        outcome["workflow"]["next_action"] == "choose_source"
                        and choice.get("missing_count") == count
                        and choice.get("directory_scan_requested") == scanned
                        and choice.get("auto_assign") is False
                        and all(x.get("requires_explicit_user_selection") is True for x in items)
                        and all(x.get("requires_manual_review") is True for x in hints)
                        and all(len(x.get("candidate_hints", [])) <= 3 for x in items)
                        and (bool(hints) if scanned else not hints)
                        and outcome["human_approval_recorded"] is False
                        and before == {p.name for p in root.iterdir()}
                        and not journal.exists()
                    )
                    assess("file_choice_guardrail", f"{i}-{j}", okay,
                           "Hint used without opt-in, became an automatic choice, or wrote files")

            # 25 unsafe execution attempts: absent flags, absent/fake token,
            # altered output paths and unapproved crop. No writes allowed.
            for i in range(5):
                assignments = [
                    {"item_id": "item_01", "input_path": str(photo),
                     "output_path": str(root / f"ready_{i}.jpg")},
                    {"item_id": "item_02", "input_path": str(pdf),
                     "output_path": str(root / f"ready_{i}.pdf"),
                     "pages_to_extract": "1-3"},
                ]
                preview = assist_case(notice_text=notice, assignments=assignments)
                fingerprint = preview.get("approval_fingerprint")
                changed = [dict(x) for x in assignments]
                changed[0]["output_path"] = str(root / f"changed_{i}.jpg")
                crop = [dict(x) for x in assignments]
                crop[0]["mode"] = "cover"
                cases = (
                    (assignments, dict(execute=True, confirm_execution=False,
                                       approval_fingerprint=fingerprint), "awaiting_human_approval"),
                    (assignments, dict(execute=True, confirm_execution=True),
                     "awaiting_human_approval"),
                    (assignments, dict(execute=True, confirm_execution=True,
                                       approval_fingerprint="0" * 64), "plan_changed"),
                    (changed, dict(execute=True, confirm_execution=True,
                                   approval_fingerprint=fingerprint), "plan_changed"),
                    (crop, dict(execute=True, confirm_execution=True,
                                approval_fingerprint=fingerprint), "needs_review"),
                )
                for j, (mapping, flags, expected) in enumerate(cases):
                    # Height 401 and varying size limits keep this family
                    # distinct from the candidate cases, not merely IDs.
                    scenario_notice = (
                        f"- 증명사진: JPG 300×401px {510 + i * 20}KB 이하\n"
                        f"- 이력서: PDF {3 + j}MB 이하 최대 3페이지"
                    )
                    notice_variants.add(scenario_notice)
                    # Same inputs and approval flags, but a new notice
                    # requires its OWN exact plan fingerprint.
                    scenario_preview = assist_case(
                        notice_text=scenario_notice, assignments=assignments,
                    )
                    current_flags = dict(flags)
                    if "approval_fingerprint" in current_flags and current_flags["approval_fingerprint"] != "0" * 64:
                        current_flags["approval_fingerprint"] = scenario_preview.get("approval_fingerprint")
                    before = {p.name for p in root.iterdir()}
                    outcome = assist_case(
                        action="start", notice_text=scenario_notice, assignments=mapping, **current_flags
                    )
                    assess(
                        "execution_guardrail", f"{i}-{j}",
                        outcome["status"] == expected
                        and outcome["human_approval_recorded"] is False
                        and outcome["institutional_submission_confirmed"] is False
                        and outcome.get("execution_permitted") is not True
                        and not jobs._jobs
                        and before == {p.name for p in root.iterdir()}
                        and not journal.exists(),
                        "An unsafe start request wrote files or advanced past confirmation",
                    )

    count = sum(group["total"] for group in result["families"].values())
    passed = sum(group["passed"] for group in result["families"].values())
    counts_ok = all(x["total"] == FAMILY_COUNT for x in result["families"].values())
    result["evaluated_cases"] = count
    result["distinct_synthetic_notices"] = len(notice_variants)
    result["passed_cases"] = passed
    result["status"] = (
        "pass" if counts_ok and count == TOTAL
        and len(notice_variants) == TOTAL and passed == count else "fail"
    )
    for group in result["families"].values():
        group["pass_rate"] = round(group["passed"] / group["total"], 4)
    result["metrics"] = {
        "known_rule_fixture_match_rate": result["families"]["rule_extraction"]["pass_rate"],
        "ambiguity_block_rate": result["families"]["ambiguity_guardrail"]["pass_rate"],
        "candidate_non_autoselection_rate": result["families"]["file_choice_guardrail"]["pass_rate"],
        "unsafe_execution_refusal_rate": result["families"]["execution_guardrail"]["pass_rate"],
        "missing_document_selection_prompt_count": 1,
        "prompt_count_basis": "single grouped prompt in the static two-item fixture; not a human study",
        "candidate_semantic_accuracy": None,
        "real_notice_generalization": None,
        "real_user_satisfaction": None,
    }
    result["interpretation"] = (
        "These 100 generated, known-label component cases are not a real-world "
        "accuracy estimate. Candidate names are deliberately not content-verified. "
        "Prompt count is a deterministic UI snapshot, not an observed dialogue."
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Return a failing exit status when a regression is detected")
    args = parser.parse_args()
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.check and report["status"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""JeChulOK v2.4 — 24 synthetic onboarding state evaluations.

Six invented technical notices × four states each: all inputs missing,
one input missing, complete plan awaiting approval, and an ambiguous
condition. No personal notices, background jobs or actual submissions.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter

from background_jobs import LocalJobManager
from submission_assistant import assist
import mcp_server


def evaluate() -> dict:
    results = []
    total_missing = 0
    grouped_questions = 0
    with tempfile.TemporaryDirectory(prefix="jechulok-v24-ux-synthetic-") as temp:
        root = Path(temp).resolve()
        image = root / "photo.png"
        Image.new("RGB", (640, 480), "white").save(image)
        pdf = root / "resume.pdf"
        doc = PdfWriter()
        for _ in range(7):
            doc.add_blank_page(width=210, height=297)
        with pdf.open("wb") as file:
            doc.write(file)
        jobs = LocalJobManager(journal_root=root / ".jechulok-jobs")
        with patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(root)}):
            for variant in range(6):
                notice = (
                    f"- 증명사진: JPG {300 + variant * 10}×{400 + variant * 10}px "
                    f"{500 + variant * 50}KB 이하\n"
                    f"- 이력서: PDF 5MB 이하 최대 {3 + variant}페이지"
                )
                assignments = [
                    {"item_id": "item_01", "input_path": str(image),
                     "output_path": str(root / f"photo_{variant}.jpg")},
                    {"item_id": "item_02", "input_path": str(pdf),
                     "output_path": str(root / f"resume_{variant}.pdf"),
                     "pages_to_extract": "1-3"},
                ]
                cases = (
                    ("both_files_missing", notice, None, "choose_source", 2, 2),
                    ("one_file_missing", notice, assignments[:1], "choose_source", 1, 2),
                    ("exact_plan_requires_approval", notice, assignments,
                     "approve_exact_plan", 0, 3),
                    ("ambiguous_notice", notice + f"\n공통 PDF {2 + variant}MB 이하",
                     assignments, "clarify_notice", 0, 1),
                )
                for key, message, mappings, action, missing, stage in cases:
                    before = sorted(p.name for p in root.iterdir())
                    answer = assist(
                        notice_text=message,
                        assignments=mappings,
                        confine=mcp_server._confined,
                        confine_directory=mcp_server._confined_directory,
                        jobs=jobs,
                    )
                    ux = answer["experience"]
                    no_private_output = (str(root) not in json.dumps(ux, ensure_ascii=False))
                    ok = (
                        ux["next_action"] == action
                        and ux["current_stage"] == stage
                        and ux["outstanding_file_choices"] == missing
                        and len(ux["file_choices"]) == missing
                        and ux["progress_percent"] == 20 * (stage - 1)
                        and ux["institutional_submission_verified"] is False
                        and ux["automatic_file_selection"] is False
                        and ux["telemetry_recorded"] is False
                        and ux["requires_separate_human_approval"] ==
                            (action == "approve_exact_plan")
                        and no_private_output
                        and sorted(p.name for p in root.iterdir()) == before
                        and not jobs._jobs
                        and not (root / ".jechulok-jobs").exists()
                    )
                    results.append({"id": f"{variant+1:02d}_{key}", "passed": ok})
                    if key == "both_files_missing":
                        total_missing += missing
                        grouped_questions += 1

    passed = sum(1 for row in results if row["passed"])
    return {
        "suite": "jechulok_v24_synthetic_first_run_ux",
        "status": "pass" if len(results) == 24 and passed == 24 else "fail",
        "scenarios": results,
        "scenario_count": len(results),
        "passed_count": passed,
        "complete_missing_document_cases": 6,
        "total_missing_documents_in_those_cases": total_missing,
        "one_grouped_question_per_case": grouped_questions,
        "individual_question_counterfactual": total_missing,
        "counterfactual_question_saving_fraction":
            round(1 - grouped_questions / total_missing, 4),
        "counterfactual_is_not_observed_behavior": True,
        "real_notice_accuracy": None,
        "observed_user_question_count": None,
        "human_testers": 0,
        "network_used": False,
        "real_personal_documents_read": False,
        "jobs_started": False,
        "outputs_created": False,
        "metrics_notice": (
            "The 50% prompt difference compares one grouped prompt with a "
            "hypothetical one-prompt-per-missing-file baseline on six synthetic "
            "two-document cases. It is NOT a measured real-user reduction."
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

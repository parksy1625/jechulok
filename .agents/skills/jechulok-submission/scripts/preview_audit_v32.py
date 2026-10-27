#!/usr/bin/env python3
"""Six fabricated v3.2 risk-preview scenarios, no personal inputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter

from preview_prepare_v32 import preview_file


def run_audit() -> dict:
    results: list[dict[str, str]] = []

    def check(code: str, passed: bool) -> None:
        results.append({"code": code, "status": "pass" if passed else "fail"})

    with tempfile.TemporaryDirectory(prefix="jechulok-v32-audit-") as temp:
        work = Path(temp)
        photo = work / "invented.png"
        Image.new("RGB", (640, 480), "lightblue").save(photo)
        pdf = work / "invented.pdf"
        writer = PdfWriter()
        for i in range(3):
            writer.add_blank_page(width=200 + i * 50, height=300)
        with pdf.open("wb") as fh:
            writer.write(fh)
        photo_before = photo.read_bytes()
        pdf_before = pdf.read_bytes()

        args = {"input_path": str(photo),
                "rules_text": "JPG 가로 300픽셀 세로 400픽셀 500KB 이하"}
        padded = preview_file(**args)
        check("contain_padding", padded["status"] == "ready_for_review"
              and any(r["code"] == "white_padding" for r in padded["risks"]))
        cropped = preview_file(**args, mode="cover")
        check("crop_separate_approval", cropped["status"] == "ready_for_review"
              and any(r["code"] == "center_crop" and r["requires_separate_approval"]
                      for r in cropped["risks"]))
        with patch("preview_prepare_v32.info_for", side_effect=AssertionError("read before rules")):
            unclear = preview_file(input_path=str(photo), rules_text="얼굴 위치 확인")
        check("ambiguous_notice_no_file_read", unclear["status"] == "needs_review"
              and unclear["input"] is None)
        pdf_rules = "PDF 최대 2페이지"
        need_pages = preview_file(input_path=str(pdf), rules_text=pdf_rules)
        check("explicit_pdf_selection", need_pages["action"] == "choose_pages")
        selected = preview_file(input_path=str(pdf), rules_text=pdf_rules, pages="2-3")
        check("selected_page_order", selected["status"] == "ready_for_review"
              and selected["planned_output"]["selected_pages"] == [2, 3])
        existing = preview_file(**args, output=str(pdf))
        check("existing_output_untouched", existing["status"] == "blocked"
              and existing["reason_code"] == "output_exists_or_invalid"
              and photo.read_bytes() == photo_before and pdf.read_bytes() == pdf_before)
        serialized = json.dumps([padded, cropped, unclear, need_pages, selected, existing])
        no_path_leaked = str(work) not in serialized

    return {
        "schema": "jechulok-preview-audit-v32",
        "status": "pass" if no_path_leaked and all(
            x["status"] == "pass" for x in results) else "fail",
        "scenario_count": len(results), "passed_count": sum(
            x["status"] == "pass" for x in results),
        "cases": results, "synthetic_only": True, "no_path_leaked": no_path_leaked,
        "user_documents_read": False, "production_files_written": False,
        "network_used": False, "uploads_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Six synthetic-only read-only preview checks")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        parser.error("--check required")
    outcome = run_audit()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

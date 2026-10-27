#!/usr/bin/env python3
"""Eight invented-file v3.3 postflight scenarios; no user files or uploads."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter

from conversion_guard_v33 import bound_preview, verify_conversion
from jechulok import build_parser, prepare_image, prepare_pdf, safe_file


def run_audit() -> dict:
    results: list[dict[str, str]] = []

    def check(name: str, condition: bool) -> None:
        results.append({"code": name, "status": "pass" if condition else "fail"})

    with tempfile.TemporaryDirectory(prefix="jechulok-v33-invented-") as folder:
        work = Path(folder)
        image = work / "invented.png"
        Image.new("RGB", (640, 480), "navy").save(image)
        output = work / "out.jpg"
        alternate = work / "other.jpg"
        plan = work / "preview.json"
        rules = "JPG 가로 300픽셀 세로 400픽셀 500KB 이하"

        image_plan = bound_preview(input_path=str(image), rules_text=rules, output=str(output))
        check("bound_readonly_preflight", image_plan["status"] == "ready_for_review"
              and not output.exists() and image_plan["files_written"] == 0)
        plan.write_text(json.dumps(image_plan), encoding="utf-8")
        args = build_parser().parse_args(["prepare-image", "--input", str(image),
                                          "--output", str(output), "--width", "300",
                                          "--height", "400", "--max-kb", "500"])
        prepare_image(safe_file(str(image)), args)
        valid = verify_conversion(preview_path=str(plan), input_path=str(image),
                                  output_path_str=str(output))
        check("jpg_postflight_matches", valid["status"] == "pass")
        alternate.write_bytes(output.read_bytes())
        wrong_path = verify_conversion(preview_path=str(plan), input_path=str(image),
                                       output_path_str=str(alternate))
        check("target_substitution_blocked", wrong_path["reason_code"] == "output_path_not_in_preview")
        Image.new("RGB", (300, 400), "black").save(output, "JPEG")
        bad_padding = verify_conversion(preview_path=str(plan), input_path=str(image),
                                        output_path_str=str(output))
        check("unexpected_padding_blocked", bad_padding["reason_code"] == "postflight_mismatch")
        image.write_bytes(image.read_bytes() + b"synthetic change")
        changed = verify_conversion(preview_path=str(plan), input_path=str(image),
                                    output_path_str=str(output))
        check("changed_source_blocked", changed["reason_code"] == "source_changed_since_preview")

        pdf = work / "invented.pdf"
        pdf_output = work / "out.pdf"
        document = PdfWriter()
        for width in (200, 300, 400):
            document.add_blank_page(width=width, height=500)
        with pdf.open("wb") as handle:
            document.write(handle)
        pdf_preview = bound_preview(input_path=str(pdf), rules_text="PDF 최대 2페이지",
                                    pages="3,1", output=str(pdf_output))
        plan.write_text(json.dumps(pdf_preview), encoding="utf-8")
        pdf_args = build_parser().parse_args(["prepare-pdf", "--input", str(pdf),
                                              "--output", str(pdf_output), "--pages", "3,1",
                                              "--max-pages", "2"])
        prepare_pdf(safe_file(str(pdf)), pdf_args)
        pdf_ok = verify_conversion(preview_path=str(plan), input_path=str(pdf),
                                   output_path_str=str(pdf_output))
        check("pdf_page_order_matches", pdf_ok["status"] == "pass")
        # An invented alternative PDF of equal page count but reversed geometry.
        modified = PdfWriter()
        modified.add_blank_page(width=200, height=500)
        modified.add_blank_page(width=400, height=500)
        with pdf_output.open("wb") as handle:
            modified.write(handle)
        pdf_bad = verify_conversion(preview_path=str(plan), input_path=str(pdf),
                                    output_path_str=str(pdf_output))
        check("pdf_wrong_order_blocked", pdf_bad["reason_code"] == "postflight_mismatch")

        with patch("conversion_guard_v33.safe_file", side_effect=AssertionError("source read")):
            unclear = bound_preview(input_path=str(pdf), rules_text="사진 좀 좋게")
        check("ambiguous_rules_block_before_read", unclear["status"] == "needs_review")

        serialized = json.dumps([image_plan, valid, wrong_path, bad_padding, changed,
                                 pdf_preview, pdf_ok, pdf_bad, unclear], ensure_ascii=False)
        no_path = str(work) not in serialized and image.name not in serialized

    passed = sum(item["status"] == "pass" for item in results)
    return {
        "schema": "jechulok-conversion-guard-audit-v33",
        "status": "pass" if passed == len(results) and no_path else "fail",
        "scenario_count": len(results), "passed_count": passed,
        "cases": results, "synthetic_only": True, "synthetic_files_created": True,
        "synthetic_files_cleaned_up": True, "user_documents_read": False,
        "production_files_written": False, "no_path_leaked": no_path,
        "network_used": False, "uploads_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Eight synthetic v3.3 postflight regressions")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        parser.error("--check required")
    result = run_audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""v3.2 local read-only single-file preparation preview.

Only an explicitly provided input is inspected. Never create outputs, return
absolute paths, approve edits, estimate JPEG bytes falsely, or upload files.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

from jechulok import MAX_OUTPUT_PIXELS, evaluation, info_for, output_path, pages_from, safe_file
from submission_rules import parse_requirements


def _report() -> dict[str, Any]:
    return {
        "schema": "jechulok-preview-v32", "status": "needs_review",
        "action": "clarify_requirements", "reason_code": None,
        "input": None, "requested": None, "planned_output": None,
        "risks": [], "technical_checks_before": [],
        "exact_output_size_predictable": False,
        "preview_only": True, "files_written": 0, "network_used": False,
        "automatic_upload": False, "execution_permitted": False,
        "human_approval_recorded": False, "institutional_acceptance_verified": False,
        "limitations": [
            "Image quality and final JPEG bytes cannot be known without encoding.",
            "Document content, portrait composition, digital signatures and actual submission are not verified.",
        ],
    }


def _issue(result: dict[str, Any], code: str, *, status: str = "needs_review",
           action: str = "manual_review") -> dict[str, Any]:
    result.update(status=status, action=action, reason_code=code)
    return result


def _risk(result: dict[str, Any], code: str, *, requires_approval: bool = False,
          fraction_pct: float | None = None) -> None:
    item: dict[str, Any] = {"code": code, "requires_manual_review": True,
                            "requires_separate_approval": requires_approval}
    if fraction_pct is not None:
        item["estimated_area_pct"] = round(fraction_pct, 1)
    result["risks"].append(item)


def _oriented_size(path: Path, width: int, height: int) -> tuple[int, int, bool]:
    """Read only EXIF orientation, not decoded full-size pixels."""
    with Image.open(path) as image:
        orientation = image.getexif().get(274, 1)
    if not isinstance(orientation, int) or orientation not in range(1, 9):
        return width, height, False
    if orientation in {5, 6, 7, 8}:
        return height, width, True
    return width, height, orientation != 1


def preview_file(*, input_path: str, rules_text: str, output: str | None = None,
                 pages: str | None = None, mode: str = "contain") -> dict[str, Any]:
    """Plan without making/approving changes, even for valid file operations."""
    result = _report()
    if mode not in {"contain", "cover"}:
        return _issue(result, "invalid_image_mode", status="blocked")
    # Resolve rules before touching a user file. Ambiguous instructions stop here.
    try:
        parsed = parse_requirements(rules_text)
    except (TypeError, ValueError):
        return _issue(result, "invalid_requirements")
    if parsed["status"] != "parsed":
        result["rule_issue_codes"] = sorted({str(item["code"]) for item in parsed["issues"]})
        return _issue(result, "ambiguous_or_missing_requirements")
    rules = parsed["rules"]
    kind = rules["expected_format"]
    if kind not in {"jpg", "pdf"}:
        return _issue(result, "unsupported_or_missing_target_format")
    result["requested"] = {key: rules[key] for key in
                           ("expected_format", "max_kb", "width", "height", "max_pages")}
    if (kind == "jpg" and pages is not None) or (kind == "pdf" and mode != "contain"):
        return _issue(result, "incompatible_options", status="blocked")
    try:
        source = safe_file(input_path)
        meta = info_for(source)
    except (TypeError, ValueError, OSError):
        return _issue(result, "input_missing_or_unreadable", status="blocked")
    except Exception:
        return _issue(result, "input_inspection_failed", status="blocked")
    result["input"] = {"format": meta["format"], "size_bytes": meta["size_bytes"],
                       "width": meta["width"], "height": meta["height"],
                       "pages": meta["pages"]}
    result["technical_checks_before"] = [
        {"rule": c["rule"], "status": c["status"]}
        for c in evaluation(meta, expected_format=kind, max_kb=rules["max_kb"],
                            width=rules["width"], height=rules["height"],
                            max_pages=rules["max_pages"])["checks"]
    ]
    if meta["issues"]:
        return _issue(result, "source_integrity_unverified", status="blocked")

    if kind == "jpg":
        if meta["format"] not in {"jpg", "png", "webp"}:
            return _issue(result, "unsupported_image_source", status="blocked")
        if type(meta["width"]) is not int or type(meta["height"]) is not int:
            return _issue(result, "image_dimensions_unverified", status="blocked")
        try:
            source_w, source_h, rotated = _oriented_size(source, meta["width"], meta["height"])
        except Exception:
            return _issue(result, "image_orientation_unverified", status="blocked")
        target_w = rules["width"] or source_w
        target_h = rules["height"] or source_h
        if rules["width"] and rules["height"] is None:
            target_h = round(source_h * target_w / source_w)
        if rules["height"] and rules["width"] is None:
            target_w = round(source_w * target_h / source_h)
        if target_w <= 0 or target_h <= 0 or target_w * target_h > MAX_OUTPUT_PIXELS:
            return _issue(result, "output_pixel_limit", status="blocked")
        result["planned_output"] = {
            "format": "jpg", "width": target_w, "height": target_h,
            "requested_max_kb": rules["max_kb"], "estimated_size_bytes": None,
            "size_limit_guaranteed": False,
        }
        if rotated:
            _risk(result, "exif_orientation_applied")
        ratio = (source_w / source_h) / (target_w / target_h)
        if abs(ratio - 1.0) > 1e-7:
            if mode == "cover":
                _risk(result, "center_crop", requires_approval=True,
                      fraction_pct=100 * (1 - min(ratio, 1 / ratio)))
            else:
                _risk(result, "white_padding", fraction_pct=100 * (1 - min(ratio, 1 / ratio)))
        if target_w > source_w or target_h > source_h:
            _risk(result, "upscale_may_reduce_sharpness")
        _risk(result, "metadata_and_transparency_removed")
        if rules["max_kb"] is not None:
            _risk(result, "jpeg_size_may_not_fit")
        if mode == "cover":
            _risk(result, "cover_mode_requires_approval", requires_approval=True)
        already = (meta["format"] == "jpg" and meta["extension"] == "jpg"
                   and not rotated and (rules["width"] is None or meta["width"] == rules["width"])
                   and (rules["height"] is None or meta["height"] == rules["height"])
                   and (rules["max_kb"] is None or meta["size_bytes"] <= rules["max_kb"] * 1024)
                   and output is None and mode == "contain")
        if already:
            result["risks"] = []
            result["status"], result["action"] = "already_compliant", "check_only"
            return result
        extension = "jpg"
        action = "prepare_image"
    else:
        if meta["format"] != "pdf" or type(meta["pages"]) is not int:
            return _issue(result, "unsupported_or_unreadable_pdf", status="blocked")
        if pages is None and meta["extension"] != "pdf":
            return _issue(result, "pdf_extension_mismatch")
        if pages is None:
            if rules["max_pages"] is not None and meta["pages"] > rules["max_pages"]:
                return _issue(result, "choose_explicit_pdf_pages", action="choose_pages")
            if rules["max_kb"] is not None and meta["size_bytes"] > rules["max_kb"] * 1024:
                return _issue(result, "pdf_size_cannot_be_shrunk_by_preview")
            if output is None:
                result["status"], result["action"] = "already_compliant", "check_only"
                return result
            return _issue(result, "pdf_copy_without_page_selection_unsupported")
        try:
            selection = pages_from(pages, meta["pages"])
        except ValueError:
            return _issue(result, "invalid_pdf_page_selection", status="blocked")
        if rules["max_pages"] is not None and len(selection) > rules["max_pages"]:
            return _issue(result, "selected_pages_exceed_limit", status="blocked")
        result["planned_output"] = {
            "format": "pdf", "page_count": len(selection),
            "selected_pages": [index + 1 for index in selection],
            "requested_max_kb": rules["max_kb"], "estimated_size_bytes": None,
            "size_limit_guaranteed": False,
        }
        _risk(result, "pdf_signatures_forms_bookmarks_may_change")
        if rules["max_kb"] is not None:
            _risk(result, "pdf_extraction_may_exceed_size_limit")
        extension = "pdf"
        action = "prepare_pdf"
    try:
        output_path(source, output, extension)
    except (ValueError, OSError):
        return _issue(result, "output_exists_or_invalid", status="blocked")
    result["status"], result["action"] = "ready_for_review", action
    return result


def render_text(report: dict[str, Any]) -> str:
    descriptions = {
        "white_padding": "사진 비율을 유지하기 위해 흰 여백이 생길 수 있습니다",
        "center_crop": "중앙을 기준으로 원본의 일부가 잘립니다",
        "cover_mode_requires_approval": "사진 자르기에는 별도의 명시적 승인이 필요합니다",
        "upscale_may_reduce_sharpness": "원본보다 크게 확대하면 선명도가 떨어질 수 있습니다",
        "exif_orientation_applied": "촬영 방향 메타데이터에 따라 이미지를 회전·반전합니다",
        "metadata_and_transparency_removed": "JPG 변환 중 투명 배경과 메타데이터는 제거됩니다",
        "jpeg_size_may_not_fit": "지정된 용량 제한은 실제 인코딩 전 보증할 수 없습니다",
        "pdf_signatures_forms_bookmarks_may_change": "PDF 추출 시 서명·폼·북마크·첨부가 손실될 수 있습니다",
        "pdf_extraction_may_exceed_size_limit": "PDF 추출 후에도 용량 제한을 초과할 수 있습니다",
    }
    decisions = {
        "prepare_image": "새 JPG 준비 전 사람의 검토 필요",
        "prepare_pdf": "새 PDF 추출 전 사람의 검토 필요",
        "check_only": "기술 조건상 추가 변환이 필요하지 않음",
        "choose_pages": "유지할 PDF 페이지를 직접 선택 필요",
        "manual_review": "제출 조건과 파일 상태를 직접 확인 필요",
        "clarify_requirements": "모호한 제출 규격을 먼저 확인 필요",
    }
    lines = ["제출OK 변환 전 미리보기 (읽기 전용)",
             f"상태: {report['status']}",
             f"권장 행동: {decisions.get(report['action'], report['action'])}"]
    if report["reason_code"]:
        lines.append(f"확인 필요: {report['reason_code']}")
    if report["planned_output"]:
        lines.append("예상 출력: " + json.dumps(report["planned_output"], ensure_ascii=False))
    for risk in report["risks"]:
        message = descriptions.get(risk["code"], risk["code"])
        if "estimated_area_pct" in risk:
            message += f" (면적 추정 {risk['estimated_area_pct']}%)"
        lines.append("주의: " + message)
    lines.append("실제 변환·업로드·승인 없음. 출력 용량은 미리 확정할 수 없습니다.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only file-specific conversion preview")
    parser.add_argument("--input", required=True, help="Explicit local file path; no folder discovery")
    parser.add_argument("--rules", required=True, help="Exact textual technical submission conditions")
    parser.add_argument("--output", help="Proposed NEW output path (existence checked only)")
    parser.add_argument("--pages", help="Explicit PDF page range, e.g. 2-3")
    parser.add_argument("--mode", choices=["contain", "cover"], default="contain")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    result = preview_file(input_path=args.input, rules_text=args.rules,
                          output=args.output, pages=args.pages, mode=args.mode)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result), end="")
    return 0 if result["status"] in {"already_compliant", "ready_for_review"} else 3


if __name__ == "__main__":
    sys.exit(main())

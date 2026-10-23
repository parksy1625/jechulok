"""JeChulOK v0.6: read-only output filename proposals for reviewed file mappings.

This module NEVER writes a file or implies that filename recommendations have
been approved. Actual execution still needs prepare_submission_batch's dry-run
and separate double confirmation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import jechulok as core
from notice_batch import analyze_notice

_FILENAMES = {
    "photo": "증명사진", "resume": "이력서", "cover_letter": "자기소개서",
    "graduation": "졸업증명서", "employment": "재직증명서",
    "transcript": "성적증명서", "portfolio": "포트폴리오",
    "certificate": "자격증",
}


def suggest_output_paths(
    notice_text: str,
    assignments: list[dict[str, Any]],
    output_directory: str,
    *,
    confine: Callable[..., Path],
    confine_directory: Callable[[str], Path],
) -> dict[str, Any]:
    """Propose distinct, currently unused names. Do not create or reserve them."""
    notice = analyze_notice(notice_text)
    if notice["status"] != "parsed":
        return {
            "status": "needs_review", "notice": notice, "proposals": [],
            "message": "모호한 제출 조건을 먼저 확인해야 합니다. 출력 경로는 제안하지 않습니다.",
        }
    if not isinstance(assignments, list) or len(assignments) != len(notice["items"]):
        return {
            "status": "needs_review", "notice": notice, "proposals": [],
            "message": "모든 제출 항목에 확인된 입력 파일을 한 개씩 매칭해야 합니다.",
        }

    directory = confine_directory(output_directory)
    records: dict[str, dict[str, Any]] = {}
    ids = {entry["item_id"] for entry in notice["items"]}
    for assignment in assignments:
        if not isinstance(assignment, dict) or (
            set(assignment) - {"item_id", "input_path", "pages_to_extract"}
        ):
            raise ValueError("출력 경로 제안에는 item_id, input_path, pages_to_extract만 허용합니다.")
        item_id = assignment.get("item_id")
        if not isinstance(item_id, str) or item_id not in ids or item_id in records:
            raise ValueError("item_id가 중복되었거나 공고의 항목과 일치하지 않습니다.")
        records[item_id] = assignment
    if set(records) != ids:
        raise ValueError("누락된 제출 항목이 있습니다.")

    proposals: list[dict[str, Any]] = []
    used_sources: set[Path] = set()
    reserved_names: set[Path] = set()
    problems: list[dict[str, str]] = []

    for item in notice["items"]:
        item_id = item["item_id"]
        assignment = records[item_id]
        rules = item["parsed"]["rules"]
        fmt = rules["expected_format"]
        try:
            source = confine(assignment.get("input_path"))
            if source in used_sources:
                raise ValueError("하나의 입력 파일을 둘 이상의 제출 항목에 지정할 수 없습니다.")
            used_sources.add(source)
            metadata = core.info_for(core.safe_file(str(source)))
            if core.evaluation(metadata)["status"] == "fail":
                raise ValueError("파일 확장자와 실제 내용이 일치하지 않습니다.")
            pages = assignment.get("pages_to_extract")
            if fmt == "jpg":
                if metadata["format"] not in {"jpg", "png", "webp"}:
                    raise ValueError("사진은 JPG/PNG/WebP 원본만 지원합니다.")
                if pages is not None:
                    raise ValueError("사진에는 PDF 페이지 범위를 지정할 수 없습니다.")
                action = "prepare_image"
                warning = None
            elif fmt == "pdf":
                if metadata["format"] != "pdf" or metadata["pages"] is None:
                    raise ValueError("열 수 없는 PDF입니다.")
                if pages is None:
                    report = core.evaluation(
                        metadata, expected_format="pdf",
                        max_kb=rules["max_kb"], max_pages=rules["max_pages"],
                    )
                    if report["status"] == "pass":
                        action = "verify_existing"
                        warning = None
                    else:
                        action = "select_pdf_pages"
                        warning = "PDF가 조건을 통과하지 못했습니다. 보존할 페이지를 사용자가 직접 결정해야 합니다."
                else:
                    if not isinstance(pages, str):
                        raise ValueError("PDF 페이지 선택은 문자열이어야 합니다.")
                    chosen = core.pages_from(pages, metadata["pages"])
                    if rules["max_pages"] is not None and len(chosen) > rules["max_pages"]:
                        raise ValueError("선택된 페이지 수가 제출 조건을 초과합니다.")
                    action = "extract_pdf_pages"
                    warning = "페이지 추출 후 파일 용량은 실행 시 실제로 다시 검증합니다."
            else:
                raise ValueError("자동 처리는 단일 JPG/PDF 규격만 지원합니다.")

            output: Path | None = None
            if action in {"prepare_image", "extract_pdf_pages", "select_pdf_pages"}:
                stem = "제출용_" + _FILENAMES[item["category"]]
                extension = ".jpg" if fmt == "jpg" else ".pdf"
                for index in range(1, 101):
                    suffix = "" if index == 1 else f"_{index}"
                    candidate = directory / (stem + suffix + extension)
                    # These are suggestions, never reserved; execution must recheck.
                    if candidate == source or candidate in used_sources or candidate in reserved_names:
                        continue
                    if candidate.exists() or candidate.is_symlink():
                        continue
                    output = candidate
                    reserved_names.add(candidate)
                    break
                if output is None:
                    raise ValueError("충돌하지 않는 출력 파일 이름을 제안하지 못했습니다.")

            proposals.append({
                "item_id": item_id, "label": item["label"],
                "input_path": str(source), "action": action,
                "suggested_output_path": str(output) if output else None,
                "pages_to_extract": pages,
                "requires_page_selection": action == "select_pdf_pages",
                "requires_user_approval": True,
                "notice_evidence": item["evidence"],
                "warning": warning,
            })
            if action == "select_pdf_pages":
                problems.append({"item_id": item_id, "reason": warning or "PDF 페이지 선택 필요"})
        except (ValueError, OSError, core.Image.DecompressionBombError,
                core.UnidentifiedImageError) as exc:
            problems.append({"item_id": item_id, "reason": str(exc)})

    return {
        "status": "needs_review" if problems else "suggestions_only",
        "notice_status": notice["status"],
        "output_directory": str(directory),
        "proposals": proposals,
        "problems": problems,
        "summary": {
            "total_items": len(notice["items"]),
            "proposed_items": len(proposals),
            "need_attention": len(problems),
            "files_created": 0,
            "technically_verified": 0,
        },
        "notes": [
            "모든 출력 경로는 읽기 전용 제안이며 파일을 생성·예약하지 않습니다.",
            "사용자는 각 파일과 PDF 페이지 범위를 확인해야 합니다.",
            "실제 작업 전 prepare_submission_batch(execute=false)로 계획을 재검증한 뒤 별도로 실행 승인해야 합니다.",
            "문서 내용과 실제 제출 성공 여부는 자동으로 판단할 수 없습니다.",
        ],
    }

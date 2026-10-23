"""JeChulOK v1.7: safe, human-readable guidance without guessing files.

Provides bounded issue explanations, batchable human file-choice prompts,
and read-only filename hints for an EXPLICITLY authorized directory.
No scans without a user-provided directory, no automatic assignments, and
no new authority to approve/crop/submit documents.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from file_candidates import suggest_files
from notice_batch import analyze_notice

MAX_VISIBLE_ISSUES = 5
MAX_HINTS_PER_ITEM = 3


def notice_issues(text: str) -> dict[str, Any]:
    """Return grounded ambiguous lines and precise next-human decisions."""
    parsed = analyze_notice(text)
    issues: list[dict[str, Any]] = []
    for item in parsed["unassigned_conditions"]:
        issues.append({
            "code": "unassigned_condition", "line": item["line"],
            "item_id": None, "evidence": item["evidence"][:180],
            "explanation": "이 파일 규격을 적용할 제출 항목을 알 수 없습니다.",
            "human_decision": "공고 원문에서 적용할 서류를 확인한 뒤 항목별로 조건을 구분해주세요.",
        })
    for item in parsed["items"]:
        if item["status"] == "parsed":
            continue
        duplicate = "issue" in item
        issues.append({
            "code": "duplicate_document_type" if duplicate else "uncertain_document_rule",
            "line": item["line"],
            "item_id": item["item_id"],
            "evidence": item["evidence"][:180],
            "explanation": "같은 종류의 서류가 중복 표기됐습니다." if duplicate
                           else "이 제출 조건을 자동으로 확정할 수 없습니다.",
            "human_decision": "어느 서류를 의미하는지 직접 구분해주세요." if duplicate
                              else "해당 서류의 정확한 파일 형식·규격을 공고에서 확인해주세요.",
        })
    issues.sort(key=lambda item: item["line"])
    first = issues[0] if issues else None
    return {
        "status": parsed["status"],
        "issue_count": len(issues),
        "issues": issues[:MAX_VISIBLE_ISSUES],
        "truncated": len(issues) > MAX_VISIBLE_ISSUES,
        "next_action": first["human_decision"] if first else "공고에서 지원되는 개별 서류 규격을 확인해주세요.",
        "files_modified": False,
    }


def missing_file_choices(
    notice_text: str,
    assignments: list[dict[str, Any]] | None,
    source_directory: str | None,
    *,
    confine_directory: Callable[[str], Path],
) -> dict[str, Any]:
    """Show all still-unassigned items, with *hints* only when opted in."""
    parsed = analyze_notice(notice_text)
    if parsed["status"] != "parsed":
        return {
            "status": "needs_review", "missing_count": 0, "items": [],
            "message": "공고의 모호한 조건부터 사용자에게 확인받아야 합니다.",
            "auto_assign": False,
        }

    matched = {
        entry["item_id"] for entry in (assignments or [])
        if isinstance(entry, dict) and isinstance(entry.get("item_id"), str)
    }
    missing = [
        item for item in parsed["items"] if item["item_id"] not in matched
    ]
    suggestions_by_id: dict[str, Any] = {}
    scan: dict[str, Any] | None = None
    if missing and source_directory is not None:
        if not isinstance(source_directory, str) or not source_directory.strip():
            raise ValueError("source_directory must be a nonempty directory path")
        scan = suggest_files(
            notice_text, source_directory,
            confine_directory=confine_directory,
        )
        suggestions_by_id = {item["item_id"]: item for item in scan["items"]}
    result = []
    for item in missing:
        hint = suggestions_by_id.get(item["item_id"], {})
        result.append({
            "item_id": item["item_id"],
            "label": item["label"],
            "expected_format": item["parsed"]["rules"]["expected_format"],
            "candidate_hints": [
                {
                    "filename": candidate["filename"],
                    "input_path": candidate["input_path"],
                    "match_type": candidate["match_type"],
                    "requires_manual_review": True,
                }
                for candidate in hint.get("candidates", [])[:MAX_HINTS_PER_ITEM]
            ],
            "candidate_count_in_scanned_directory": hint.get("total_compatible_files", 0),
            "requires_explicit_user_selection": True,
        })
    return {
        "status": "needs_input" if missing else "complete",
        "missing_count": len(missing),
        "items": result,
        "directory_scan_requested": source_directory is not None and bool(missing),
        "directory_scan_truncated": scan["truncated"] if scan is not None else False,
        "scan_limit": 250,
        "auto_assign": False,
        "note": (
            "사용자가 지정한 폴더의 바로 아래 항목 최대 250개를 파일명·확장자만 확인했습니다. "
            "후보는 내용 검증이나 서류 적합성 판정이 아니며, 자동 매칭하지 않습니다."
            if scan is not None else
            "폴더를 지정하지 않았으므로 파일을 검색하지 않았습니다."
        ),
    }


def explain_plan_blockers(blocked: list[dict[str, Any]]) -> dict[str, Any]:
    """Bounded errors and stable codes from an actual read-only preflight."""
    rules: tuple[tuple[str, str, str], ...] = (
        ("페이지", "pdf_pages", "PDF에서 유지할 페이지를 직접 지정하거나 현재 페이지 구성을 확인해 주세요."),
        ("pages", "pdf_pages", "PDF에서 유지할 페이지를 직접 지정하거나 현재 페이지 구성을 확인해 주세요."),
        ("중앙 자르기", "crop_approval", "사진을 자르기 전에 자르기 방식을 확인하고 별도로 승인해 주세요."),
        ("crop", "crop_approval", "사진을 자르기 전에 자르기 방식을 확인하고 별도로 승인해 주세요."),
        ("이미", "output_exists", "기존 파일을 덮어쓰지 않도록 새로운 출력 파일명을 선택해 주세요."),
        ("new file", "output_exists", "기존 파일을 덮어쓰지 않도록 새로운 출력 파일명을 선택해 주세요."),
        ("outside", "unsafe_path", "허용한 작업 폴더 안의 실제 파일을 선택해 주세요."),
        ("허용", "unsafe_path", "허용한 작업 폴더 안의 실제 파일을 선택해 주세요."),
        ("symbolic", "unsafe_path", "심볼릭 링크가 아닌 실제 파일 경로를 선택해 주세요."),
        ("PDF", "pdf_invalid", "PDF 원본의 실제 파일 형식과 페이지 수를 확인해 주세요."),
        ("JPG", "image_invalid", "이미지 형식과 제출 규격을 확인해 주세요."),
        ("중복", "duplicate_assignment", "서류별 파일 및 출력 경로의 중복을 확인해 주세요."),
    )
    result: list[dict[str, str]] = []
    for entry in blocked[:MAX_VISIBLE_ISSUES]:
        raw = str(entry.get("reason", ""))[:200]
        code, action = "manual_review", "공고와 원본 파일 조건을 확인한 뒤 다시 미리보기 해주세요."
        for marker, candidate, hint in rules:
            if marker.casefold() in raw.casefold():
                code, action = candidate, hint
                break
        result.append({
            "item_id": str(entry.get("item_id", ""))[:40],
            "code": code, "reason_excerpt": raw,
            "next_action": action,
        })
    return {
        "issue_count": len(blocked), "issues": result,
        "truncated": len(blocked) > MAX_VISIBLE_ISSUES,
        "auto_fix": False, "execution_permitted": False,
    }

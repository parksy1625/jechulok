"""JeChulOK v0.7: read-only human review and final technical package checks.

Never uploads/submits, approves a plan, crops, selects PDF pages, modifies files,
or claims institutional acceptance. No stored approvals or implicit trust.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import jechulok as core
from notice_batch import analyze_notice, prepare_batch

_GUIDES: dict[str, tuple[str, str]] = {
    "format": ("convert_format", "제출 조건의 파일 형식을 확인하고 지원되는 방식으로 새 파일을 준비하세요."),
    "file_signature": ("unrecognized_file", "원본 파일이 올바른 이미지/PDF인지 확인하고 정상 파일을 선택하세요."),
    "extension_matches_content": ("extension_mismatch", "확장자만 변경하지 말고 실제 파일 형식에 맞는 파일을 사용하세요."),
    "max_kb": ("reduce_size", "지정된 용량 제한을 확인하고 품질 조정 또는 적절한 원본으로 다시 준비하세요."),
    "width": ("adjust_dimensions", "사진의 가로 픽셀을 지정된 값으로 다시 준비하세요."),
    "height": ("adjust_dimensions", "사진의 세로 픽셀을 지정된 값으로 다시 준비하세요."),
    "max_pages": ("select_pages", "필요한 PDF 페이지를 사용자가 직접 선택한 후 새 파일로 추출하세요."),
}
_BATCH_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("이미 있습니다", "output_exists", "기존 파일은 덮어쓰지 않습니다. 새 출력 파일명을 선택하세요."),
    ("Output must be a new file", "output_exists", "다른 이름의 새 출력 파일을 선택하세요."),
    ("이미 존재", "output_exists", "새로운 출력 경로를 지정하세요."),
    ("페이지", "select_pages", "PDF에서 유지할 페이지를 사용자가 직접 확정하세요."),
    ("pages", "select_pages", "PDF에서 유지할 페이지를 사용자가 직접 확정하세요."),
    ("중앙 자르기", "crop_permission", "사진을 자르기 전에 사용자에게 자르기 승인을 받으세요."),
    ("승인", "approval_required", "실행할 파일·경로·페이지를 사용자에게 확인받으세요."),
    ("중복", "duplicate_assignment", "각 제출 항목에 서로 다른 파일과 출력 경로를 지정하세요."),
    ("허용", "path_not_allowed", "허용된 작업 폴더 내 파일을 선택하세요."),
    ("outside", "path_not_allowed", "허용된 작업 폴더 내 파일을 선택하세요."),
    ("JPG", "unsupported_format", "명시된 JPG 요건과 지원 이미지 원본 형식을 확인하세요."),
    ("PDF", "check_pdf", "PDF의 내용·유효성·페이지 범위와 용량 제한을 확인하세요."),
)


def _guide_from_error(message: str) -> dict[str, str]:
    for marker, code, advice in _BATCH_PATTERNS:
        if marker.casefold() in message.casefold():
            return {"code": code, "action": advice}
    return {"code": "manual_investigation", "action": "공고의 원문 조건과 파일 상태를 직접 확인하세요."}


def _guide_from_check(check: dict[str, Any]) -> dict[str, str]:
    code, action = _GUIDES.get(
        check["rule"], ("manual_investigation", "기술 조건과 원본 파일을 직접 확인하세요.")
    )
    return {"code": code, "action": action}


def batch_guidance(result: dict[str, Any]) -> dict[str, Any]:
    """Enrich genuine batch tool results with bounded, non-executable advice."""
    guides: list[dict[str, Any]] = []
    for item in result.get("blocked", []):
        issue = _guide_from_error(str(item["reason"]))
        guides.append({"item_id": item["item_id"], **issue})
    if result["status"] == "needs_review" and not guides:
        guides.append({
            "item_id": "all", "code": "clarify_requirements",
            "action": "모호한 제출 규격 또는 누락된 파일 매칭을 사용자에게 확인받으세요.",
        })
    if result["status"] == "error":
        guides.append({"item_id": "all", **_guide_from_error(str(result.get("reason", "")))})
    if result["status"] == "needs_confirmation":
        guides.append({
            "item_id": "all", "code": "approval_required",
            "action": "이 작업 계획 전체를 검토하고 사용자의 명시적 승인을 받으세요.",
        })
    result["remediation"] = guides
    result["approval_checklist"] = [
        {"id": "confirm_notice", "done": False, "required": True,
         "message": "공고의 항목별 파일 조건과 모호한 조건을 직접 확인"},
        {"id": "confirm_paths", "done": False, "required": True,
         "message": "항목별 입력 파일과 새 출력 경로 및 내용 확인"},
        {"id": "confirm_pdf_pages", "done": False, "required": True,
         "message": "PDF 추출 시 보존할 페이지·서명·폼 영향 확인"},
        {"id": "confirm_crop", "done": False, "required": True,
         "message": "사진 자르기가 있다면 실제 사용자 승인 확인"},
        {"id": "approve_exact_plan", "done": False, "required": True,
         "message": "dry-run 결과를 사용자에게 제시하고 실행 승인 확보"},
    ]
    result["human_approval_recorded"] = False
    result["institutional_submission_confirmed"] = False
    return result


def review_plan(
    notice_text: str,
    assignments: list[dict[str, Any]],
    *,
    confine: Callable[..., Path],
) -> dict[str, Any]:
    """Review current files and provide outstanding decisions, never writes."""
    dry = batch_guidance(prepare_batch(
        notice_text, assignments, execute=False, confirm_execution=False,
        confine=confine,
    ))
    blocked = dry["status"] != "planned"
    return {
        "status": "needs_review" if blocked else "awaiting_human_approval",
        "dry_run": True,
        "execution_permitted": False,
        "plan": dry.get("plan", []),
        "summary": dry.get("summary"),
        "notice": dry.get("notice"),
        "blocked": dry.get("blocked", []),
        "remediation": dry["remediation"],
        "approval_checklist": dry["approval_checklist"],
        "next_step": (
            "차단된 조건을 직접 해결한 뒤 다시 미리보기를 생성하세요."
            if blocked else
            "모든 입력·출력 경로, 사진 자르기, PDF 페이지 범위를 사용자에게 검토받으세요. "
            "사용자가 정확한 계획을 명시적으로 승인하기 전에는 실행하지 마세요."
        ),
        "human_approval_recorded": False,
        "institutional_submission_confirmed": False,
    }


def _manual_checklist(notice_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = [
        {"id": "correct_identity_and_content", "required": True, "verified": False,
         "description": "모든 파일의 본문·이름·개인정보 및 제출 대상 적합성을 직접 확인"},
        {"id": "complete_institution_requirements", "required": True, "verified": False,
         "description": "공고 원문의 기타 조건, 파일명 규칙, 마감일·접수 방법 직접 확인"},
        {"id": "review_upload_and_receipt", "required": True, "verified": False,
         "description": "최종 사이트에서 첨부 파일·접수 완료 화면 또는 접수증 직접 확인"},
    ]
    if any(item["category"] == "photo" for item in notice_items):
        checks.append({
            "id": "check_portrait", "required": True, "verified": False,
            "description": "사진 배경·얼굴 위치·인물 식별·기관 사진 규정 직접 확인",
        })
    if any(item["parsed"]["rules"]["expected_format"] == "pdf" for item in notice_items):
        checks.append({
            "id": "check_pdf_integrity", "required": True, "verified": False,
            "description": "PDF의 페이지 순서·본문·서명·첨부·폼 및 북마크 손실 여부 직접 확인",
        })
    return checks


def verify_package(
    notice_text: str,
    files: list[dict[str, Any]],
    *,
    confine: Callable[..., Path],
) -> dict[str, Any]:
    """Read and independently verify explicitly assigned *final* local files."""
    notice = analyze_notice(notice_text)
    checklist = _manual_checklist(notice["items"])
    envelope: dict[str, Any] = {
        "status": "needs_review",
        "results": [],
        "manual_checklist": checklist,
        "manual_review_required": True,
        "ready_to_submit": False,
        "institutional_submission_confirmed": False,
    }
    if notice["status"] != "parsed":
        envelope["remediation"] = [{
            "item_id": "all", "code": "clarify_requirements",
            "action": "공고에서 확정되지 않은 조건을 먼저 확인하세요.",
        }]
        return envelope
    if not isinstance(files, list) or len(files) != len(notice["items"]):
        envelope["remediation"] = [{
            "item_id": "all", "code": "missing_final_files",
            "action": "모든 공고 항목에 최종 파일을 정확히 한 개씩 지정하세요.",
        }]
        return envelope
    expected = {item["item_id"]: item for item in notice["items"]}
    assigned: dict[str, dict[str, Any]] = {}
    for item in files:
        if not isinstance(item, dict) or set(item) != {"item_id", "file_path"}:
            raise ValueError("최종 파일 항목은 item_id와 file_path만 포함해야 합니다.")
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or item_id not in expected or item_id in assigned:
            raise ValueError("최종 파일 item_id가 중복되거나 공고와 일치하지 않습니다.")
        assigned[item_id] = item
    if set(assigned) != set(expected):
        raise ValueError("최종 파일 매칭이 누락되었습니다.")

    used: set[Path] = set()
    remediation: list[dict[str, Any]] = []
    for item in notice["items"]:
        item_id = item["item_id"]
        current: dict[str, Any] = {
            "item_id": item_id, "label": item["label"],
            "technical_status": "unverified",
            "manual_content_review_required": True,
        }
        try:
            path = confine(assigned[item_id]["file_path"])
            if path in used:
                raise ValueError("동일 최종 파일을 여러 제출 항목에 지정할 수 없습니다.")
            used.add(path)
            meta = core.info_for(core.safe_file(str(path)))
            rules = item["parsed"]["rules"]
            report = core.evaluation(
                meta, expected_format=rules["expected_format"],
                max_kb=rules["max_kb"], width=rules["width"],
                height=rules["height"], max_pages=rules["max_pages"],
            )
            # Independently enforce parseability even where the notice omits
            # width/height or a PDF page count.
            if meta["format"] == "pdf" and meta["pages"] is None and report["status"] == "pass":
                report["status"] = "unverified"
            if meta["format"] == "jpg" and (
                meta["width"] is None or meta["height"] is None
            ) and report["status"] == "pass":
                report["status"] = "unverified"
            current.update({
                "file_path": str(path),
                "technical_status": report["status"],
                "checks": report["checks"], "observed": meta,
            })
            for check in report["checks"]:
                if check["status"] != "pass":
                    remediation.append({"item_id": item_id, **_guide_from_check(check)})
            if report["status"] == "unverified" and not any(
                entry["item_id"] == item_id for entry in remediation
            ):
                remediation.append({
                    "item_id": item_id, "code": "unreadable_document",
                    "action": "페이지 수·이미지 무결성을 확인할 수 없습니다. 유효한 새 파일을 선택하세요.",
                })
        except (ValueError, OSError, core.Image.DecompressionBombError,
                core.UnidentifiedImageError) as exc:
            current["technical_status"] = "error"
            current["error"] = str(exc)[:250]
            remediation.append({"item_id": item_id, **_guide_from_error(str(exc))})
        envelope["results"].append(current)

    passed = sum(x["technical_status"] == "pass" for x in envelope["results"])
    envelope["status"] = "technical_pass" if passed == len(notice["items"]) else "needs_review"
    envelope["summary"] = {
        "total_items": len(notice["items"]),
        "technically_verified": passed,
        "not_verified": len(notice["items"]) - passed,
        "pending_manual_checks": len(checklist),
        "institutional_submission_confirmed": False,
    }
    envelope["remediation"] = remediation
    envelope["next_step"] = (
        "모든 기술 조건을 통과했습니다. 하지만 본문·서명·사진 규정·실제 접수는 사용자가 직접 확인해야 합니다."
        if envelope["status"] == "technical_pass"
        else "기술 검증이 완료되지 않은 파일과 공고 조건을 수정한 후 재검증하세요."
    )
    return envelope

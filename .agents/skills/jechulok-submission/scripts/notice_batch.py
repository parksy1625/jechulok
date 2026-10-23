"""JeChulOK v0.6: deterministic multi-document notice parsing and safe batch planning.

No LLM, network or OCR. Explicit named line items only; unassigned constraints
and ambiguous conditions block all automated batch processing.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Callable

import jechulok as core
from submission_rules import parse_requirements

MAX_NOTICE_LENGTH = 20_000
MAX_ITEMS = 12
_KIND = (
    ("photo", re.compile(r"^(?:증명사진|지원서\s*사진|프로필\s*사진|사진|반명함(?:판)?\s*사진)$")),
    ("resume", re.compile(r"^(?:이력서|입사지원서)$")),
    ("cover_letter", re.compile(r"^(?:자기소개서|자소서)$")),
    ("graduation", re.compile(r"^(?:졸업증명서|졸업예정증명서)$")),
    ("employment", re.compile(r"^(?:재직증명서|경력증명서)$")),
    ("transcript", re.compile(r"^(?:성적증명서)$")),
    ("portfolio", re.compile(r"^(?:포트폴리오)$")),
    ("certificate", re.compile(r"^(?:자격증\s*사본|자격증명서|자격증)$")),
)
_ITEM_LINE = re.compile(r"^\s*(?:(?:[-*•]\s*)|(?:\d{1,2}[.)]\s*))?(?P<label>[^:：\n]{2,36})\s*[:：]\s*(?P<rules>.+?)\s*$")
_RULE_SIGNAL = re.compile(r"(?i)(?:\b(?:pdf|jpe?g|jfif|png|webp|gif|heic|avif)\b|\d+\s*(?:KB|MB|KiB|MiB|px|픽셀|페이지|쪽|cm|mm)\b|흰색\s*배경|전자\s*서명)")


def _category(label: str) -> str | None:
    name = re.sub(r"\s+", " ", label.strip())
    for kind, pattern in _KIND:
        if pattern.fullmatch(name):
            return kind
    return None


def analyze_notice(notice_text: str) -> dict[str, Any]:
    if not isinstance(notice_text, str) or not notice_text.strip():
        raise ValueError("공고 원문이 필요합니다.")
    if len(notice_text) > MAX_NOTICE_LENGTH:
        raise ValueError("공고는 최대 20,000자까지 분석합니다.")
    entries: list[dict[str, Any]] = []
    unassigned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(notice_text.splitlines(), 1):
        cleaned = line.strip()
        if not cleaned:
            continue
        match = _ITEM_LINE.fullmatch(line)
        category = _category(match.group("label")) if match else None
        if category:
            if len(entries) >= MAX_ITEMS:
                raise ValueError("한 번에 최대 12개 제출 항목을 분석할 수 있습니다.")
            rule_text = match.group("rules").strip()
            parsed = parse_requirements(rule_text)
            duplicate = category in seen
            seen.add(category)
            entry = {
                "item_id": f"item_{len(entries)+1:02d}",
                "label": match.group("label").strip(),
                "category": category,
                "line": line_number,
                "evidence": cleaned,
                "requirements_text": rule_text,
                "status": "needs_review" if duplicate else parsed["status"],
                "parsed": parsed,
            }
            if duplicate:
                entry["issue"] = "같은 종류의 제출 항목이 여러 번 등장합니다. 수동으로 구분하세요."
            entries.append(entry)
        elif _RULE_SIGNAL.search(cleaned):
            unassigned.append({"line": line_number, "evidence": cleaned,
                               "issue": "어느 파일에 적용하는지 확정할 수 없는 조건입니다."})
    if not entries:
        status = "needs_review" if unassigned else "no_items"
    elif unassigned or any(e["status"] != "parsed" for e in entries):
        status = "needs_review"
    else:
        status = "parsed"
    return {
        "status": status,
        "items": entries,
        "unassigned_conditions": unassigned[:40],
        "total_items": len(entries),
        "notes": [
            "항목명이 명시된 '사진: JPG ...' 형태만 분리합니다. 추론으로 파일을 매칭하지 않습니다.",
            "공통 조건 또는 분리되지 않은 숫자/형식 조건이 있으면 일괄 작업을 차단합니다.",
            "검사 결과는 기술 조건에 한정되며 실제 기관 접수를 보증하지 않습니다.",
        ],
    }


def _prepare_batch_internal(
    notice_text: str,
    assignments: list[dict[str, Any]],
    *,
    execute: bool = False,
    confirm_execution: bool = False,
    confine: Callable[..., Path],
) -> dict[str, Any]:
    notice = analyze_notice(notice_text)
    if notice["status"] != "parsed":
        return {"status": "needs_review", "message": "공고의 일부 조건을 항목별로 확정하지 못했습니다.",
                "notice": notice}
    if not isinstance(assignments, list) or len(assignments) != len(notice["items"]):
        return {"status": "needs_review", "message": "모든 제출 항목에 정확히 하나의 파일 매칭이 필요합니다.", "notice": notice}
    if type(execute) is not bool or type(confirm_execution) is not bool:
        raise ValueError("execute 및 confirm_execution은 참/거짓 값이어야 합니다.")

    ids = {e["item_id"] for e in notice["items"]}
    records: dict[str, dict[str, Any]] = {}
    for a in assignments:
        if not isinstance(a, dict) or set(a) - {"item_id", "input_path", "output_path", "pages_to_extract", "mode", "crop_approved"}:
            raise ValueError("허용되지 않는 파일 매칭 필드가 있습니다.")
        item_id = a.get("item_id")
        if not isinstance(item_id, str) or item_id not in ids or item_id in records:
            raise ValueError("item_id가 중복되거나 공고의 항목과 일치하지 않습니다.")
        records[item_id] = a
    if set(records) != ids:
        raise ValueError("누락된 제출 항목이 있습니다.")

    plans: list[dict[str, Any]] = []
    used_inputs: set[Path] = set()
    used_outputs: set[Path] = set()
    blocked: list[dict[str, str]] = []
    for item in notice["items"]:
        a = records[item["item_id"]]
        item_id = item["item_id"]
        rules = item["parsed"]["rules"]
        fmt = rules["expected_format"]
        try:
            src = confine(a.get("input_path"))
            if src in used_inputs:
                raise ValueError("동일한 입력 파일을 여러 항목에 중복 지정할 수 없습니다.")
            used_inputs.add(src)
            meta = core.info_for(core.safe_file(str(src)))
            if core.evaluation(meta)["status"] == "fail":
                raise ValueError("파일 확장자와 실제 내용이 일치하지 않습니다.")
            mode = a.get("mode", "contain")
            if mode not in ("contain", "cover"):
                raise ValueError("이미지 맞춤 방식이 올바르지 않습니다.")
            if mode == "cover" and a.get("crop_approved") is not True:
                raise ValueError("중앙 자르기는 사용자의 명시적 승인이 필요합니다.")

            pages = a.get("pages_to_extract")
            output_path = a.get("output_path")
            if fmt == "jpg":
                if meta["format"] not in {"jpg", "png", "webp"}:
                    raise ValueError("JPG 변환 가능한 이미지 파일이 아닙니다.")
                if pages is not None:
                    raise ValueError("사진 항목에는 PDF 페이지 선택을 적용할 수 없습니다.")
                if not output_path:
                    raise ValueError("JPG 출력 경로를 지정해야 합니다.")
                dest = confine(output_path, for_output=True)
                if dest.suffix.lower() not in {".jpg", ".jpeg"}:
                    raise ValueError("JPG 출력 경로는 .jpg/.jpeg여야 합니다.")
                action = "prepare_image"
            elif fmt == "pdf":
                if meta["format"] != "pdf" or meta["pages"] is None:
                    raise ValueError("PDF가 암호화되었거나 페이지 수를 읽지 못했습니다.")
                if pages is None:
                    report = core.evaluation(meta, expected_format="pdf",
                                             max_kb=rules["max_kb"], max_pages=rules["max_pages"])
                    if report["status"] != "pass":
                        raise ValueError("PDF 원본이 조건에 맞지 않습니다. 보존할 페이지를 직접 지정해야 합니다.")
                    if output_path:
                        raise ValueError("변경 없는 PDF 검사에는 새 출력 경로를 사용하지 않습니다.")
                    dest = None
                    action = "verify_existing"
                else:
                    if not isinstance(pages, str):
                        raise ValueError("PDF 페이지 범위를 문자열로 지정해야 합니다.")
                    selected = core.pages_from(pages, meta["pages"])
                    if rules["max_pages"] is not None and len(selected) > rules["max_pages"]:
                        raise ValueError("선택한 PDF 페이지 수가 제출 제한을 초과합니다.")
                    if not output_path:
                        raise ValueError("PDF 추출 출력 경로를 지정해야 합니다.")
                    dest = confine(output_path, for_output=True)
                    if dest.suffix.lower() != ".pdf":
                        raise ValueError("PDF 출력 경로는 .pdf여야 합니다.")
                    action = "extract_pdf_pages"
            else:
                raise ValueError("자동 일괄 처리는 단일 JPG/PDF 조건만 지원합니다.")

            if dest is not None:
                if src == dest or dest in used_outputs:
                    raise ValueError("출력 경로 중복 또는 원본 덮어쓰기를 허용하지 않습니다.")
                used_outputs.add(dest)
            plans.append({
                "item_id": item_id, "label": item["label"], "action": action,
                "input_path": str(src), "output_path": str(dest) if dest else None,
                "rules": rules, "pages_to_extract": pages,
                "mode": mode, "crop_approved": a.get("crop_approved") is True,
            })
        except (ValueError, OSError, core.Image.DecompressionBombError) as exc:
            blocked.append({"item_id": item_id, "reason": str(exc)})
    if any(Path(p["input_path"]) in used_outputs for p in plans):
        blocked.append({"item_id": "batch", "reason": "출력 파일을 다른 항목의 입력 파일로 사용할 수 없습니다."})
    if blocked:
        return {"status": "needs_review", "message": "파일 매칭 또는 사전 검사가 실패했습니다. 어떤 출력도 생성하지 않았습니다.",
                "blocked": blocked, "plan": plans, "notice": notice}
    if not execute:
        return {"status": "planned", "dry_run": True, "plan": plans, "notice": notice,
                "message": "미리보기입니다. 실제 파일 생성에는 execute=true 및 confirm_execution=true가 모두 필요합니다."}
    if confirm_execution is not True:
        return {"status": "needs_confirmation", "dry_run": True, "plan": plans,
                "message": "실행 승인 없이 파일을 생성하지 않습니다."}

    created: list[Path] = []
    outcomes: list[dict[str, Any]] = []
    try:
        for plan in plans:
            src = Path(plan["input_path"])
            out = Path(plan["output_path"]) if plan["output_path"] else None
            rules = plan["rules"]
            if plan["action"] == "verify_existing":
                report = core.evaluation(core.info_for(src), expected_format="pdf",
                                         max_kb=rules["max_kb"], max_pages=rules["max_pages"])
                if report["status"] != "pass":
                    raise ValueError("PDF 재검사 실패: " + plan["item_id"])
                outcomes.append({"item_id": plan["item_id"], "status": "pass",
                                 "action": "verify_existing", "output": None, "verification": report})
                continue
            if out is None:
                raise ValueError("출력 경로가 없습니다.")
            if out.exists() or out.is_symlink():
                raise ValueError("출력 파일이 이미 있습니다. 덮어쓰기는 허용하지 않습니다.")
            if plan["action"] == "prepare_image":
                args = argparse.Namespace(output=str(out), width=rules["width"], height=rules["height"],
                                          max_kb=rules["max_kb"], mode=plan["mode"])
                operation = core.prepare_image(src, args)
            else:
                args = argparse.Namespace(output=str(out), pages=plan["pages_to_extract"],
                                          max_kb=rules["max_kb"], max_pages=rules["max_pages"])
                operation = core.prepare_pdf(src, args)
            created.append(out)
            verification = core.evaluation(core.info_for(out), expected_format=rules["expected_format"],
                                           max_kb=rules["max_kb"], width=rules["width"],
                                           height=rules["height"], max_pages=rules["max_pages"])
            if verification["status"] != "pass":
                raise ValueError("최종 파일 재검증에 실패했습니다: " + plan["item_id"])
            outcomes.append({"item_id": plan["item_id"], "status": "pass",
                             "action": plan["action"], "output": str(out),
                             "verification": verification, "preparation": operation})
    except Exception as exc:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        return {"status": "error", "message": "일괄 처리 실패. 이번 작업에서 완성된 출력 파일은 정리했습니다.",
                "reason": str(exc)[:300], "rolled_back": [str(x) for x in created], "results": []}
    return {"status": "pass", "dry_run": False, "results": outcomes,
            "limitations": "명시된 형식·픽셀·용량·페이지 수만 검증합니다. 문서 내용과 실제 접수는 확인하지 못합니다."}



def _attach_batch_summary(notice_text: str, result: dict[str, Any]) -> dict[str, Any]:
    """Present item-by-item progress without claiming real-world submission."""
    notice = result.get("notice") or analyze_notice(notice_text)
    items = notice["items"]
    status = result["status"]
    outcome_by_id = {entry["item_id"]: entry for entry in result.get("results", [])}
    plans_by_id = {entry["item_id"]: entry for entry in result.get("plan", [])}
    blocked = {entry["item_id"] for entry in result.get("blocked", [])}
    blocked_all = "batch" in blocked or notice["status"] != "parsed"
    rolled_back = set(result.get("rolled_back", []))
    statuses: list[dict[str, Any]] = []

    for item in items:
        item_id = item["item_id"]
        finished = outcome_by_id.get(item_id)
        plan = plans_by_id.get(item_id, {})
        if status == "pass" and finished and finished["status"] == "pass":
            technical_status = "verified"
        elif status == "error" and any(
            p["item_id"] == item_id and p.get("output_path") in rolled_back
            for p in result.get("plan", [])
        ):
            technical_status = "rolled_back"
        elif blocked_all or item_id in blocked:
            technical_status = "blocked"
        elif status == "planned":
            technical_status = "planned"
        elif status == "needs_confirmation":
            technical_status = "awaiting_confirmation"
        else:
            technical_status = "not_executed"
        statuses.append({
            "item_id": item_id, "label": item["label"],
            "technical_status": technical_status,
            "action": (finished or plan).get("action"),
            "output_path": (finished or {}).get("output"),
            "manual_content_review_required": True,
        })

    verified = [entry for entry in result.get("results", []) if entry.get("status") == "pass"]
    result["summary"] = {
        "total_items": len(items),
        "technically_verified": len(verified) if status == "pass" else 0,
        "generated_files": sum(
            1 for entry in verified if entry.get("output") is not None
        ) if status == "pass" else 0,
        "unchanged_verified": sum(
            1 for entry in verified if entry.get("action") == "verify_existing"
        ) if status == "pass" else 0,
        "blocked_items": sum(1 for entry in statuses if entry["technical_status"] == "blocked"),
        "not_verified": len(items) - (len(verified) if status == "pass" else 0),
        "manual_review_required": True,
        "institutional_submission_confirmed": False,
        "items": statuses,
    }
    return result


def prepare_batch(
    notice_text: str,
    assignments: list[dict[str, Any]],
    *,
    execute: bool = False,
    confirm_execution: bool = False,
    confine: Callable[..., Path],
) -> dict[str, Any]:
    """v0.4 compatible API plus a truthful v0.6 technical progress summary."""
    result = _prepare_batch_internal(
        notice_text, assignments, execute=execute,
        confirm_execution=confirm_execution, confine=confine,
    )
    return _attach_batch_summary(notice_text, result)

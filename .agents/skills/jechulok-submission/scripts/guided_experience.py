"""JeChulOK v0.8: minimal read-only agent guidance and safe local HTML reports.

Neither tool submits documents, selects PDF pages, authorizes processing, stores
approvals, or guarantees acceptance by an institution.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Callable

from notice_batch import analyze_notice
from review_workflow import review_plan, verify_package

MAX_REPORT_BYTES = 256 * 1024


def _first_problem(report: dict[str, Any]) -> dict[str, str] | None:
    guides = report.get("remediation") or []
    if guides:
        first = guides[0]
        return {"code": str(first["code"]), "action": str(first["action"])}
    return None


def guide_next_step(
    notice_text: str,
    assignments: list[dict[str, Any]] | None = None,
    final_files: list[dict[str, Any]] | None = None,
    *,
    confine: Callable[..., Path],
) -> dict[str, Any]:
    """Ask for only one next human decision; never invent consent or write."""
    notice = analyze_notice(notice_text)
    base: dict[str, Any] = {
        "read_only": True,
        "execution_permitted": False,
        "human_approval_recorded": False,
        "institutional_submission_confirmed": False,
        "total_items": len(notice["items"]),
        "unresolved_count": 0,
    }
    if notice["status"] != "parsed":
        details = notice.get("unassigned_conditions") or [
            item for item in notice["items"] if item["status"] != "parsed"
        ]
        first = details[0] if details else {}
        return {**base, "status": "needs_review",
                "next_action": "clarify_notice",
                "item_id": first.get("item_id"),
                "question": "공고에서 이 조건이 어느 서류에 적용되는지 확인해 주세요: "
                            + str(first.get("evidence", first.get("requirements_text", "제출 조건"))),
                "unresolved_count": max(1, len(details))}

    if final_files is not None:
        report = verify_package(notice_text, final_files, confine=confine)
        if report["status"] != "technical_pass":
            issue = _first_problem(report)
            return {**base, "status": "needs_review",
                    "next_action": "fix_final_files", "issue": issue,
                    "question": issue["action"] if issue else "최종 파일 규격을 다시 검토해 주세요.",
                    "unresolved_count": report.get("summary", {}).get("not_verified", 1),
                    "summary": report.get("summary", {})}
        pending = report["manual_checklist"]
        return {**base, "status": "technical_pass_manual_review_pending",
                "next_action": "check_original_content",
                "question": pending[0]["description"] if pending else
                            "파일 내용과 최종 접수 여부를 직접 확인해 주세요.",
                "unresolved_count": len(pending), "summary": report["summary"]}

    if assignments is None:
        assignments = []
    if not isinstance(assignments, list):
        raise ValueError("assignments must be a list")

    # Surface the first missing input, without guessing or reading arbitrary directories.
    known = {item["item_id"] for item in notice["items"]}
    matched: set[str] = set()
    for assignment in assignments:
        if not isinstance(assignment, dict):
            raise ValueError("Each assignment must be an object")
        item_id = assignment.get("item_id")
        if not isinstance(item_id, str) or item_id not in known or item_id in matched:
            raise ValueError("Assignments contain unknown or duplicate item IDs")
        matched.add(item_id)
    missing = [item for item in notice["items"] if item["item_id"] not in matched]
    if missing:
        first = missing[0]
        return {**base, "status": "needs_input", "next_action": "choose_source",
                "item_id": first["item_id"], "question":
                f"{first['label']}에 사용할 실제 파일을 직접 지정해 주세요.",
                "unresolved_count": len(missing)}

    report = review_plan(notice_text, assignments, confine=confine)
    if report["status"] != "awaiting_human_approval":
        issue = _first_problem(report)
        return {**base, "status": "needs_review", "next_action": "fix_plan",
                "issue": issue,
                "question": issue["action"] if issue else "항목별 파일과 공고 조건을 다시 확인해 주세요.",
                "unresolved_count": max(1, len(report.get("blocked", []))),
                "summary": report.get("summary", {})}

    # Explicit paths/pages are provided for user confirmation; never shorten them
    # in a way that could conceal which file would be edited.
    return {**base, "status": "awaiting_human_approval",
            "next_action": "approve_exact_plan",
            "question": "다음 입력·출력 경로와 PDF 페이지 선택을 모두 검토했나요? "
                        "실행을 원하면 이 정확한 작업 계획을 명시적으로 승인해 주세요.",
            "plan_preview": report["plan"],
            "unresolved_count": 1, "summary": report.get("summary", {})}


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _render_report(inspection: dict[str, Any]) -> str:
    """Static, offline HTML with no scripts, images, links or absolute paths."""
    total = inspection.get("summary", {}).get("total_items", 0)
    passed = inspection.get("summary", {}).get("technically_verified", 0)
    rows: list[str] = []
    for entry in inspection.get("results", []):
        observed = entry.get("observed") or {}
        name = Path(entry.get("file_path", "")).name or "(확인 불가)"
        checks = entry.get("checks") or []
        reasons = ", ".join(
            str(check["rule"]) for check in checks if check.get("status") != "pass"
        ) or "—"
        rows.append(
            "<tr><td>" + _escape(entry["label"]) + "</td><td>" + _escape(name)
            + "</td><td>" + _escape(entry["technical_status"]) + "</td><td>"
            + _escape(observed.get("size_bytes", "—")) + "</td><td>"
            + _escape(reasons) + "</td></tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="5">규격을 자동 검사할 수 있는 최종 파일이 없습니다.</td></tr>')
    tasks = "".join(
        '<li><span aria-hidden="true">☐ </span>' + _escape(item["description"]) + "</li>"
        for item in inspection.get("manual_checklist", [])
    )
    remediation = "".join(
        "<li>" + _escape(item["action"]) + "</li>"
        for item in inspection.get("remediation", [])
    )
    if not remediation:
        remediation = "<li>기술 검증 오류가 보고되지 않았습니다. 수동 검토는 여전히 필요합니다.</li>"
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
        "<title>제출OK 기술 검증 보고서</title>"
        "<style>body{font:15px/1.65 system-ui,sans-serif;color:#172033;"
        "max-width:900px;margin:3rem auto;padding:0 1rem}"
        "h1{font-size:1.6rem}h2{font-size:1.2rem;margin-top:2rem}"
        "table{border-collapse:collapse;width:100%;font-size:.9rem}"
        "th,td{border:1px solid #d5dae2;padding:.65rem;text-align:left;word-break:break-word}"
        "th{background:#f4f6fa}li{margin:.45rem 0}"
        "small{color:#526070}.notice{border-left:3px solid #6c7787;padding-left:1rem}"
        "@media print{body{margin:0;max-width:none}}</style></head><body>"
        "<h1>제출OK · 로컬 기술 검증 보고서</h1>"
        '<p class="notice"><strong>접수 완료 증명이 아닙니다.</strong> '
        "기술적 규격만 검사했으며 파일 내용·서명·사진 구성·제출처 접수 여부는 미확인입니다.</p>"
        "<p><strong>검증 결과:</strong> " + _escape(inspection["status"])
        + " · " + _escape(passed) + "/" + _escape(total) + "개 항목 기술 검증</p>"
        "<h2>항목별 검사</h2><table><thead><tr>"
        "<th>제출 항목</th><th>최종 파일명</th><th>기술 상태</th><th>바이트</th><th>미충족 조건</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        "<h2>수정 또는 추가 확인</h2><ul>" + remediation + "</ul>"
        "<h2>사용자 최종 확인 (모두 미완료)</h2><ul>" + tasks + "</ul>"
        "<small>보고서는 로컬에서만 생성됩니다. 원본 파일의 절대 경로, 본문, "
        "사진 픽셀 또는 문서 페이지는 포함하지 않습니다. "
        "검증은 보고서 생성 당시의 상태이며 이후 파일 변경을 보증하지 않습니다.</small>"
        "</body></html>"
    )


def create_report(
    notice_text: str,
    files: list[dict[str, Any]],
    output_path: str,
    *,
    execute: bool = False,
    confirm_execution: bool = False,
    confine: Callable[..., Path],
) -> dict[str, Any]:
    """Preview by default; requires two explicit booleans for exclusive local write."""
    if type(execute) is not bool or type(confirm_execution) is not bool:
        raise ValueError("execute and confirm_execution must be booleans")
    inspection = verify_package(notice_text, files, confine=confine)
    overview = {
        "technical_status": inspection["status"],
        "summary": inspection.get("summary", {}),
        "manual_review_required": True,
        "institutional_submission_confirmed": False,
        "ready_to_submit": False,
    }
    if not execute:
        return {"status": "preview", "dry_run": True,
                "message": "미리보기입니다. 보고서 파일을 생성하지 않았습니다.",
                **overview}
    if not confirm_execution:
        return {"status": "needs_confirmation", "dry_run": True,
                "message": "사용자의 별도 승인 없이 HTML 보고서를 생성하지 않습니다.",
                **overview}

    target = confine(output_path, for_output=True)
    if target.suffix.lower() != ".html":
        raise ValueError("HTML 보고서 출력 경로는 .html 확장자여야 합니다.")
    # Prevent accidental report overwrite even if preflight races with another process.
    data = _render_report(inspection).encode("utf-8")
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError("HTML report is too large")
    created = False
    try:
        with target.open("xb") as stream:
            created = True
            stream.write(data)
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise
    return {"status": "report_created", "dry_run": False,
            "output_path": str(target), "bytes_written": len(data),
            "message": "로컬 정적 HTML 보고서를 생성했습니다. 접수 완료가 아닙니다.",
            **overview}

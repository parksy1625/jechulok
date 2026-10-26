"""JeChulOK v2.4: stateless, user-centered guided MCP entry point.

One tool surfaces one useful human-facing next action without guessing
assignments, granting human approval, or bypassing preflight/locking.
Sessions/notice documents are never stored by this module.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Literal

from guided_experience import guide_next_step
from guided_clarity import explain_plan_blockers, missing_file_choices, notice_issues
from first_run_ux_v24 import progress_view
from review_workflow import review_plan, verify_package


Action = Literal["next", "start", "status", "cancel", "verify"]
STEPS = (
    {"id": "notice", "label": "공고 확인"},
    {"id": "files", "label": "원본 파일 선택"},
    {"id": "plan", "label": "작업 계획 미리보기"},
    {"id": "prepare", "label": "승인 후 파일 준비"},
    {"id": "check", "label": "기술 검증과 직접 확인"},
)


def plan_fingerprint(plan: list[dict[str, Any]]) -> str:
    """A deterministic plan equality check, NOT a human-authentication token."""
    payload = json.dumps(
        plan, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _envelope(
    status: str, step: int, *, next_action: str,
    question: str, **extra: Any,
) -> dict[str, Any]:
    result = {
        "status": status,
        "workflow": {
            "name": "제출OK 안내 모드",
            "step": step, "total_steps": 5,
            "steps": [
                {"id": item["id"], "label": item["label"],
                 "state": "current" if index + 1 == step else
                          "previous" if index + 1 < step else "upcoming"}
                for index, item in enumerate(STEPS)
            ],
            "next_action": next_action,
            "question": question,
        },
        "human_approval_recorded": False,
        "institutional_submission_confirmed": False,
        "automatic_upload": False,
        **extra,
    }
    # Add the same privacy-safe, deterministic status card to ALL outcomes,
    # including missing input, errors, cancellation and final verification.
    result["experience"] = progress_view(result)
    return result


def assist(
    *,
    action: Action = "next",
    notice_text: str | None = None,
    assignments: list[dict[str, Any]] | None = None,
    final_files: list[dict[str, Any]] | None = None,
    job_id: str | None = None,
    approval_fingerprint: str | None = None,
    execute: bool = False,
    confirm_execution: bool = False,
    source_directory: str | None = None,
    confine: Callable[..., Path],
    confine_directory: Callable[[str], Path] | None = None,
    jobs: Any,
) -> dict[str, Any]:
    if action not in {"next", "start", "status", "cancel", "verify"}:
        raise ValueError("Unsupported guide action")
    if type(execute) is not bool or type(confirm_execution) is not bool:
        raise ValueError("Execution flags must be booleans")

    if action in {"status", "cancel"}:
        if not isinstance(job_id, str) or not job_id.strip():
            return _envelope("needs_job_id", 4, next_action="provide_job_id",
                             question="먼저 실행 중인 작업의 job_id를 알려주세요.")
        result = jobs.get(job_id) if action == "status" else jobs.cancel(job_id)
        status = result["status"]
        if status == "completed":
            return _envelope(
                "awaiting_final_verification", 5,
                next_action="verify_final_files",
                question="생성된 최종 파일 경로를 확인하고 기술 검증을 진행할까요?",
                job=result,
            )
        if status in {"failed", "cancelled", "not_found", "recovery_required"}:
            return _envelope(
                "needs_review", 4, next_action="review_failed_job",
                question="출력 파일과 오류를 확인한 뒤 새로운 미리보기와 승인을 진행해주세요.",
                job=result,
            )
        if status == "cancel_requested":
            return _envelope(
                "cancellation_pending", 4, next_action="check_job_again",
                question="취소가 아직 완료되지 않았습니다. 파일 처리가 끝나면 다시 조회해주세요.",
                job=result,
            )
        return _envelope(
            "working" if status in {"running", "queued", "publishing"} else "needs_review",
            4, next_action="check_job_again",
            question="작업 상태를 다시 조회하거나, 취소를 원하면 명확히 요청해주세요.",
            job=result,
        )

    if not isinstance(notice_text, str) or not notice_text.strip():
        return _envelope(
            "needs_input", 1, next_action="provide_notice",
            question="서류 제출 공고의 실제 파일 규격 부분을 알려주세요. 내용을 추측하지 않습니다.",
        )
    if action == "verify":
        if final_files is None:
            return _envelope(
                "needs_input", 5, next_action="choose_final_files",
                question="기술 검증할 최종 파일을 항목별로 직접 지정해 주세요.",
            )
        report = verify_package(notice_text, final_files, confine=confine)
        if report["status"] == "technical_pass":
            return _envelope(
                "manual_review_required", 5, next_action="manual_check_and_submit",
                question="기술 규격은 통과했습니다. 본문·사진 구도·서명·접수증은 직접 확인해 주세요.",
                verification=report,
            )
        first = (report.get("remediation") or [{}])[0]
        return _envelope(
            "needs_review", 5, next_action="fix_final_files",
            question=first.get("action", "최종 파일의 규격을 수정한 뒤 다시 검증해주세요."),
            verification=report,
        )

    if action == "next":
        guide = guide_next_step(
            notice_text, assignments, final_files, confine=confine,
        )
        follow = guide["next_action"]
        step = (
            1 if follow == "clarify_notice" else
            2 if follow == "choose_source" else
            3 if follow in {"fix_plan", "approve_exact_plan"} else 5
        )
        extra: dict[str, Any] = {"guidance": guide}
        if follow == "clarify_notice":
            extra["notice_explanation"] = notice_issues(notice_text)
        if follow == "choose_source":
            # The caller must *explicitly* opt into a folder scan; never
            # search home directories or infer an allowed root.
            if source_directory is not None and confine_directory is None:
                raise ValueError("A directory authorization callback is required")
            extra["file_selection"] = missing_file_choices(
                notice_text, assignments, source_directory,
                confine_directory=confine_directory or _no_directory_search,
            )
            count = extra["file_selection"]["missing_count"]
            if count > 1:
                guide["question"] = (
                    f"다음 {count}개 서류에 사용할 원본 파일을 각각 지정해 주세요. "
                    "파일명 후보는 참고용이며 자동 선택하지 않습니다."
                )
        if follow == "fix_plan":
            check = review_plan(notice_text, assignments or [], confine=confine)
            extra["problem_explanation"] = explain_plan_blockers(check.get("blocked", []))
            first_issue = extra["problem_explanation"]["issues"]
            if first_issue:
                guide["question"] = first_issue[0]["next_action"]
        if follow == "approve_exact_plan":
            preview = review_plan(notice_text, assignments or [], confine=confine)
            if preview["status"] != "awaiting_human_approval":
                return _envelope(
                    "needs_review", 3, next_action="fix_plan",
                    question="계획의 조건이 변경되었습니다. 다시 확인해주세요.",
                    guidance=preview,
                )
            extra["approval_fingerprint"] = plan_fingerprint(preview["plan"])
            extra["approval_fingerprint_purpose"] = (
                "같은 계획인지 비교하는 값이며, 사용자의 실제 승인을 증명하지 않습니다."
            )
        return _envelope(
            guide["status"], step,
            next_action=follow, question=guide["question"], **extra,
        )

    # "start": new local job, never auto-select a file or auto-approve.
    if assignments is None:
        return _envelope(
            "needs_input", 2, next_action="choose_source",
            question="항목별 원본 파일과 출력 파일명, PDF 페이지를 지정해 주세요.",
        )
    preview = review_plan(notice_text, assignments, confine=confine)
    if preview["status"] != "awaiting_human_approval":
        issue_explanation = explain_plan_blockers(preview.get("blocked", []))
        first_issue = issue_explanation["issues"]
        return _envelope(
            "needs_review", 3, next_action="fix_plan",
            question=first_issue[0]["next_action"] if first_issue
                     else "작업 계획에 검토가 필요한 조건이 있습니다.",
            guidance=preview, problem_explanation=issue_explanation,
        )

    current = plan_fingerprint(preview["plan"])
    if not execute or not confirm_execution or not approval_fingerprint:
        return _envelope(
            "awaiting_human_approval", 3, next_action="approve_exact_plan",
            question="입력·출력 경로, PDF 페이지, 자르기 방식을 확인하고 실행을 명확히 승인해주세요.",
            plan_preview=preview["plan"],
            approval_fingerprint=current,
            execution_permitted=False,
        )
    if not isinstance(approval_fingerprint, str) or approval_fingerprint != current:
        return _envelope(
            "plan_changed", 3, next_action="review_changed_plan",
            question="승인 대상 계획이 현재 파일 상태와 일치하지 않습니다. 최신 계획을 다시 승인해주세요.",
            plan_preview=preview["plan"],
            approval_fingerprint=current,
            execution_permitted=False,
        )
    result = jobs.start(
        notice_text, assignments,
        execute=True, confirm_execution=True, confine=confine,
        expected_plan_fingerprint=current,
    )
    if result.get("status") in {"queued", "running", "publishing", "completed"}:
        return _envelope(
            "job_started", 4, next_action="check_job_again",
            question="작업을 시작했습니다. 제공된 job_id로 실제 상태를 확인해주세요.",
            job=result, execution_permitted=True,
        )
    return _envelope(
        "needs_review", 3, next_action="review_changed_plan",
        question="재검증 중 작업이 시작되지 않았습니다. 결과를 확인하고 새 미리보기를 승인해주세요.",
        job=result, execution_permitted=False,
    )


def _no_directory_search(path: str) -> Path:
    """Defensive no-op guard; never called unless a folder was explicitly given."""
    raise ValueError("Directory search must be explicitly authorized")

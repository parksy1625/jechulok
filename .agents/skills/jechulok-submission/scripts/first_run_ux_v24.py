"""JeChulOK v2.4 — human-facing, read-only progress card.

Summarizes an already evaluated assist_submission result; never opens
files, scans paths, stores user data, runs jobs, or changes consent.
No raw notice text, file paths, evidence snippets, identifiers other than
safe 'item_XX' ids, or unsanitized error messages are repeated here.
"""
from __future__ import annotations

from typing import Any

STAGE_LABELS = (
    "공고의 제출 규격 확인",
    "원본 파일을 직접 선택",
    "입력·출력 계획 검토",
    "명시적 승인 후 파일 준비",
    "기술 규격 및 직접 제출 확인",
)
ACTION_HELP = {
    "provide_notice": "공고의 파일 형식·규격 부분을 입력해 주세요.",
    "clarify_notice": "해석하지 못한 공고 조건이 어떤 서류에 적용되는지 직접 확인해 주세요.",
    "choose_source": "필요한 서류마다 사용할 원본을 직접 지정해 주세요. 파일명 후보는 자동 선택하지 않습니다.",
    "fix_plan": "표시된 기술 규격 오류부터 수정하고 새 미리보기를 확인해 주세요.",
    "approve_exact_plan": "입력·출력 경로와 페이지, 자르기 옵션을 모두 확인한 뒤 별도로 실행을 승인해 주세요.",
    "review_changed_plan": "파일 상태나 계획이 변경됐습니다. 다시 미리보고 승인해야 합니다.",
    "check_job_again": "job_id로 처리 상태를 확인해 주세요. 완료 전에는 최종 파일을 확정하지 않습니다.",
    "review_failed_job": "작업 오류를 검토하고 재실행 전에 새 계획을 승인해 주세요.",
    "verify_final_files": "생성된 파일을 직접 선택한 뒤 기술 검증을 진행해 주세요.",
    "choose_final_files": "기술 검증할 최종 파일을 직접 지정해 주세요.",
    "fix_final_files": "최종 파일의 규격 오류를 수정하고 검증을 다시 진행해 주세요.",
    "manual_check_and_submit": "기술 조건 외의 본문·사진·서명을 직접 검토하고 제출처에서 접수 여부를 확인해 주세요.",
    "check_original_content": "규격 이외의 실제 파일 내용과 기관 접수 여부를 직접 확인해 주세요.",
    "provide_job_id": "실행 시 반환된 작업 ID를 지정해 주세요.",
}
APPROVAL_ACTIONS = {"approve_exact_plan", "review_changed_plan"}
MAX_VISIBLE = 12


def progress_view(response: dict[str, Any]) -> dict[str, Any]:
    """Attach deterministic task-oriented UX metadata to one workflow result.

    'progress_percent' is just an interface step indicator (not actual work
    completion or elapsed time). It never says submitted or accepted.
    """
    workflow = response.get("workflow", {})
    step = workflow.get("step")
    action = workflow.get("next_action")
    if type(step) is not int or not 1 <= step <= 5 or action not in ACTION_HELP:
        raise ValueError("Unknown guided workflow stage or action")
    selection = response.get("file_selection") or {}
    items = selection.get("items") or []
    safe_items = []
    for item in items[:MAX_VISIBLE]:
        ident = item.get("item_id")
        fmt = item.get("expected_format")
        if not isinstance(ident, str) or not ident.startswith("item_"):
            continue
        # Labels and original paths may include user content, so exclude.
        safe_items.append({
            "item_id": ident if len(ident) <= 12 else "item_unknown",
            "expected_format": fmt if fmt in {"jpg", "pdf", "png", "webp"} else None,
            "requires_explicit_user_selection": True,
        })
    notice = response.get("notice_explanation") or {}
    blockers = response.get("problem_explanation") or {}
    decisions = []
    if action == "choose_source":
        decisions = safe_items
    blocker_total = (notice.get("issue_count", 0) if action == "clarify_notice"
                     else blockers.get("issue_count", 0) if action == "fix_plan" else 0)
    return {
        "schema": 1,
        "current_stage": step,
        "total_stages": 5,
        "stage_label": STAGE_LABELS[step - 1],
        "progress_percent": (step - 1) * 20,
        "progress_is_only_step_indicator": True,
        "next_action": action,
        "next_step_help": ACTION_HELP[action],
        "outstanding_file_choices": int(selection.get("missing_count", 0))
            if action == "choose_source" else 0,
        "file_choices": decisions,
        "unresolved_notice_or_plan_issues": max(0, int(blocker_total)),
        "requires_separate_human_approval": action in APPROVAL_ACTIONS,
        "institutional_submission_verified": False,
        "data_transmitted": False,
        "telemetry_recorded": False,
        "automatic_file_selection": False,
        "independent_approval_inferred": False,
    }

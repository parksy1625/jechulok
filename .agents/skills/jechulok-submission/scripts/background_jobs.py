"""JeChulOK v1.3: in-memory, cooperative local batch jobs.

One active job per local stdio MCP process. No network, disk job registry,
implicit approvals, persistent resume, or preemptive thread termination.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from secrets import token_urlsafe
from threading import Event, RLock, Thread
from time import monotonic
from typing import Any, Callable

from notice_batch import prepare_batch

MAX_HISTORY = 16
ACTIVE = frozenset({"queued", "running", "cancel_requested"})
FINAL = frozenset({"completed", "failed", "cancelled"})


class LocalJobManager:
    def __init__(self) -> None:
        self._lock = RLock()
        self._jobs: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _view(job: dict[str, Any]) -> dict[str, Any]:
        current = job["status"]
        progress = {
            "type": "live_poll_snapshot",
            "live_streaming": False,
            "phase": current,
            "completed_items": job["completed"] if current not in {"failed", "cancelled"} else 0,
            "total_items": job["total"],
            "percent": round(job["completed"] * 100 / job["total"]) if job["total"] and current not in {"failed", "cancelled"} else 0,
            "current_item_id": job.get("current_item"),
            "note": "동일 로컬 MCP 프로세스에서 get_submission_job을 호출할 때 갱신되는 상태입니다.",
        }
        return {
            "status": current,
            "job_id": job["id"],
            "progress": progress,
            "events": deepcopy(job["events"][-24:]),
            "cancel_requested": job["cancel"].is_set(),
            "result": deepcopy(job.get("result")) if current in FINAL else None,
            "reusable_approval": False,
            "institutional_submission_confirmed": False,
            "limits": "취소는 현재 파일 작업이 끝난 뒤 적용됩니다. MCP 프로세스를 종료하면 작업 조회가 불가능합니다.",
        }

    def start(
        self, notice_text: str, assignments: list[dict[str, Any]],
        *, execute: bool, confirm_execution: bool, confine: Callable[..., Path],
    ) -> dict[str, Any]:
        if type(execute) is not bool or type(confirm_execution) is not bool:
            raise ValueError("execute and confirm_execution must be booleans")
        with self._lock:
            if any(j["status"] in ACTIVE for j in self._jobs.values()):
                return {"status": "busy", "message": "이미 실행 중인 일괄 작업이 있습니다. 완료 또는 취소를 확인하세요."}

        # Both approval flags are required. Without them this is a read-only
        # preview and no thread/job is created.
        preview = prepare_batch(notice_text, assignments, confine=confine)
        if preview["status"] != "planned":
            return preview
        if not execute or not confirm_execution:
            return {
                "status": "needs_confirmation" if execute else "planned",
                "dry_run": True, "plan": preview["plan"],
                "message": "실행 전 정확한 파일 경로·선택 페이지·자르기 방식에 대한 사용자 승인이 필요합니다.",
                "job_started": False,
                "institutional_submission_confirmed": False,
            }
        with self._lock:
            if any(j["status"] in ACTIVE for j in self._jobs.values()):
                return {"status": "busy", "message": "이미 실행 중인 일괄 작업이 있습니다."}
            if len(self._jobs) >= MAX_HISTORY:
                for key in list(self._jobs):
                    if self._jobs[key]["status"] in FINAL:
                        del self._jobs[key]
                        break
            job_id = token_urlsafe(18)
            job: dict[str, Any] = {
                "id": job_id, "status": "queued",
                "total": len(preview["plan"]), "completed": 0,
                "current_item": None,
                "events": [], "result": None, "cancel": Event(),
            }
            self._jobs[job_id] = job
            worker = Thread(
                target=self._work,
                args=(job_id, notice_text, deepcopy(assignments), confine),
                name="jechulok-job-" + job_id[:6], daemon=True,
            )
            worker.start()
            return self._view(job)

    def _work(self, job_id: str, notice_text: str,
              assignments: list[dict[str, Any]], confine: Callable[..., Path]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job["status"] == "queued":
                job["status"] = "running"
            job["events"].append({"event": "job_started", "completed_items": 0})

        def track(message: dict[str, Any]) -> None:
            with self._lock:
                job = self._jobs[job_id]
                if message["event"] == "item_started":
                    job["current_item"] = message["item_id"]
                elif message["event"] == "item_completed":
                    job["current_item"] = None
                    job["completed"] = message["completed_items"]
                job["events"].append({
                    "event": message["event"],
                    "item_id": message.get("item_id"),
                    "completed_items": message["completed_items"],
                })
                job["events"] = job["events"][-32:]

        try:
            result = prepare_batch(
                notice_text, assignments,
                execute=True, confirm_execution=True, confine=confine,
                on_progress=track, should_cancel=self._jobs[job_id]["cancel"].is_set,
            )
        except Exception:
            # Do not expose filesystem exception messages to polling clients.
            result = {
                "status": "error",
                "message": "예기치 않은 실행 오류가 발생했습니다. 작업 폴더의 출력 파일을 직접 확인하세요.",
                "institutional_submission_confirmed": False,
            }
        with self._lock:
            job = self._jobs[job_id]
            job["result"] = result
            job["current_item"] = None
            if result["status"] == "pass":
                job["status"] = "completed"
                job["completed"] = job["total"]
            elif result["status"] == "cancelled":
                job["status"] = "cancelled"
                job["completed"] = 0
            else:
                job["status"] = "failed"
                job["completed"] = 0
            job["events"].append({
                "event": "job_finished", "result_status": result["status"],
                "completed_items": job["completed"],
            })

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return {
                    "status": "not_found",
                    "message": "이 로컬 MCP 프로세스에 해당 작업이 없습니다.",
                    "reusable_approval": False,
                }
            return self._view(job)

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return {"status": "not_found", "message": "이 로컬 MCP 프로세스에 해당 작업이 없습니다."}
            if job["status"] in FINAL:
                return self._view(job)
            job["cancel"].set()
            job["status"] = "cancel_requested"
            job["events"].append({
                "event": "cancel_requested",
                "message": "현재 파일 처리가 끝난 후 중단 및 롤백합니다.",
            })
            return self._view(job)


manager = LocalJobManager()

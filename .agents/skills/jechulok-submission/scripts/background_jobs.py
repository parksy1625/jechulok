"""JeChulOK v1.5 local batch manager with optional durable, fail-closed recovery.

The old LocalJobManager() API stays transient for v1.3 compatibility.
MCP uses LocalJobManager(journal_root=...) so approved jobs are staged and
journaled. Interrupted jobs NEVER auto-resume or auto-delete final files.
"""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
from secrets import token_urlsafe
from threading import Event, RLock, Thread
from typing import Any, Callable

import jechulok as core
from job_journal import JobJournal, eligible_stage, pid_is_alive, stage_for_output
from job_lock import FolderWriteLock
from notice_batch import prepare_batch

MAX_HISTORY = 16
ACTIVE = frozenset({"queued", "running", "cancel_requested", "publishing"})
FINAL = frozenset({"completed", "failed", "cancelled"})


class LocalJobManager:
    def __init__(self, journal_root: Path | None = None) -> None:
        self._lock = RLock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._journal = JobJournal(journal_root) if journal_root is not None else None
        self._session = token_urlsafe(12)
        self._active_lease: FolderWriteLock | None = None
        self._recovered: dict[str, dict[str, Any]] = {}
        if self._journal is not None:
            self._recovered = {r["job_id"]: r for r in self._journal.scan()}

    @staticmethod
    def _view(job: dict[str, Any]) -> dict[str, Any]:
        current = job["status"]
        progress = {
            "type": "live_poll_snapshot",
            "live_streaming": False,
            "phase": current,
            "completed_items": job["completed"] if current not in {"failed", "cancelled"} else 0,
            "total_items": job["total"],
            "percent": round(job["completed"] * 100 / job["total"])
                       if job["total"] and current not in {"failed", "cancelled"} else 0,
            "current_item_id": job.get("current_item"),
            "note": "동일 로컬 MCP 프로세스에서 조회할 때 갱신되는 파일 단위 상태입니다.",
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
            "limits": "취소는 현재 파일 처리 후 적용됩니다. 서버가 종료되면 실행은 복구되지 않습니다.",
        }

    @staticmethod
    def _recovered_view(record: dict[str, Any]) -> dict[str, Any]:
        old = record["status"]
        interrupted = old in ACTIVE
        alive = pid_is_alive(record.get("pid")) if interrupted else False
        stages = [item for item in record["staging"]
                  if isinstance(item, dict) and isinstance(item.get("stage"), str)]
        outputs = [p for p in record["outputs"] if isinstance(p, str)]
        final_present = sum(Path(p).exists() for p in outputs)
        stage_present = sum(Path(item["stage"]).exists() for item in stages)
        return {
            "status": "possibly_active" if interrupted and alive else
                      "interrupted" if interrupted else old,
            "job_id": record["job_id"],
            "recovered_from_disk": True,
            "previous_status": old,
            "completed_items_before_interruption": record.get("completed", 0),
            "total_items": record.get("total", 0),
            "staging_files": [
                {"item_id": item.get("item_id"),
                 "filename": Path(item["stage"]).name,
                 "exists": Path(item["stage"]).exists()}
                for item in stages
            ],
            "output_files": [
                {"filename": Path(p).name, "exists": Path(p).exists()}
                for p in outputs
            ],
            "staging_file_count": stage_present,
            "final_output_count": final_present,
            "possibly_active_process": alive,
            "next_action": (
                "다른 서버가 실행 중일 수 있습니다. 해당 서버 상태를 먼저 확인하세요."
                if alive else
                "남은 최종 파일을 직접 검토한 후 임시 파일 정리 미리보기를 요청하세요."
            ) if interrupted else "기존 결과 파일을 기술 조건에 따라 다시 확인하세요.",
            "requires_manual_review": interrupted,
            "reusable_approval": False,
            "institutional_submission_confirmed": False,
            "message": ("기록은 복원됐지만 작업은 재실행되지 않았습니다. "
                        "임시 파일과 최종 출력 파일을 확인한 후 복구 확인을 진행하세요.")
                       if interrupted else "이전 작업 상태 기록입니다. 결과 파일은 현재 상태로 재검증해야 합니다.",
        }

    def _persist(self, job: dict[str, Any]) -> None:
        if self._journal is None:
            return
        self._journal.write({
            "schema": 1,
            "job_id": job["id"],
            "status": job["status"],
            "total": job["total"],
            "completed": job["completed"],
            "pid": os.getpid(),
            "session": self._session,
            "staging": deepcopy(job.get("staging", [])),
            "outputs": list(job.get("outputs", [])),
        })

    def _refresh_recovered(self) -> None:
        # Avoid stale snapshots when another MCP process writes a record.
        if self._journal is not None:
            self._recovered = {r["job_id"]: r for r in self._journal.scan()}

    def _has_unresolved_recovery(self) -> bool:
        return any(
            r["status"] in ACTIVE and r["job_id"] not in self._jobs
            for r in self._recovered.values()
        )

    def start(
        self, notice_text: str, assignments: list[dict[str, Any]],
        *, execute: bool, confirm_execution: bool, confine: Callable[..., Path],
    ) -> dict[str, Any]:
        if type(execute) is not bool or type(confirm_execution) is not bool:
            raise ValueError("execute and confirm_execution must be booleans")
        with self._lock:
            if any(j["status"] in ACTIVE for j in self._jobs.values()):
                return {"status": "busy", "message": "이미 실행 중인 일괄 작업이 있습니다."}

        preview = prepare_batch(notice_text, assignments, confine=confine)
        if preview["status"] != "planned":
            return preview
        if not execute or not confirm_execution:
            return {
                "status": "needs_confirmation" if execute else "planned",
                "dry_run": True, "plan": preview["plan"],
                "message": "정확한 입력/출력 경로·페이지 선택을 확인하고 별도 승인을 받아야 합니다.",
                "job_started": False, "institutional_submission_confirmed": False,
            }
        with self._lock:
            if any(j["status"] in ACTIVE for j in self._jobs.values()):
                return {"status": "busy", "message": "이미 실행 중인 일괄 작업이 있습니다."}
            lease = None
            try:
                if self._journal is not None:
                    lease = FolderWriteLock.acquire(self._journal)
                    if lease is None:
                        return {
                            "status": "busy", "code": "folder_writer_active",
                            "message": "동일 작업 폴더에서 다른 MCP 프로세스가 작업 중입니다.",
                            "job_started": False,
                        }
                    # The OS lock is held across this scan AND all writes.
                    self._refresh_recovered()
                if self._has_unresolved_recovery():
                    return {
                        "status": "recovery_required",
                        "message": "이전에 중단된 작업의 출력을 확인하고 복구 결정을 마친 뒤 새 작업을 시작하세요.",
                        "job_started": False, "reusable_approval": False,
                        "pending_job_count": sum(
                            r["status"] in ACTIVE for r in self._recovered.values()
                        ),
                    }
                if len(self._jobs) >= MAX_HISTORY:
                    for key in list(self._jobs):
                        if self._jobs[key]["status"] in FINAL:
                            del self._jobs[key]
                            break
                if len(self._jobs) >= MAX_HISTORY:
                    return {"status": "busy", "message": "최근 작업 기록 공간이 가득 찼습니다."}
                job_id = token_urlsafe(18)
                staging: list[dict[str, str]] = []
                if self._journal is not None:
                    for plan in preview["plan"]:
                        final = plan.get("output_path")
                        if final:
                            target = Path(final)
                            staged = stage_for_output(target, job_id, plan["item_id"])
                            confine(str(staged), for_output=True)
                            staging.append({
                                "item_id": plan["item_id"],
                                "stage": str(staged), "final": str(target),
                            })
                job: dict[str, Any] = {
                    "id": job_id, "status": "queued",
                    "total": len(preview["plan"]), "completed": 0,
                    "current_item": None, "events": [], "result": None,
                    "cancel": Event(), "staging": staging,
                    "outputs": [
                        p["output_path"] for p in preview["plan"]
                        if p.get("output_path")
                    ],
                }
                # The durable journal must be written BEFORE the worker starts.
                self._persist(job)
                self._jobs[job_id] = job
                worker = Thread(
                    target=self._work,
                    args=(job_id, notice_text, deepcopy(assignments), confine),
                    name="jechulok-job-" + job_id[:6], daemon=True,
                )
                self._active_lease = lease
                try:
                    worker.start()
                except BaseException:
                    self._jobs.pop(job_id, None)
                    self._active_lease = None
                    raise
                lease = None  # Ownership moved to _work's finally block.
                return self._view(job)
            finally:
                # Preflight/recovery refusals and thread startup failures
                # release immediately; they never strand a writer lease.
                if lease is not None:
                    lease.release()


    def _cleanup_stages(self, staging: list[dict[str, str]]) -> None:
        # Staging paths are random and exclusive; never delete a final path.
        for item in reversed(staging):
            path = Path(item["stage"])
            if eligible_stage(path, item["stage"], item["job_id"]):
                if path.exists():
                    path.unlink()

    def _publish(
        self, job: dict[str, Any], staged_result: dict[str, Any],
        confine: Callable[..., Path],
    ) -> dict[str, Any]:
        staging = job["staging"]
        mappings = {item["item_id"]: item for item in staging}
        published: list[tuple[Path, Path, tuple[int, int, int, int]]] = []
        try:
            with self._lock:
                if job["cancel"].is_set():
                    raise InterruptedError("cancelled before publish")
                job["status"] = "publishing"
                self._persist(job)

            # Hard link is exclusive (never replaces a user's output). Stage
            # and final are in the same directory/filesystem.
            for result in staged_result["results"]:
                item_id = result["item_id"]
                if item_id not in mappings:
                    continue   # verified original PDF: no new output
                if job["cancel"].is_set():
                    raise InterruptedError("cancelled while publishing")
                item = mappings[item_id]
                stage = confine(item["stage"])
                final = confine(item["final"], for_output=True)
                if stage != Path(item["stage"]) or final != Path(item["final"]):
                    raise ValueError("Staging path changed")
                if not eligible_stage(stage, item["stage"], job["id"]):
                    raise ValueError("Invalid staging file")
                os.link(str(stage), str(final))  # O_EXCL semantics.
                identity = final.stat()
                published.append((stage, final, (identity.st_dev, identity.st_ino,
                                                  identity.st_size, identity.st_mtime_ns)))
                # Reinspect the final filename, not the stage name.
                meta = core.info_for(core.safe_file(str(final)))
                spec = result["verification"]["checks"]
                # Re-run all explicit rule checks from stage verification's expected values.
                expected = {c["rule"]: c["expected"] for c in spec}
                verified = core.evaluation(
                    meta,
                    expected_format=expected.get("format", meta["format"]),
                    max_kb=expected.get("max_kb"),
                    width=expected.get("width"),
                    height=expected.get("height"),
                    max_pages=expected.get("max_pages"),
                )
                if verified["status"] != "pass":
                    raise ValueError("Published output failed independent verification")
                result["output"] = str(final)
                result["verification"] = verified
                if isinstance(result.get("preparation"), dict):
                    result["preparation"]["output"] = str(final)
                    result["preparation"]["report"] = verified
                for info in staged_result["summary"]["items"]:
                    if info["item_id"] == item_id:
                        info["output_path"] = str(final)

            if job["cancel"].is_set():
                raise InterruptedError("cancelled after publishing")
            # Files are committed. Only remove owned staging hard links.
            for stage, final, identity in published:
                if eligible_stage(stage, str(stage), job["id"]):
                    stage.unlink(missing_ok=True)
            return staged_result
        except Exception as exc:
            # Do not erase any output replaced/changed by another actor.
            unresolved: list[str] = []
            for stage, final, identity in reversed(published):
                try:
                    stat = final.stat(follow_symlinks=False)
                    observed = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
                    if not final.is_symlink() and stage.is_file() and stage.samefile(final) and observed == identity:
                        final.unlink()
                    else:
                        unresolved.append(final.name)
                except FileNotFoundError:
                    pass
                except OSError:
                    unresolved.append(final.name)
            for item in staging:
                stage = Path(item["stage"])
                if eligible_stage(stage, item["stage"], job["id"]) and stage.is_file():
                    stage.unlink(missing_ok=True)
            interrupted = isinstance(exc, InterruptedError)
            return {
                "status": "cancelled" if interrupted else "error",
                "message": "일괄 작업 게시가 중단되었습니다. 최종 출력 경로를 직접 확인하세요.",
                "results": [], "rolled_back": [], "manual_review_required": True,
                "remaining_output_names": unresolved,
                "retry_guidance": {"automatic_retry": False, "reuse_prior_approval": False},
                "institutional_submission_confirmed": False,
            }

    def _work(self, job_id: str, notice_text: str,
              assignments: list[dict[str, Any]], confine: Callable[..., Path]) -> None:
        try:
            self._execute_work(job_id, notice_text, assignments, confine)
        finally:
            with self._lock:
                if self._active_lease is not None:
                    self._active_lease.release()
                    self._active_lease = None

    def _execute_work(self, job_id: str, notice_text: str,
                      assignments: list[dict[str, Any]], confine: Callable[..., Path]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job["status"] == "queued":
                job["status"] = "running"
            job["events"].append({"event": "job_started", "completed_items": 0})
            try:
                self._persist(job)
            except (OSError, ValueError):
                job["status"] = "failed"
                job["result"] = {"status": "error", "message": "작업 기록을 저장하지 못해 파일 처리를 시작하지 않았습니다."}
                return

        def track(message: dict[str, Any]) -> None:
            with self._lock:
                j = self._jobs[job_id]
                if message["event"] == "item_started":
                    j["current_item"] = message["item_id"]
                elif message["event"] == "item_completed":
                    j["current_item"] = None
                    j["completed"] = message["completed_items"]
                j["events"].append({
                    "event": message["event"],
                    "item_id": message.get("item_id"),
                    "completed_items": message["completed_items"],
                })
                j["events"] = j["events"][-32:]
                self._persist(j)

        # For durable jobs, prepare ONLY on exclusive stage filenames until
        # the batch is entirely valid. v1.3 transient jobs remain unchanged.
        if self._journal is not None:
            paths = {x["item_id"]: x["stage"] for x in job["staging"]}
            for item in assignments:
                if item["item_id"] in paths:
                    item["output_path"] = paths[item["item_id"]]

        try:
            result = prepare_batch(
                notice_text, assignments, execute=True,
                confirm_execution=True, confine=confine,
                on_progress=track, should_cancel=job["cancel"].is_set,
            )
            if self._journal is not None:
                if result["status"] == "pass":
                    result = self._publish(job, result, confine)
                else:
                    self._cleanup_stages([
                        {**item, "job_id": job_id} for item in job["staging"]
                    ])
        except Exception:
            # An unexpected exception must not be treated as a safe completed
            # rollback; the disk state needs explicit manual inspection.
            result = {
                "status": "error",
                "message": "예기치 않은 실행 오류입니다. 이전 출력과 임시 파일을 직접 확인하세요.",
                "manual_review_required": True,
                "institutional_submission_confirmed": False,
            }
        with self._lock:
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
            try:
                self._persist(job)
            except (OSError, ValueError):
                job["status"] = "failed"
                job["result"] = {
                    "status": "error",
                    "message": "실행 결과를 로컬 기록으로 확정하지 못했습니다. 출력 파일을 확인하세요.",
                    "manual_review_required": True,
                }

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                return self._view(job)
            self._refresh_recovered()
            record = self._recovered.get(job_id)
            if record is not None:
                return self._recovered_view(record)
            return {"status": "not_found", "message": "이 로컬 MCP 환경에 해당 작업이 없습니다.",
                    "reusable_approval": False}

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                if job_id in self._recovered:
                    return {
                        "status": "recovery_required",
                        "message": "재시작한 이전 작업은 취소할 수 없습니다. 복구 검토를 진행하세요.",
                        "reusable_approval": False,
                    }
                return {"status": "not_found", "message": "이 로컬 MCP 프로세스에 해당 작업이 없습니다."}
            if job["status"] in FINAL:
                return self._view(job)
            job["cancel"].set()
            job["status"] = "cancel_requested"
            job["events"].append({
                "event": "cancel_requested",
                "message": "현재 파일 처리가 끝난 후 중단 및 롤백합니다.",
            })
            try:
                self._persist(job)
            except (OSError, ValueError):
                # Cancellation is still set in memory, but durable update failed.
                return {"status": "cancel_requested", "durability_warning": True,
                        "message": "취소는 요청되었으나 기록 저장에 실패했습니다. 최종 상태를 확인하세요."}
            return self._view(job)

    def review_recovery(self) -> dict[str, Any]:
        """Read-only ordered recovery checklist; no destructive side effects."""
        with self._lock:
            self._refresh_recovered()
            # A live job owned by this MCP instance is not a crash recovery.
            # Other processes' records may still need attention.
            own_ids = set(self._jobs)
            jobs = [
                self._recovered_view(x) for x in self._recovered.values()
                if x["status"] in ACTIVE and x["job_id"] not in own_ids
            ]
            return {
                "status": "recovery_required" if jobs else "clear",
                "interrupted_jobs": jobs,
                "interrupted_job_count": len(jobs),
                "recommended_action": (
                    "최종 출력 파일을 직접 확인하고, 해당 작업의 resolve_interrupted_submission_job "
                    "미리보기를 호출하세요."
                    if jobs else "복구 대기 기록이 없습니다. 새 작업은 미리보기부터 진행하세요."
                ),
                "auto_resume": False, "auto_delete": False,
                "message": "임시 파일은 명시적으로 복구를 승인하기 전까지 삭제하지 않습니다.",
            }

    def resolve_recovery(
        self, job_id: str, *,
        cleanup_staging: bool = False,
        confirm_cleanup: bool = False,
        checked_final_outputs: bool = False,
        confine: Callable[..., Path],
    ) -> dict[str, Any]:
        with self._lock:
            self._refresh_recovered()
            if not (cleanup_staging and confirm_cleanup and checked_final_outputs):
                return self._resolve_recovery_locked(
                    job_id, cleanup_staging=cleanup_staging,
                    confirm_cleanup=confirm_cleanup,
                    checked_final_outputs=checked_final_outputs, confine=confine,
                )
            if self._journal is None:
                return {"status": "error", "message": "복구 기록 저장소가 없습니다."}
            lease = FolderWriteLock.acquire(self._journal)
            if lease is None:
                return {
                    "status": "busy", "code": "folder_writer_active",
                    "message": "다른 MCP 서버가 같은 폴더에서 작업 중입니다. 정리하지 않았습니다.",
                    "final_outputs_will_be_deleted": False,
                }
            try:
                # The journal might have been updated by the previous owner
                # since our initial read; recheck after obtaining the OS lock.
                self._refresh_recovered()
                return self._resolve_recovery_locked(
                    job_id, cleanup_staging=cleanup_staging,
                    confirm_cleanup=confirm_cleanup,
                    checked_final_outputs=checked_final_outputs, confine=confine,
                )
            finally:
                lease.release()

    def _resolve_recovery_locked(
        self, job_id: str, *,
        cleanup_staging: bool, confirm_cleanup: bool,
        checked_final_outputs: bool, confine: Callable[..., Path],
    ) -> dict[str, Any]:
        with self._lock:
            record = self._recovered.get(job_id)
            if record is None or record["status"] not in ACTIVE:
                return {"status": "not_found", "message": "복구 대상 중단 기록이 없습니다."}
            previous = self._recovered_view(record)
            if not cleanup_staging or not confirm_cleanup or not checked_final_outputs:
                return {
                    "status": "needs_confirmation",
                    "dry_run": True, "recovery": previous,
                    "message": "임시 파일 삭제와 최종 출력 경로 검토를 각각 명시적으로 승인해야 합니다.",
                    "final_outputs_will_be_deleted": False,
                }
            # Another server process might still be running this job.
            if pid_is_alive(record.get("pid")):
                return {
                    "status": "possibly_active",
                    "message": "기존 서버 프로세스가 실행 중일 수 있습니다. 강제로 정리하지 않습니다.",
                    "final_outputs_will_be_deleted": False,
                }
            if self._journal is None:
                return {"status": "error", "message": "작업 기록 디렉터리를 사용할 수 없습니다."}

            # Validate *all* journal paths and ensure stages precisely match
            # their approved final filenames BEFORE unlinking anything.
            stages: list[Path] = []
            for item in record["staging"]:
                if not isinstance(item, dict) or not all(
                    isinstance(item.get(key), str) for key in ("item_id", "stage", "final")
                ):
                    return {"status": "needs_review", "message": "작업 기록 형식이 올바르지 않습니다."}
                final = Path(item["final"])
                stage = Path(item["stage"])
                if stage != stage_for_output(final, job_id, item["item_id"]):
                    return {"status": "needs_review", "message": "임시 경로 서명이 일치하지 않습니다."}
                if not eligible_stage(stage, item["stage"], job_id):
                    return {"status": "needs_review", "message": "임시 파일의 안전성을 확인할 수 없습니다."}
                try:
                    if stage.exists():
                        if confine(str(stage)) != stage:
                            raise ValueError("Path mismatch")
                    else:
                        if confine(str(stage), for_output=True) != stage:
                            raise ValueError("Path mismatch")
                except (OSError, ValueError):
                    return {"status": "needs_review", "message": "허용된 경로 밖의 임시 파일은 처리할 수 없습니다."}
                stages.append(stage)

            removed: list[str] = []
            try:
                for stage in stages:
                    if stage.is_file():
                        stage.unlink()
                        removed.append(stage.name)
            except OSError:
                return {
                    "status": "needs_review", "message": "일부 임시 파일의 삭제에 실패했습니다. 수동 확인이 필요합니다.",
                    "removed_stage_filenames": removed, "final_outputs_will_be_deleted": False,
                }
            updated = dict(record, status="reviewed", completed=0)
            try:
                self._journal.write(updated)
            except (OSError, ValueError):
                return {"status": "needs_review", "message": "임시 파일 정리 후 기록 상태 저장에 실패했습니다."}
            self._recovered[job_id] = updated
            return {
                "status": "reviewed", "job_id": job_id,
                "removed_stage_filenames": removed,
                "final_outputs_will_be_deleted": False,
                "reusable_approval": False,
                "next_step": "최종 파일을 직접 확인하고, 새 작업은 새 미리보기 및 승인 후 시작하세요.",
            }


manager = LocalJobManager()

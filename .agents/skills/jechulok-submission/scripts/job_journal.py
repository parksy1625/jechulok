"""Private, local crash journal for v1.4 background jobs.

Stores only job states and approved output/staging paths, never notices,
file contents, raw source paths, or reusable approvals. No auto-resume.
"""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
from secrets import token_urlsafe
from stat import S_ISREG
from typing import Any

SCHEMA = 1
MAX_RECORD_BYTES = 32 * 1024
MAX_RECORDS = 32
VALID_ID = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
RUNNING = frozenset({"queued", "running", "cancel_requested", "publishing"})


def _id(value: str) -> str:
    if not isinstance(value, str) or not 12 <= len(value) <= 60 or any(c not in VALID_ID for c in value):
        raise ValueError("Invalid job identifier")
    return value


class JobJournal:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).absolute()
        if self.root.exists():
            self._safe_directory()

    def _safe_directory(self) -> None:
        if self.root.is_symlink() or not self.root.is_dir() or self.root.resolve() != self.root:
            raise ValueError("Job journal directory cannot be a symlink or alias")
        # A directory created by JeChulOK has mode 0700. Fail closed on
        # world/group-readable records on POSIX; Windows uses ACLs.
        if os.name != "nt" and (self.root.stat().st_mode & 0o077):
            raise ValueError("Job journal directory permissions are too broad")

    def _ensure_directory(self) -> None:
        if not self.root.exists():
            self.root.mkdir(mode=0o700, parents=False, exist_ok=False)
        self._safe_directory()

    def _path(self, job_id: str) -> Path:
        return self.root / (_id(job_id) + ".json")

    def write(self, record: dict[str, Any]) -> None:
        self._ensure_directory()
        path = self._path(record["job_id"])
        encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_RECORD_BYTES:
            raise ValueError("Job record exceeds size limit")
        temp = self.root / (_id(record["job_id"]) + "." + token_urlsafe(7) + ".tmp")
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(encoded)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(str(temp), str(path))
        finally:
            temp.unlink(missing_ok=True)

    def read(self, job_id: str) -> dict[str, Any] | None:
        self._safe_directory() if self.root.exists() else None
        path = self._path(job_id)
        if path.is_symlink() or not path.is_file():
            return None
        try:
            if path.stat().st_size > MAX_RECORD_BYTES:
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError, UnicodeError):
            return None
        if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("job_id") != job_id:
            return None
        if data.get("status") not in RUNNING | {"completed", "failed", "cancelled", "reviewed"}:
            return None
        if not isinstance(data.get("staging"), list) or not isinstance(data.get("outputs"), list):
            return None
        return data

    def scan(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        self._safe_directory()
        result: list[dict[str, Any]] = []
        for path in sorted(self.root.iterdir(), key=lambda p: p.name)[:MAX_RECORDS * 5]:
            if path.suffix != ".json" or path.is_symlink():
                continue
            job_id = path.stem
            try:
                record = self.read(job_id)
            except ValueError:
                continue
            if record:
                result.append(record)
                if len(result) >= MAX_RECORDS:
                    break
        return result


def stage_for_output(output: Path, job_id: str, item_id: str) -> Path:
    """Same-directory temporary filename, with random job ID and final extension."""
    _id(job_id)
    if not item_id.startswith("item_") or len(item_id) > 20:
        raise ValueError("Invalid item identifier")
    return output.with_name("." + output.stem + ".jechulok-" + job_id + "-" + item_id + output.suffix)


def eligible_stage(path: Path, expected: str, job_id: str) -> bool:
    """Never delete user output or symlink; only a journal-named stage."""
    try:
        candidate = Path(expected)
        if str(path) != expected or not path.is_absolute():
            return False
        if path.is_symlink() or path.resolve(strict=False) != path:
            return False
        if not path.name.startswith(".") or ".jechulok-" + job_id + "-" not in path.name:
            return False
        if path.is_file():
            stat = path.stat(follow_symlinks=False)
            return S_ISREG(stat.st_mode)
        return not path.exists()
    except (OSError, ValueError):
        return False


def pid_is_alive(pid: Any) -> bool:
    """Read-only PID liveness probe. Windows MUST NOT use os.kill(pid, 0)."""
    if type(pid) is not int or pid <= 0:
        return True
    if os.name == "nt":
        # On Windows os.kill(pid, 0) can generate a console interrupt:
        # it is NOT a harmless POSIX-style liveness check. Use kernel32.
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            # ERROR_INVALID_PARAMETER: PID doesn't exist. Access denied or
            # any other error must be conservatively treated as active.
            return False if ctypes.get_last_error() == 87 else True
        try:
            exit_code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # Only POSIX treats signal 0 as a non-signalling probe.
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        return False if exc.errno == errno.ESRCH else True
    return True

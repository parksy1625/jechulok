"""Cross-process, local-only advisory writer lock for JeChulOK approved jobs.

The OS releases the lock when its owning process terminates. Never infer
job completion or delete files from lock availability alone: read the
crash journal separately. Do not remove the lock file while in use.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path

from job_journal import JobJournal


class FolderWriteLock:
    def __init__(self, fd: int, path: Path) -> None:
        self._fd = fd
        self.path = path

    @classmethod
    def acquire(cls, journal: JobJournal) -> "FolderWriteLock | None":
        # Only an explicitly approved execution/recovery creates this folder.
        journal._ensure_directory()
        path = journal.root / ".writer.lock"
        if path.is_symlink():
            raise ValueError("Refusing symlinked writer lock")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(path), flags, 0o600)
        try:
            if os.name == "nt":
                # msvcrt locking operates on bytes at the current file offset.
                # A permanent one-byte lock file is stable across restarts.
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"1")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # File descriptor must reference the same visible lock file;
            # fail closed if another actor replaced it concurrently.
            if path.is_symlink() or os.stat(path).st_ino != os.fstat(fd).st_ino:
                raise ValueError("Writer lock was replaced while acquiring")
            return cls(fd, path)
        except OSError as exc:
            os.close(fd)
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK} or (
                getattr(exc, "winerror", None) in {33, 36}
            ):
                return None
            raise
        except BaseException:
            os.close(fd)
            raise

    def release(self) -> None:
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def __enter__(self) -> "FolderWriteLock":
        return self

    def __exit__(self, *args: object) -> None:
        self.release()

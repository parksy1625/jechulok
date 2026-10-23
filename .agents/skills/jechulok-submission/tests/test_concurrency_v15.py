"""v1.5 tests: OS-enforced writer exclusivity, crash-safe unlock, recovery UX."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import background_jobs
import job_journal
from job_lock import FolderWriteLock
import mcp_server as server
import notice_batch

NOTICE = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"


class MultiProcessLockTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name).resolve()
        self.root_env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.root_env.start()
        self.journal_dir = self.root / ".jechulok-jobs"
        self.photo = self.root / "photo.png"
        Image.new("RGB", (640, 480), "white").save(self.photo)
        self.pdf = self.root / "resume.pdf"
        w = PdfWriter()
        for _ in range(5):
            w.add_blank_page(width=200, height=300)
        with self.pdf.open("wb") as f:
            w.write(f)
        self.assignments = [
            {"item_id": "item_01", "input_path": str(self.photo),
             "output_path": str(self.root / "ready.jpg")},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.root / "ready.pdf"), "pages_to_extract": "1-3"},
        ]

    def tearDown(self):
        self.root_env.stop()
        self.folder.cleanup()

    def test_read_only_preview_does_not_create_a_lockfile(self):
        manager = background_jobs.LocalJobManager(journal_root=self.journal_dir)
        preview = manager.start(
            NOTICE, self.assignments, execute=False,
            confirm_execution=False, confine=server._confined,
        )
        self.assertEqual(preview["status"], "planned")
        self.assertFalse(self.journal_dir.exists())

    def test_second_process_cannot_take_lock_and_exit_releases_it(self):
        code = (
            "import sys;from pathlib import Path;"
            f"sys.path.insert(0,{str(ROOT / 'scripts')!r});"
            "from job_lock import FolderWriteLock;"
            "from job_journal import JobJournal;"
            "lock=FolderWriteLock.acquire(JobJournal(Path(sys.argv[1])));"
            "print('LOCKED' if lock else 'BUSY',flush=True);"
            "sys.stdin.readline();"
            "lock.release() if lock else None"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", code, str(self.journal_dir)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), "LOCKED")
            holder = job_journal.JobJournal(self.journal_dir)
            self.assertIsNone(FolderWriteLock.acquire(holder))
            # A second MCP server in the same working directory refuses
            # approved execution without creating a job record.
            manager = background_jobs.LocalJobManager(journal_root=self.journal_dir)
            result = manager.start(
                NOTICE, self.assignments, execute=True,
                confirm_execution=True, confine=server._confined,
            )
            self.assertEqual(result["status"], "busy", result)
            self.assertEqual(result["code"], "folder_writer_active")
            self.assertFalse((self.root / "ready.jpg").exists())
            self.assertFalse(list(self.journal_dir.glob("*.json")))
        finally:
            if proc.stdin:
                proc.stdin.write("\n")
                proc.stdin.flush()
                proc.stdin.close()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            if proc.stdout: proc.stdout.close()
            if proc.stderr: proc.stderr.close()
        self.assertEqual(proc.returncode, 0)
        new_lease = FolderWriteLock.acquire(job_journal.JobJournal(self.journal_dir))
        self.assertIsNotNone(new_lease)
        new_lease.release()

    def test_os_releases_writer_lock_when_owning_process_crashes(self):
        code = (
            "import os,sys;from pathlib import Path;"
            f"sys.path.insert(0,{str(ROOT / 'scripts')!r});"
            "from job_lock import FolderWriteLock;"
            "from job_journal import JobJournal;"
            "lock=FolderWriteLock.acquire(JobJournal(Path(sys.argv[1])));"
            "print('LOCKED' if lock else 'BUSY',flush=True);"
            "os._exit(0)"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code, str(self.journal_dir)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("LOCKED", proc.stdout)
        lease = FolderWriteLock.acquire(job_journal.JobJournal(self.journal_dir))
        self.assertIsNotNone(lease)
        lease.release()

    def test_recovery_cleanup_refuses_when_other_process_holds_lock(self):
        journal = job_journal.JobJournal(self.journal_dir)
        job_id = "TestInterruptedJob_1234"
        stage = job_journal.stage_for_output(self.root / "ready.jpg", job_id, "item_01")
        stage.write_bytes(b"temporary work")
        journal.write({
            "schema": 1, "job_id": job_id, "status": "running",
            "total": 1, "completed": 0, "pid": 999999999,
            "staging": [{"item_id": "item_01", "stage": str(stage),
                         "final": str(self.root / "ready.jpg")}],
            "outputs": [str(self.root / "ready.jpg")],
        })
        manager = background_jobs.LocalJobManager(journal_root=self.journal_dir)
        with FolderWriteLock.acquire(journal):
            blocked = manager.resolve_recovery(
                job_id, cleanup_staging=True, confirm_cleanup=True,
                checked_final_outputs=True, confine=server._confined,
            )
            self.assertEqual(blocked["status"], "busy")
            self.assertTrue(stage.exists())
        accepted = manager.resolve_recovery(
            job_id, cleanup_staging=True, confirm_cleanup=True,
            checked_final_outputs=True, confine=server._confined,
        )
        self.assertEqual(accepted["status"], "reviewed", accepted)
        self.assertFalse(stage.exists())

    def test_live_worker_holds_lease_until_terminal_and_releases_on_cancel(self):
        owner = background_jobs.LocalJobManager(journal_root=self.journal_dir)
        another = background_jobs.LocalJobManager(journal_root=self.journal_dir)
        entered, resume = threading.Event(), threading.Event()
        original = notice_batch.core.prepare_pdf

        def slow_pdf(source, opts):
            entered.set()
            if not resume.wait(8):
                raise ValueError("test PDF gate expired")
            return original(source, opts)

        with patch.object(notice_batch.core, "prepare_pdf", side_effect=slow_pdf):
            first = owner.start(NOTICE, self.assignments, execute=True,
                                confirm_execution=True, confine=server._confined)
            self.assertIn(first["status"], {"queued", "running"})
            try:
                self.assertTrue(entered.wait(8))
                blocked = another.start(
                    NOTICE, self.assignments, execute=True,
                    confirm_execution=True, confine=server._confined,
                )
                self.assertEqual(blocked["status"], "busy")
                self.assertEqual(blocked["code"], "folder_writer_active")
                requested = owner.cancel(first["job_id"])
                self.assertEqual(requested["status"], "cancel_requested")
            finally:
                resume.set()
            deadline = time.monotonic() + 12
            while owner.get(first["job_id"])["status"] not in background_jobs.FINAL:
                self.assertLess(time.monotonic(), deadline, "worker did not terminate")
                time.sleep(.025)
        final = owner.get(first["job_id"])
        self.assertEqual(final["status"], "cancelled", final)
        self.assertFalse((self.root / "ready.jpg").exists())
        self.assertFalse((self.root / "ready.pdf").exists())
        # Other process now observes durable cancelled record, not an
        # indefinitely held writer lock, and can start a fresh approved job.
        again = another.start(
            NOTICE, self.assignments, execute=True,
            confirm_execution=True, confine=server._confined,
        )
        self.assertIn(again["status"], {"queued", "running", "completed"}, again)
        # Test cleanup must never race a still-running writer, especially on
        # Windows where opening lock files prevents directory removal.
        until = time.monotonic() + 12
        while another.get(again["job_id"])["status"] not in background_jobs.FINAL:
            self.assertLess(time.monotonic(), until, "second worker did not terminate")
            time.sleep(.025)
        self.assertEqual(another.get(again["job_id"])["status"], "completed")

    def test_many_completed_records_never_hide_an_interrupted_job(self):
        journal = job_journal.JobJournal(self.journal_dir)
        for n in range(40):
            journal.write({
                "schema": 1, "job_id": f"COMPLETED_JOB_{n:04d}_12345678",
                "status": "completed", "completed": 1, "total": 1,
                "pid": 999999999, "staging": [], "outputs": [],
            })
        active_id = "ZZ_INTERRUPTED_987654321"
        journal.write({
            "schema": 1, "job_id": active_id,
            "status": "running", "completed": 0, "total": 1,
            "pid": 999999999, "staging": [], "outputs": [],
        })
        manager = background_jobs.LocalJobManager(journal_root=self.journal_dir)
        report = manager.review_recovery()
        self.assertEqual(report["status"], "recovery_required")
        self.assertEqual(report["interrupted_job_count"], 1)
        self.assertEqual(report["interrupted_jobs"][0]["job_id"], active_id)
        self.assertEqual(manager.start(
            NOTICE, self.assignments, execute=True,
            confirm_execution=True, confine=server._confined,
        )["status"], "recovery_required")
        self.assertFalse((self.root / "ready.jpg").exists())

    def test_review_is_refreshed_and_excludes_this_process_active_work(self):
        owner = background_jobs.LocalJobManager(journal_root=self.journal_dir)
        manager = background_jobs.LocalJobManager(journal_root=self.journal_dir)
        self.assertEqual(manager.review_recovery()["status"], "clear")
        entered, resume = threading.Event(), threading.Event()
        original = notice_batch.core.prepare_pdf

        def hold(src, opts):
            entered.set()
            if not resume.wait(8):
                raise ValueError("test timed out")
            return original(src, opts)

        with patch.object(notice_batch.core, "prepare_pdf", side_effect=hold):
            start = owner.start(NOTICE, self.assignments, execute=True,
                                confirm_execution=True, confine=server._confined)
            try:
                self.assertTrue(entered.wait(8))
                own_report = owner.review_recovery()
                self.assertEqual(own_report["status"], "clear", own_report)
                foreign_report = manager.review_recovery()
                self.assertEqual(foreign_report["interrupted_job_count"], 1)
                self.assertTrue(foreign_report["interrupted_jobs"][0]["possibly_active_process"])
            finally:
                resume.set()
            until = time.monotonic() + 12
            while owner.get(start["job_id"])["status"] not in background_jobs.FINAL:
                self.assertLess(time.monotonic(), until)
                time.sleep(.02)
        refreshed = manager.review_recovery()
        self.assertEqual(refreshed["status"], "clear", refreshed)


if __name__ == "__main__":
    unittest.main()

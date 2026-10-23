"""v1.4 durable recovery: crash journals, safe staging and explicit cleanup."""
from __future__ import annotations

import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter
from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import background_jobs
import job_journal
import mcp_server as server
import notice_batch

NOTICE = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"


class DurableRecoveryV14Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        self.state = self.root / ".jechulok-jobs"
        self.photo = self.root / "photo.png"
        Image.new("RGB", (640, 480), "white").save(self.photo)
        self.pdf = self.root / "resume.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=200, height=300)
        with self.pdf.open("wb") as fp:
            writer.write(fp)
        self.ready = self.root / "ready.jpg"
        self.ready_pdf = self.root / "ready.pdf"
        self.assignments = [
            {"item_id": "item_01", "input_path": str(self.photo), "output_path": str(self.ready)},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.ready_pdf), "pages_to_extract": "1-3"},
        ]
        self.jobs = background_jobs.LocalJobManager(journal_root=self.state)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _start(self, manager=None, execute=True, confirm=True):
        return (manager or self.jobs).start(
            NOTICE, self.assignments,
            execute=execute, confirm_execution=confirm, confine=server._confined,
        )

    def _done(self, job_id):
        until = time.monotonic() + 12
        while time.monotonic() < until:
            r = self.jobs.get(job_id)
            if r["status"] in background_jobs.FINAL:
                return r
            time.sleep(.025)
        self.fail("Job did not become terminal")

    def _seed_interrupted(self, *, pid=999999999, stage_exists=True, existing_output=False):
        job_id = "TESTjobSafeRecovery_01234"
        stage = job_journal.stage_for_output(self.ready, job_id, "item_01")
        if stage_exists:
            stage.write_bytes(b"synthetic temporary contents")
        if existing_output:
            self.ready.write_bytes(b"existing approved output -- do not delete")
        record = {
            "schema": 1, "job_id": job_id, "status": "running",
            "total": 2, "completed": 1, "pid": pid, "session": "synthetic",
            "outputs": [str(self.ready), str(self.ready_pdf)],
            "staging": [{
                "item_id": "item_01", "stage": str(stage), "final": str(self.ready),
            }],
        }
        job_journal.JobJournal(self.state).write(record)
        return job_id, stage

    def test_readonly_preview_leaves_no_job_store(self):
        result = self._start(execute=False, confirm=False)
        self.assertEqual(result["status"], "planned")
        self.assertFalse(self.state.exists())
        self.assertFalse(self.ready.exists())

    def test_success_publishes_only_final_files_and_keeps_private_history(self):
        started = self._start()
        self.assertIn(started["status"], {"queued", "running", "publishing", "completed"})
        job_id = started["job_id"]
        end = self._done(job_id)
        self.assertEqual(end["status"], "completed", end)
        self.assertTrue(self.ready.exists())
        self.assertTrue(self.ready_pdf.exists())
        self.assertEqual(end["result"]["summary"]["generated_files"], 2)
        self.assertEqual(end["result"]["results"][0]["output"], str(self.ready))
        self.assertEqual(end["result"]["results"][1]["output"], str(self.ready_pdf))
        self.assertFalse(list(self.root.glob(".*.jechulok-*")))
        self.assertFalse(end["reusable_approval"])
        self.assertFalse(end["institutional_submission_confirmed"])

        records = list(self.state.glob("*.json"))
        self.assertEqual(len(records), 1)
        record = job_journal.JobJournal(self.state).read(job_id)
        self.assertEqual(record["status"], "completed")
        serialized = records[0].read_text("utf-8")
        self.assertNotIn(NOTICE, serialized)
        self.assertNotIn(str(self.photo), serialized)
        self.assertNotIn(str(self.pdf), serialized)
        self.assertNotIn("confirm_execution", serialized)
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(records[0].stat().st_mode), 0o600)

        restored = background_jobs.LocalJobManager(journal_root=self.state)
        state = restored.get(job_id)
        self.assertEqual(state["status"], "completed")
        self.assertTrue(state["recovered_from_disk"])
        self.assertFalse(state["reusable_approval"])
        self.assertTrue(self.ready.exists())
        self.assertEqual(restored.review_recovery()["status"], "clear")

    def test_interrupted_record_blocks_restart_until_explicit_review(self):
        job_id, stage = self._seed_interrupted(existing_output=True)
        new_server = background_jobs.LocalJobManager(journal_root=self.state)
        before_stage = stage.read_bytes()
        before_output = self.ready.read_bytes()

        inspection = new_server.review_recovery()
        self.assertEqual(inspection["status"], "recovery_required")
        self.assertEqual(inspection["interrupted_jobs"][0]["status"], "interrupted")
        self.assertFalse(inspection["auto_resume"])
        self.assertFalse(inspection["auto_delete"])
        self.assertTrue(stage.exists())
        blocked = self._start(manager=new_server)
        self.assertEqual(blocked["status"], "needs_review" if self.ready.exists() else "recovery_required")
        preview = new_server.resolve_recovery(
            job_id, cleanup_staging=True, confirm_cleanup=False,
            checked_final_outputs=True, confine=server._confined,
        )
        self.assertEqual(preview["status"], "needs_confirmation")
        self.assertEqual(stage.read_bytes(), before_stage)
        result = new_server.resolve_recovery(
            job_id, cleanup_staging=True, confirm_cleanup=True,
            checked_final_outputs=True, confine=server._confined,
        )
        self.assertEqual(result["status"], "reviewed", result)
        self.assertFalse(stage.exists())
        self.assertEqual(self.ready.read_bytes(), before_output)
        self.assertEqual(new_server.review_recovery()["status"], "clear")
        self.assertEqual(job_journal.JobJournal(self.state).read(job_id)["status"], "reviewed")
        self.assertFalse(result["reusable_approval"])

    def test_recovered_job_blocks_new_approved_execution(self):
        job_id, stage = self._seed_interrupted()
        restarted = background_jobs.LocalJobManager(journal_root=self.state)
        blocked = self._start(manager=restarted)
        self.assertEqual(blocked["status"], "recovery_required")
        self.assertFalse(self.ready.exists())
        self.assertFalse(self.ready_pdf.exists())
        self.assertTrue(stage.exists())

    def test_crash_during_publication_keeps_final_file(self):
        job_id, stage = self._seed_interrupted()
        os.link(stage, self.ready)  # Simulate one successfully published hard link.
        journal = job_journal.JobJournal(self.state)
        old = journal.read(job_id)
        old["status"] = "publishing"
        journal.write(old)
        before = self.ready.read_bytes()
        restarted = background_jobs.LocalJobManager(journal_root=self.state)
        inspected = restarted.review_recovery()["interrupted_jobs"][0]
        self.assertEqual(inspected["previous_status"], "publishing")
        self.assertTrue(inspected["output_files"][0]["exists"])
        self.assertTrue(stage.exists())
        result = restarted.resolve_recovery(
            job_id, cleanup_staging=True, confirm_cleanup=True,
            checked_final_outputs=True, confine=server._confined,
        )
        self.assertEqual(result["status"], "reviewed", result)
        self.assertFalse(stage.exists())
        self.assertEqual(self.ready.read_bytes(), before)
        self.assertFalse(result["final_outputs_will_be_deleted"])

    def test_pid_check_is_readonly_on_all_platforms(self):
        self.assertFalse(job_journal.pid_is_alive(999999999))
        if os.name == "nt":
            # Regression: os.kill(pid, 0) can interrupt the Windows Python
            # process itself. The new query must use kernel32 only.
            with patch.object(job_journal.os, "kill", side_effect=AssertionError("signal sent")):
                self.assertTrue(job_journal.pid_is_alive(os.getpid()))
        else:
            self.assertTrue(job_journal.pid_is_alive(os.getpid()))

    def test_alive_owner_refuses_deletion(self):
        job_id, stage = self._seed_interrupted(pid=os.getpid())
        recovered = background_jobs.LocalJobManager(journal_root=self.state)
        result = recovered.resolve_recovery(
            job_id, cleanup_staging=True, confirm_cleanup=True,
            checked_final_outputs=True, confine=server._confined,
        )
        self.assertEqual(result["status"], "possibly_active")
        self.assertTrue(stage.exists())

    def test_manipulated_record_cannot_delete_user_output(self):
        job_id, stage = self._seed_interrupted()
        final = self.root / "USER_DATA.jpg"
        final.write_bytes(b"precious content")
        record = job_journal.JobJournal(self.state).read(job_id)
        record["staging"][0]["stage"] = str(final)
        job_journal.JobJournal(self.state).write(record)
        recovered = background_jobs.LocalJobManager(journal_root=self.state)
        response = recovered.resolve_recovery(
            job_id, cleanup_staging=True, confirm_cleanup=True,
            checked_final_outputs=True, confine=server._confined,
        )
        self.assertEqual(response["status"], "needs_review")
        self.assertEqual(final.read_bytes(), b"precious content")
        self.assertTrue(stage.exists())

    def test_symlinked_stage_refuses_cleanup(self):
        job_id, stage = self._seed_interrupted(stage_exists=False)
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external) / "important"
            outside.write_bytes(b"keep")
            try:
                stage.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink unsupported")
            recovered = background_jobs.LocalJobManager(journal_root=self.state)
            result = recovered.resolve_recovery(
                job_id, cleanup_staging=True, confirm_cleanup=True,
                checked_final_outputs=True, confine=server._confined,
            )
            self.assertEqual(result["status"], "needs_review")
            self.assertEqual(outside.read_bytes(), b"keep")
            self.assertTrue(stage.is_symlink())

    def test_publish_conflict_preserves_external_output_and_cleans_stages(self):
        original = notice_batch.core.prepare_pdf

        def interfere(src, args):
            # Another process creates the exact final path after preflight.
            self.ready_pdf.write_bytes(b"other program data")
            return original(src, args)

        with patch.object(notice_batch.core, "prepare_pdf", side_effect=interfere):
            started = self._start()
            finished = self._done(started["job_id"])
        self.assertEqual(finished["status"], "failed")
        self.assertFalse(self.ready.exists())
        self.assertEqual(self.ready_pdf.read_bytes(), b"other program data")
        self.assertFalse(list(self.root.glob(".*.jechulok-*")))
        self.assertFalse(finished["reusable_approval"])

    def test_journal_corrupt_and_oversized_files_are_ignored(self):
        self.state.mkdir(mode=0o700)
        (self.state / "corrupted.json").write_text("{bad-json", encoding="utf-8")
        (self.state / "oversized.json").write_bytes(b"x" * (job_journal.MAX_RECORD_BYTES + 1))
        fresh = background_jobs.LocalJobManager(journal_root=self.state)
        self.assertEqual(fresh.review_recovery()["status"], "clear")


class RecoveryMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_19_tools_and_readonly_recovery_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            args = StdioServerParameters(
                command=sys.executable,
                args=[str(ROOT / "scripts" / "mcp_server.py")],
                env={"JECHULOK_ALLOWED_DIRS": str(root)},
            )
            async with Client(args) as client:
                names = {x.name for x in (await client.list_tools()).tools}
                self.assertEqual(len(names), 20)
                self.assertIn("list_interrupted_submission_jobs", names)
                self.assertIn("resolve_interrupted_submission_job", names)
                response = await client.call_tool("list_interrupted_submission_jobs", {})
                self.assertEqual(response.structured_content["status"], "clear")
                self.assertFalse((root / ".jechulok-jobs").exists())


if __name__ == "__main__":
    unittest.main()

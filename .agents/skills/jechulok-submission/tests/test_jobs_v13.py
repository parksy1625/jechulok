"""v1.3 cooperative background jobs: real progress, rollback and stdio MCP."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter
from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mcp_server as server
import background_jobs
import notice_batch

NOTICE = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"


class BackgroundJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        self.photo = self.root / "photo.png"
        Image.new("RGB", (640, 480), "white").save(self.photo)
        self.pdf = self.root / "resume.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=100, height=100)
        with self.pdf.open("wb") as fp:
            writer.write(fp)
        self.output_photo = self.root / "ready.jpg"
        self.output_pdf = self.root / "ready.pdf"
        self.assignments = [
            {"item_id": "item_01", "input_path": str(self.photo),
             "output_path": str(self.output_photo)},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.output_pdf), "pages_to_extract": "1-3"},
        ]
        self.jobs = background_jobs.LocalJobManager()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def start(self, execute=True, confirm=True, assignments=None):
        return self.jobs.start(
            NOTICE, self.assignments if assignments is None else assignments,
            execute=execute, confirm_execution=confirm, confine=server._confined,
        )

    def await_final(self, job_id, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.jobs.get(job_id)
            if state["status"] in background_jobs.FINAL:
                return state
            time.sleep(.02)
        self.fail("Background job did not reach terminal state within timeout")

    def test_previews_dont_create_jobs_or_files(self):
        initial = self.start(execute=False, confirm=False)
        self.assertEqual(initial["status"], "planned")
        self.assertFalse(initial["job_started"])
        only_first_flag = self.start(execute=True, confirm=False)
        self.assertEqual(only_first_flag["status"], "needs_confirmation")
        self.assertFalse(self.jobs._jobs)
        self.assertFalse(self.output_photo.exists())
        self.assertFalse(self.output_pdf.exists())
        self.assertFalse(self.jobs.cancel("nonexistent")["status"] == "cancelled")

    def test_end_to_end_progress_and_technical_success(self):
        started = self.start()
        self.assertIn(started["status"], {"queued", "running", "completed"})
        job_id = started["job_id"]
        done = self.await_final(job_id)
        self.assertEqual(done["status"], "completed", done)
        self.assertEqual(done["progress"]["completed_items"], 2)
        self.assertEqual(done["progress"]["percent"], 100)
        self.assertEqual(done["result"]["summary"]["technically_verified"], 2)
        self.assertTrue(self.output_photo.exists())
        self.assertTrue(self.output_pdf.exists())
        self.assertTrue(self.photo.exists())
        self.assertTrue(self.pdf.exists())
        self.assertTrue(any(x["event"] == "item_completed" for x in done["events"]))
        self.assertFalse(done["institutional_submission_confirmed"])
        self.assertFalse(done["reusable_approval"])

    def test_cancel_between_items_rolls_back_created_files(self):
        entered = threading.Event()
        release = threading.Event()
        original = notice_batch.core.prepare_pdf

        def slow_pdf(src, args):
            entered.set()
            if not release.wait(8):
                raise RuntimeError("PDF test release timed out")
            return original(src, args)

        with patch.object(notice_batch.core, "prepare_pdf", side_effect=slow_pdf):
            started = self.start()
            job_id = started["job_id"]
            try:
                self.assertTrue(entered.wait(8), "Worker never reached PDF")
                mid = self.jobs.get(job_id)
                self.assertEqual(mid["progress"]["completed_items"], 1, mid)
                self.assertEqual(mid["progress"]["current_item_id"], "item_02")
                self.assertTrue(self.output_photo.exists())
                requested = self.jobs.cancel(job_id)
                self.assertEqual(requested["status"], "cancel_requested")
                self.assertTrue(requested["cancel_requested"])
                self.assertEqual(self.start()["status"], "busy")
            finally:
                release.set()
            done = self.await_final(job_id)
            self.assertEqual(done["status"], "cancelled", done)
            self.assertEqual(done["result"]["status"], "cancelled")
            self.assertEqual(done["progress"]["completed_items"], 0)
            self.assertEqual(done["progress"]["percent"], 0)
            self.assertFalse(self.output_photo.exists())
            self.assertFalse(self.output_pdf.exists())
            self.assertTrue(self.photo.exists())
            self.assertTrue(self.pdf.exists())
            self.assertFalse(done["result"]["retry_guidance"]["reuse_prior_approval"])
            self.assertFalse(done["result"]["retry_guidance"]["automatic_retry"])

        # There is no implicit restart. It requires a fresh explicit action.
        preview = self.start(execute=False, confirm=False)
        self.assertEqual(preview["status"], "planned")
        self.assertFalse(preview["job_started"])

    def test_cancel_before_first_file_rolls_back(self):
        entered = threading.Event()
        release = threading.Event()
        original = notice_batch.core.prepare_image

        def slow_image(src, args):
            entered.set()
            if not release.wait(8):
                raise RuntimeError("Image test release timed out")
            return original(src, args)

        with patch.object(notice_batch.core, "prepare_image", side_effect=slow_image):
            job = self.start()
            try:
                self.assertTrue(entered.wait(8))
                self.assertEqual(self.jobs.cancel(job["job_id"])["status"], "cancel_requested")
            finally:
                release.set()
            result = self.await_final(job["job_id"])
            self.assertEqual(result["status"], "cancelled")
            self.assertFalse(self.output_photo.exists())
            self.assertFalse(self.output_pdf.exists())

    def test_failed_operation_does_not_leave_partial_outputs(self):
        with patch.object(notice_batch.core, "prepare_pdf",
                          side_effect=ValueError("synthetic PDF fail")):
            job = self.start()
            final = self.await_final(job["job_id"])
        self.assertEqual(final["status"], "failed")
        self.assertFalse(self.output_photo.exists())
        self.assertFalse(self.output_pdf.exists())
        self.assertFalse(final["reusable_approval"])

    def test_invalid_plan_does_not_start_or_consume_approval(self):
        with self.output_photo.open("wb") as fp:
            fp.write(b"existing output")
        result = self.start()
        self.assertEqual(result["status"], "needs_review", result)
        self.assertFalse(self.output_pdf.exists())
        self.assertEqual(self.output_photo.read_bytes(), b"existing output")
        self.assertEqual(len(self.jobs._jobs), 0)

    def test_unknown_jobs_and_completed_cannot_be_cancelled(self):
        self.assertEqual(self.jobs.get("fake")["status"], "not_found")
        self.assertEqual(self.jobs.cancel("fake")["status"], "not_found")
        job = self.start()
        done = self.await_final(job["job_id"])
        self.assertEqual(done["status"], "completed")
        self.assertEqual(self.jobs.cancel(job["job_id"])["status"], "completed")
        self.assertTrue(self.output_photo.exists())


class BackgroundJobMCPTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_discovers_three_new_tools_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(ROOT / "scripts" / "mcp_server.py")],
                env={"JECHULOK_ALLOWED_DIRS": str(root)},
            )
            async with Client(params) as client:
                names = {tool.name for tool in (await client.list_tools()).tools}
                self.assertEqual(len(names), 20)
                self.assertTrue({"start_submission_job", "get_submission_job",
                                 "cancel_submission_job", "list_interrupted_submission_jobs", "resolve_interrupted_submission_job"} <= names)
                started = await client.call_tool("start_submission_job", {
                    "notice_text": NOTICE, "assignments": [],
                })
                self.assertEqual(started.structured_content["status"], "needs_review")
                unknown = await client.call_tool("get_submission_job", {"job_id": "none"})
                self.assertEqual(unknown.structured_content["status"], "not_found")


if __name__ == "__main__":
    unittest.main()

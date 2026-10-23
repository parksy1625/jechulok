"""v1.6 guided submission: one MCP tool, exact-plan consent and real stdio."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from mcp import Client, StdioServerParameters
from PIL import Image
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import background_jobs
import mcp_server as server
from submission_assistant import assist, plan_fingerprint

NOTICE = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"


class GuidedFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        self.photo = self.root / "photo.png"
        Image.new("RGB", (640, 480), "#ffffff").save(self.photo)
        self.pdf = self.root / "resume.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=250, height=350)
        with self.pdf.open("wb") as f:
            writer.write(f)
        self.output_img = self.root / "ready.jpg"
        self.output_pdf = self.root / "ready.pdf"
        self.assignments = [
            {"item_id": "item_01", "input_path": str(self.photo),
             "output_path": str(self.output_img)},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.output_pdf), "pages_to_extract": "1-3"},
        ]
        self.files = [
            {"item_id": "item_01", "file_path": str(self.output_img)},
            {"item_id": "item_02", "file_path": str(self.output_pdf)},
        ]
        self.jobs = background_jobs.LocalJobManager(
            journal_root=self.root / ".jechulok-jobs",
        )

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def call(self, **kw):
        return assist(confine=server._confined, jobs=self.jobs, **kw)

    def wait(self, job_id: str) -> dict:
        until = time.monotonic() + 14
        while time.monotonic() < until:
            result = self.call(action="status", job_id=job_id)
            if result["status"] in {"awaiting_final_verification", "needs_review"}:
                return result
            time.sleep(.025)
        self.fail("Guided local job did not terminate")

    def test_next_one_question_at_a_time_and_never_writes(self):
        initial = self.call()
        self.assertEqual(initial["workflow"]["step"], 1)
        self.assertEqual(initial["workflow"]["next_action"], "provide_notice")
        self.assertFalse(initial["automatic_upload"])
        missing = self.call(notice_text=NOTICE)
        self.assertEqual(missing["workflow"]["step"], 2)
        self.assertEqual(missing["workflow"]["next_action"], "choose_source")
        partial = self.call(notice_text=NOTICE, assignments=self.assignments[:1])
        self.assertEqual(partial["workflow"]["next_action"], "choose_source")
        self.assertEqual(partial["guidance"]["item_id"], "item_02")
        preview = self.call(notice_text=NOTICE, assignments=self.assignments)
        self.assertEqual(preview["workflow"]["step"], 3)
        self.assertEqual(preview["workflow"]["next_action"], "approve_exact_plan")
        self.assertEqual(len(preview["approval_fingerprint"]), 64)
        self.assertFalse(preview["human_approval_recorded"])
        self.assertFalse(self.output_img.exists())
        self.assertFalse(self.output_pdf.exists())
        self.assertFalse((self.root / ".jechulok-jobs").exists())

    def test_approval_digest_is_stable_for_same_plan(self):
        a = self.call(notice_text=NOTICE, assignments=self.assignments)
        b = self.call(notice_text=NOTICE, assignments=self.assignments)
        self.assertEqual(a["approval_fingerprint"], b["approval_fingerprint"])
        self.assertEqual(plan_fingerprint(a["guidance"]["plan_preview"]),
                         a["approval_fingerprint"])

    def test_start_requires_two_flags_and_exact_preview_fingerprint(self):
        preview = self.call(notice_text=NOTICE, assignments=self.assignments)
        token = preview["approval_fingerprint"]
        missing_flag = self.call(action="start", notice_text=NOTICE,
                                 assignments=self.assignments,
                                 approval_fingerprint=token,
                                 execute=True, confirm_execution=False)
        self.assertEqual(missing_flag["status"], "awaiting_human_approval")
        missing_token = self.call(action="start", notice_text=NOTICE,
                                  assignments=self.assignments,
                                  execute=True, confirm_execution=True)
        self.assertEqual(missing_token["status"], "awaiting_human_approval")
        wrong_token = self.call(action="start", notice_text=NOTICE,
                                assignments=self.assignments,
                                approval_fingerprint="0" * 64,
                                execute=True, confirm_execution=True)
        self.assertEqual(wrong_token["status"], "plan_changed")
        self.assertFalse((self.root / ".jechulok-jobs").exists())
        self.assertFalse(self.output_img.exists())
        self.assertFalse(self.output_pdf.exists())
        self.assertFalse(self.jobs._jobs)

    def test_change_after_preview_blocks_and_requires_reapproval(self):
        preview = self.call(notice_text=NOTICE, assignments=self.assignments)
        changed = [dict(x) for x in self.assignments]
        changed[0]["output_path"] = str(self.root / "other.jpg")
        outcome = self.call(
            action="start", notice_text=NOTICE, assignments=changed,
            approval_fingerprint=preview["approval_fingerprint"],
            execute=True, confirm_execution=True,
        )
        self.assertEqual(outcome["status"], "plan_changed")
        self.assertFalse(self.jobs._jobs)
        self.assertFalse((self.root / "other.jpg").exists())

    def test_real_create_poll_and_verified_manual_completion(self):
        pre = self.call(notice_text=NOTICE, assignments=self.assignments)
        start = self.call(
            action="start", notice_text=NOTICE, assignments=self.assignments,
            approval_fingerprint=pre["approval_fingerprint"],
            execute=True, confirm_execution=True,
        )
        self.assertEqual(start["status"], "job_started", start)
        job_id = start["job"]["job_id"]
        done = self.wait(job_id)
        self.assertEqual(done["status"], "awaiting_final_verification", done)
        self.assertEqual(done["workflow"]["step"], 5)
        self.assertTrue(self.output_img.is_file())
        self.assertTrue(self.output_pdf.is_file())
        need_final = self.call(action="verify", notice_text=NOTICE)
        self.assertEqual(need_final["workflow"]["next_action"], "choose_final_files")
        verified = self.call(
            action="verify", notice_text=NOTICE, final_files=self.files,
        )
        self.assertEqual(verified["status"], "manual_review_required", verified)
        self.assertEqual(verified["verification"]["status"], "technical_pass")
        self.assertFalse(verified["institutional_submission_confirmed"])
        self.assertFalse(verified["human_approval_recorded"])
        self.assertFalse(verified["automatic_upload"])

    def test_crash_recovery_and_missing_job_guidance(self):
        no_id = self.call(action="status")
        self.assertEqual(no_id["status"], "needs_job_id")
        missing = self.call(action="status", job_id="does-not-exist")
        self.assertEqual(missing["status"], "needs_review")
        self.assertEqual(missing["job"]["status"], "not_found")

    def test_already_existing_output_blocks_start(self):
        self.output_img.write_bytes(b"important existing file")
        started = self.call(action="start", notice_text=NOTICE,
                            assignments=self.assignments,
                            execute=True, confirm_execution=True)
        self.assertEqual(started["status"], "needs_review")
        self.assertEqual(self.output_img.read_bytes(), b"important existing file")
        self.assertFalse(self.jobs._jobs)

    def test_manager_internal_fingerprint_recheck_refuses_stale_plan(self):
        preview = self.call(notice_text=NOTICE, assignments=self.assignments)
        altered = [dict(x) for x in self.assignments]
        altered[0]["output_path"] = str(self.root / "new-output.jpg")
        refused = self.jobs.start(
            NOTICE, altered, execute=True, confirm_execution=True,
            confine=server._confined,
            expected_plan_fingerprint=preview["approval_fingerprint"],
        )
        self.assertEqual(refused["status"], "plan_changed")
        self.assertFalse(self.jobs._jobs)


class GuidedStdioTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_single_entry_point_is_readonly_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            params = StdioServerParameters(
                command=sys.executable, args=[str(ROOT / "scripts" / "mcp_server.py")],
                env={"JECHULOK_ALLOWED_DIRS": str(root)},
            )
            async with Client(params) as client:
                names = {t.name for t in (await client.list_tools()).tools}
                self.assertEqual(len(names), 20)
                self.assertIn("assist_submission", names)
                reply = await client.call_tool("assist_submission", {})
                self.assertFalse(reply.is_error)
                self.assertEqual(reply.structured_content["status"], "needs_input")
                self.assertEqual(reply.structured_content["workflow"]["next_action"], "provide_notice")
                self.assertFalse((root / ".jechulok-jobs").exists())


if __name__ == "__main__":
    unittest.main()

"""v0.8 concise agent guidance and secure opt-in HTML-report tests."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter
from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mcp_server as server
from guided_experience import guide_next_step, create_report

NOTICE = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"


class V08Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        self.photo = self.root / "portrait.png"
        Image.new("RGB", (600, 450), "white").save(self.photo)
        self.pdf = self.root / "resume.pdf"
        w = PdfWriter()
        for _ in range(5):
            w.add_blank_page(width=300, height=400)
        with self.pdf.open("wb") as fp:
            w.write(fp)
        self.ready_photo = self.root / "ready.jpg"
        self.ready_pdf = self.root / "ready.pdf"
        self.report = self.root / "report.html"
        self.assignments = [
            {"item_id": "item_01", "input_path": str(self.photo),
             "output_path": str(self.ready_photo)},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.ready_pdf), "pages_to_extract": "1-3"},
        ]
        self.final_files = [
            {"item_id": "item_01", "file_path": str(self.ready_photo)},
            {"item_id": "item_02", "file_path": str(self.ready_pdf)},
        ]

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _prepare(self):
        result = server.prepare_submission_batch(
            NOTICE, self.assignments, execute=True, confirm_execution=True,
        )
        self.assertEqual(result["status"], "pass", result)

    def guide(self, notice=NOTICE, assignments=None, final_files=None):
        return guide_next_step(
            notice, assignments, final_files, confine=server._confined,
        )

    def report_call(self, *, execute=False, confirm=False, path=None, files=None,
                    notice=NOTICE):
        return create_report(
            notice, self.final_files if files is None else files,
            str(self.report if path is None else path),
            execute=execute, confirm_execution=confirm,
            confine=server._confined,
        )

    def test_guide_asks_for_missing_file_not_fake_assignment(self):
        result = self.guide()
        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["next_action"], "choose_source")
        self.assertEqual(result["item_id"], "item_01")
        self.assertFalse(result["execution_permitted"])
        self.assertFalse(result["human_approval_recorded"])
        partial = self.guide(assignments=self.assignments[:1])
        self.assertEqual(partial["item_id"], "item_02")
        self.assertFalse(self.ready_photo.exists())

    def test_guide_noisy_notice_and_invalid_mapping(self):
        ambiguous = self.guide(notice=NOTICE + "\n공통규격 PDF 100KB 이하")
        self.assertEqual(ambiguous["status"], "needs_review")
        self.assertEqual(ambiguous["next_action"], "clarify_notice")
        bad = [self.assignments[0], dict(self.assignments[1], pages_to_extract=None)]
        result = self.guide(assignments=bad)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["next_action"], "fix_plan")
        self.assertFalse(self.ready_pdf.exists())

    def test_guide_present_exact_plan_without_approval(self):
        result = self.guide(assignments=self.assignments)
        self.assertEqual(result["status"], "awaiting_human_approval")
        self.assertEqual(len(result["plan_preview"]), 2)
        self.assertEqual(result["plan_preview"][1]["pages_to_extract"], "1-3")
        self.assertFalse(result["execution_permitted"])
        self.assertFalse(result["human_approval_recorded"])
        self.assertFalse(self.ready_photo.exists())

    def test_final_guidance_after_inspection(self):
        self._prepare()
        result = self.guide(final_files=self.final_files)
        self.assertEqual(result["status"], "technical_pass_manual_review_pending")
        self.assertEqual(result["next_action"], "check_original_content")
        self.assertGreater(result["unresolved_count"], 0)
        self.assertFalse(result["institutional_submission_confirmed"])
        # Prior success must not be trusted after a file changes.
        Image.new("RGB", (20, 20)).save(self.ready_photo, "JPEG")
        changed = self.guide(final_files=self.final_files)
        self.assertEqual(changed["status"], "needs_review")
        self.assertEqual(changed["next_action"], "fix_final_files")

    def test_report_preview_and_confirmation_do_not_write(self):
        self._prepare()
        before = {p.name for p in self.root.iterdir()}
        preview = self.report_call()
        self.assertEqual(preview["status"], "preview", preview)
        self.assertEqual(preview["technical_status"], "technical_pass")
        pending = self.report_call(execute=True)
        self.assertEqual(pending["status"], "needs_confirmation")
        self.assertEqual(before, {p.name for p in self.root.iterdir()})
        self.assertFalse(self.report.exists())
        with self.assertRaises(ValueError):
            self.report_call(execute=1, confirm=True)

    def test_report_approved_write_and_no_overwrite(self):
        self._prepare()
        res = self.report_call(execute=True, confirm=True)
        self.assertEqual(res["status"], "report_created")
        self.assertTrue(self.report.is_file())
        output = self.report.read_text(encoding="utf-8")
        self.assertIn("제출OK · 로컬 기술 검증 보고서", output)
        self.assertIn("증명사진", output)
        self.assertIn("이력서", output)
        self.assertIn("technical_pass", output)
        self.assertIn("Content-Security-Policy", output)
        self.assertNotIn(str(self.root), output)
        self.assertNotIn("portrait.png", output)  # Source should never be embedded.
        self.assertNotIn("http://", output)
        self.assertNotIn("https://", output)
        self.assertNotIn("<script", output)
        original = self.report.read_bytes()
        duplicate = server.create_submission_html_report(
            NOTICE, self.final_files, str(self.report),
            execute=True, confirm_execution=True,
        )
        self.assertEqual(duplicate["status"], "error")
        self.assertEqual(self.report.read_bytes(), original)

    def test_html_escapes_hostile_filenames_and_labels(self):
        if os.name == "nt":
            self.skipTest("Windows prohibits angle brackets in filenames")
        # Labels in notice are restricted to recognized kinds. User filename is
        # not trusted, so special HTML characters must be escaped.
        self._prepare()
        weird = self.root / 'ready_<img src=x onerror=alert(1)>.jpg'
        self.ready_photo.rename(weird)
        f = [dict(self.final_files[0], file_path=str(weird)), self.final_files[1]]
        result = self.report_call(execute=True, confirm=True, files=f)
        self.assertEqual(result["status"], "report_created", result)
        body = self.report.read_text("utf-8")
        self.assertIn("&lt;img", body)
        self.assertNotIn("<img src=x", body)
        self.assertNotIn("<script", body)

    def test_incomplete_verification_generates_honest_report(self):
        result = self.report_call(execute=True, confirm=True)
        self.assertEqual(result["status"], "report_created")
        self.assertEqual(result["technical_status"], "needs_review")
        self.assertFalse(result["ready_to_submit"])
        body = self.report.read_text("utf-8")
        self.assertIn("접수 완료 증명이 아닙니다", body)

    def test_invalid_path_and_extension_rejected(self):
        self._prepare()
        bad = self.root / "report.txt"
        with self.assertRaises(ValueError):
            self.report_call(execute=True, confirm=True, path=bad)
        self.assertFalse(bad.exists())
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(ValueError):
                self.report_call(execute=True, confirm=True,
                                 path=Path(outside) / "report.html")

    async def test_mcp_inprocess_and_stdio(self):
        async with Client(server.mcp) as client:
            listing = await client.list_tools()
            names = {x.name for x in listing.tools}
            self.assertEqual(len(names), 20)
            self.assertIn("guide_submission_workflow", names)
            self.assertIn("create_submission_html_report", names)
            response = await client.call_tool("guide_submission_workflow", {
                "notice_text": NOTICE,
            })
            self.assertFalse(response.is_error)
            self.assertEqual(response.structured_content["status"], "needs_input")
            preview = await client.call_tool("create_submission_html_report", {
                "notice_text": NOTICE,
                "files": self.final_files,
                "output_path": str(self.report),
            })
            self.assertFalse(preview.is_error)
            self.assertEqual(preview.structured_content["status"], "preview")
            self.assertFalse(self.report.exists())

        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "scripts" / "mcp_server.py")],
            env={"JECHULOK_ALLOWED_DIRS": str(self.root)},
        )
        async with Client(params) as client:
            names = {x.name for x in (await client.list_tools()).tools}
            self.assertEqual(len(names), 20)
            self.assertIn("create_submission_html_report", names)


if __name__ == "__main__":
    unittest.main()

"""JeChulOK v0.7 review workflow, final file verification and MCP tests."""
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
from review_workflow import review_plan, verify_package

NOTICE = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"


class ReviewWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        self.source_photo = self.root / "source.png"
        Image.new("RGB", (600, 450), "#3376aa").save(self.source_photo)
        self.source_pdf = self.root / "source.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=200, height=300)
        with self.source_pdf.open("wb") as fh:
            writer.write(fh)
        self.ready_photo = self.root / "ready.jpg"
        self.ready_pdf = self.root / "ready.pdf"
        self.assignments = [
            {"item_id": "item_01", "input_path": str(self.source_photo),
             "output_path": str(self.ready_photo)},
            {"item_id": "item_02", "input_path": str(self.source_pdf),
             "output_path": str(self.ready_pdf), "pages_to_extract": "1-3"},
        ]
        self.final_files = [
            {"item_id": "item_01", "file_path": str(self.ready_photo)},
            {"item_id": "item_02", "file_path": str(self.ready_pdf)},
        ]

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _prepare(self):
        return server.prepare_submission_batch(
            NOTICE, self.assignments, execute=True, confirm_execution=True
        )

    def test_review_is_read_only_and_requires_human_approval(self):
        result = review_plan(NOTICE, self.assignments, confine=server._confined)
        self.assertEqual(result["status"], "awaiting_human_approval", result)
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["execution_permitted"])
        self.assertFalse(result["human_approval_recorded"])
        self.assertEqual(len(result["plan"]), 2)
        self.assertTrue(all(not step["done"] for step in result["approval_checklist"]))
        self.assertFalse(self.ready_photo.exists())
        self.assertFalse(self.ready_pdf.exists())

    def test_review_shows_remediation_for_invalid_pdf_selection(self):
        bad = [self.assignments[0], {**self.assignments[1], "pages_to_extract": None}]
        result = review_plan(NOTICE, bad, confine=server._confined)
        self.assertEqual(result["status"], "needs_review", result)
        self.assertTrue(any(x["code"] == "select_pages" for x in result["remediation"]))
        self.assertFalse(self.ready_photo.exists())
        self.assertFalse(self.ready_pdf.exists())

    def test_batch_result_contains_non_executable_approval_details(self):
        planned = server.prepare_submission_batch(NOTICE, self.assignments)
        self.assertEqual(planned["status"], "planned")
        self.assertFalse(planned["human_approval_recorded"])
        self.assertEqual(planned["remediation"], [])
        confirmed = self._prepare()
        self.assertEqual(confirmed["status"], "pass", confirmed)
        self.assertFalse(confirmed["human_approval_recorded"])
        self.assertFalse(confirmed["institutional_submission_confirmed"])
        self.assertTrue(all(not x["done"] for x in confirmed["approval_checklist"]))
        self.assertEqual(confirmed["summary"]["technically_verified"], 2)

    def test_final_checklist_verifies_current_files_not_prior_result(self):
        self.assertEqual(self._prepare()["status"], "pass")
        result = verify_package(NOTICE, self.final_files, confine=server._confined)
        self.assertEqual(result["status"], "technical_pass", result)
        self.assertEqual(result["summary"]["technically_verified"], 2)
        self.assertTrue(result["manual_review_required"])
        self.assertFalse(result["ready_to_submit"])
        self.assertFalse(result["institutional_submission_confirmed"])
        self.assertTrue(all(not check["verified"] for check in result["manual_checklist"]))
        self.assertIn("check_portrait", {x["id"] for x in result["manual_checklist"]})
        self.assertIn("check_pdf_integrity", {x["id"] for x in result["manual_checklist"]})

    def test_modified_final_file_no_longer_passes(self):
        self.assertEqual(self._prepare()["status"], "pass")
        Image.new("RGB", (10, 10), "white").save(self.ready_photo, "JPEG")
        result = verify_package(NOTICE, self.final_files, confine=server._confined)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["summary"]["technically_verified"], 1)
        self.assertTrue(any(x["code"] == "adjust_dimensions" for x in result["remediation"]))

    def test_missing_or_extra_assignments_and_duplicate_paths(self):
        self.assertEqual(verify_package(
            NOTICE, self.final_files[:1], confine=server._confined
        )["status"], "needs_review")
        with self.assertRaises(ValueError):
            verify_package(
                NOTICE, [self.final_files[0], self.final_files[0]], confine=server._confined
            )
        duplicate = [
            self.final_files[0],
            {"item_id": "item_02", "file_path": str(self.ready_photo)},
        ]
        result = verify_package(NOTICE, duplicate, confine=server._confined)
        self.assertEqual(result["status"], "needs_review")

    def test_ambiguous_notice_blocks_final_pass(self):
        notice = NOTICE + "\n공통 조건 JPG 또는 PNG 100KB 이하"
        result = verify_package(notice, self.final_files, confine=server._confined)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["results"], [])

    def test_outside_path_does_not_verify(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "ready.jpg"
            Image.new("RGB", (300, 400)).save(target)
            files = [dict(self.final_files[0], file_path=str(target)), self.final_files[1]]
            result = verify_package(NOTICE, files, confine=server._confined)
            self.assertEqual(result["status"], "needs_review")
            self.assertTrue(any(x["technical_status"] == "error" for x in result["results"]))

    async def test_inprocess_mcp_two_new_tools(self):
        async with Client(server.mcp) as client:
            listing = await client.list_tools()
            names = {tool.name for tool in listing.tools}
            self.assertEqual(len(names), 17)
            self.assertIn("review_submission_plan", names)
            self.assertIn("verify_submission_package", names)
            review = await client.call_tool("review_submission_plan", {
                "notice_text": NOTICE, "assignments": self.assignments,
            })
            self.assertFalse(review.is_error)
            self.assertEqual(review.structured_content["status"], "awaiting_human_approval")
            final = await client.call_tool("verify_submission_package", {
                "notice_text": NOTICE, "files": self.final_files,
            })
            self.assertFalse(final.is_error)
            self.assertEqual(final.structured_content["status"], "needs_review")

    async def test_stdio_tool_listing(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "scripts" / "mcp_server.py")],
            env={"JECHULOK_ALLOWED_DIRS": str(self.root)},
        )
        async with Client(params) as client:
            listing = await client.list_tools()
            names = {tool.name for tool in listing.tools}
            self.assertEqual(len(names), 17)
            self.assertIn("verify_submission_package", names)


if __name__ == "__main__":
    unittest.main()

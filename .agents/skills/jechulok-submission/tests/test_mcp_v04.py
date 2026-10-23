"""v0.4 notice item parsing, safe batch approval, rollback, actual MCP integration."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader, PdfWriter
from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mcp_server as server
from notice_batch import analyze_notice, prepare_batch

NOTICE = """[공고]
제출서류
- 증명사진: JPG 300×400px 500KB 이하
- 이력서: PDF 5MB 이하, 최대 3페이지
접수 기간: 10월 23일
"""


class NoticeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.photo = self.root / "source.png"
        Image.new("RGB", (600, 450), "#5588cc").save(self.photo)
        self.pdf = self.root / "source.pdf"
        w = PdfWriter()
        for _ in range(5):
            w.add_blank_page(width=200, height=300)
        with self.pdf.open("wb") as fp:
            w.write(fp)
        self.out_photo = self.root / "ready.jpg"
        self.out_pdf = self.root / "ready.pdf"
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        self.assignments = [
            {"item_id": "item_01", "input_path": str(self.photo), "output_path": str(self.out_photo)},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.out_pdf), "pages_to_extract": "1-3"},
        ]

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_two_distinct_items_and_evidence(self):
        result = analyze_notice(NOTICE)
        self.assertEqual(result["status"], "parsed", result)
        self.assertEqual(result["total_items"], 2)
        self.assertEqual([x["category"] for x in result["items"]], ["photo", "resume"])
        self.assertEqual(result["items"][0]["parsed"]["rules"]["width"], 300)
        self.assertEqual(result["items"][1]["parsed"]["rules"]["max_pages"], 3)
        self.assertIn("증명사진:", result["items"][0]["evidence"])

    def test_unknown_shared_or_conflicting_rules_block(self):
        for text in [
            NOTICE + "\n공통 규격 PDF 2MB 이하",
            NOTICE.replace("JPG 300×400px 500KB 이하", "JPG 또는 PNG 500KB 이하"),
            NOTICE + "\n- 증명사진: JPG 250×330px 500KB 이하",
        ]:
            result = analyze_notice(text)
            self.assertEqual(result["status"], "needs_review", result)
            self.assertFalse(self.out_photo.exists())

    def test_no_guessed_items(self):
        result = analyze_notice("서류 2개 제출하세요. 서류는 각자 PDF 5MB 이하로 제출")
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["total_items"], 0)
        self.assertTrue(result["unassigned_conditions"])
        self.assertRaises(ValueError, analyze_notice, "A" * 20001)

    def test_dry_run_and_consent(self):
        dry = prepare_batch(NOTICE, self.assignments, confine=server._confined)
        self.assertEqual(dry["status"], "planned", dry)
        self.assertEqual(len(dry["plan"]), 2)
        pending = prepare_batch(NOTICE, self.assignments, execute=True, confine=server._confined)
        self.assertEqual(pending["status"], "needs_confirmation")
        self.assertFalse(self.out_photo.exists())
        self.assertFalse(self.out_pdf.exists())

    def test_full_two_file_execution_and_recheck(self):
        result = prepare_batch(NOTICE, self.assignments, execute=True,
                               confirm_execution=True, confine=server._confined)
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["results"][0]["verification"]["status"], "pass")
        with Image.open(self.out_photo) as im:
            self.assertEqual(im.size, (300, 400))
        self.assertLessEqual(self.out_photo.stat().st_size, 500 * 1024)
        self.assertEqual(len(PdfReader(str(self.out_pdf)).pages), 3)
        self.assertTrue(self.photo.exists())
        self.assertTrue(self.pdf.exists())

    def test_preflight_blocks_all_if_one_target_exists(self):
        self.out_pdf.write_bytes(b"existing")
        res = prepare_batch(NOTICE, self.assignments, execute=True,
                            confirm_execution=True, confine=server._confined)
        self.assertEqual(res["status"], "needs_review", res)
        self.assertFalse(self.out_photo.exists())
        self.assertEqual(self.out_pdf.read_bytes(), b"existing")

    def test_missing_pages_or_item_mapping_blocks(self):
        no_pages = [self.assignments[0], {**self.assignments[1], "pages_to_extract": None}]
        res = prepare_batch(NOTICE, no_pages, confine=server._confined)
        self.assertEqual(res["status"], "needs_review", res)
        self.assertFalse(self.out_photo.exists())
        no_item = prepare_batch(NOTICE, self.assignments[:1], confine=server._confined)
        self.assertEqual(no_item["status"], "needs_review")

    def test_existing_compliant_pdf_is_verified_not_written(self):
        text = "이력서: PDF 5MB 이하, 최대 6페이지"
        assigned = [{"item_id": "item_01", "input_path": str(self.pdf)}]
        res = prepare_batch(text, assigned, execute=True, confirm_execution=True,
                            confine=server._confined)
        self.assertEqual(res["status"], "pass", res)
        self.assertEqual(res["results"][0]["action"], "verify_existing")
        self.assertIsNone(res["results"][0]["output"])

    def test_rollback_later_processing_failure(self):
        # Force a failure AFTER the first JPG has been written, regardless
        # of how efficiently a blank PDF might compress on this pypdf version.
        with patch.object(server.core, "prepare_pdf", side_effect=ValueError("simulated PDF failure")):
            res = prepare_batch(NOTICE, self.assignments, execute=True,
                                confirm_execution=True, confine=server._confined)
        self.assertEqual(res["status"], "error", res)
        self.assertFalse(self.out_photo.exists(), "First output should be rolled back")
        self.assertFalse(self.out_pdf.exists(), "Second failed output must not persist")
        self.assertTrue(self.photo.exists())

    def test_outside_root_blocked(self):
        with tempfile.TemporaryDirectory() as ext:
            targets = [{**self.assignments[0], "output_path": str(Path(ext) / "outside.jpg")}, self.assignments[1]]
            res = prepare_batch(NOTICE, targets, execute=True,
                                confirm_execution=True, confine=server._confined)
            self.assertEqual(res["status"], "needs_review", res)
            self.assertFalse(self.out_pdf.exists())

    async def test_mcp_tool_listing_and_dry_run(self):
        async with Client(server.mcp) as client:
            listing = await client.list_tools()
            names = {t.name for t in listing.tools}
            self.assertIn("analyze_submission_notice", names)
            self.assertIn("prepare_submission_batch", names)
            self.assertEqual(len(names), 9)
            response = await client.call_tool("analyze_submission_notice", {"notice_text": NOTICE})
            self.assertFalse(response.is_error)
            self.assertEqual(response.structured_content["total_items"], 2)
            dry = await client.call_tool("prepare_submission_batch", {
                "notice_text": NOTICE, "assignments": self.assignments,
            })
            self.assertEqual(dry.structured_content["status"], "planned")
            self.assertFalse(self.out_photo.exists())

    async def test_stdio_discovery_and_notice_parse(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "scripts" / "mcp_server.py")],
            env={"JECHULOK_ALLOWED_DIRS": str(self.root)},
        )
        async with Client(params) as client:
            listing = await client.list_tools()
            self.assertEqual(len(listing.tools), 9)
            response = await client.call_tool("analyze_submission_notice", {"notice_text": NOTICE})
            self.assertEqual(response.structured_content["status"], "parsed")


if __name__ == "__main__":
    unittest.main()

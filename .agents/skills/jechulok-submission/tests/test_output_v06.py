"""v0.6 output path suggestions, technical summaries and MCP transport tests."""
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
from notice_batch import prepare_batch
from output_planner import suggest_output_paths

NOTICE = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"


class V06OutputTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / "output"
        self.output.mkdir()
        self.image = self.root / "original.png"
        Image.new("RGB", (600, 450), "#336699").save(self.image)
        self.pdf = self.root / "original.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=300, height=400)
        with self.pdf.open("wb") as fp:
            writer.write(fp)
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        self.matches = [
            {"item_id": "item_01", "input_path": str(self.image)},
            {"item_id": "item_02", "input_path": str(self.pdf), "pages_to_extract": "1-3"},
        ]

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def suggest(self, matches=None, output=None, notice=NOTICE):
        return suggest_output_paths(
            notice, self.matches if matches is None else matches,
            str(self.output if output is None else output),
            confine=server._confined,
            confine_directory=server._confined_directory,
        )

    def test_read_only_proposal_with_conflict_avoidance(self):
        existing = self.output / "제출용_증명사진.jpg"
        existing.write_bytes(b"keep-existing")
        before = {path.name for path in self.output.iterdir()}
        result = self.suggest()
        self.assertEqual(result["status"], "suggestions_only", result)
        self.assertEqual(result["summary"]["files_created"], 0)
        self.assertEqual(result["summary"]["technically_verified"], 0)
        self.assertEqual(result["summary"]["total_items"], 2)
        photo, resume = result["proposals"]
        self.assertTrue(photo["suggested_output_path"].endswith("제출용_증명사진_2.jpg"))
        self.assertTrue(resume["suggested_output_path"].endswith("제출용_이력서.pdf"))
        self.assertTrue(photo["requires_user_approval"])
        self.assertEqual(before, {path.name for path in self.output.iterdir()})
        self.assertEqual(existing.read_bytes(), b"keep-existing")

    def test_pdf_without_selected_pages_requests_review(self):
        matches = [self.matches[0], {"item_id": "item_02", "input_path": str(self.pdf)}]
        result = self.suggest(matches)
        self.assertEqual(result["status"], "needs_review")
        item = result["proposals"][1]
        self.assertEqual(item["action"], "select_pdf_pages")
        self.assertTrue(item["requires_page_selection"])
        self.assertEqual(result["summary"]["need_attention"], 1)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_compliant_pdf_is_verified_without_new_name(self):
        notice = "- 이력서: PDF 5MB 이하, 최대 6페이지"
        result = self.suggest(
            [{"item_id": "item_01", "input_path": str(self.pdf)}],
            notice=notice,
        )
        self.assertEqual(result["status"], "suggestions_only", result)
        self.assertEqual(result["proposals"][0]["action"], "verify_existing")
        self.assertIsNone(result["proposals"][0]["suggested_output_path"])

    def test_no_guessing_bad_input_or_unassigned_notice(self):
        result = self.suggest(self.matches[:1])
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["proposals"], [])
        bad = self.suggest(notice=NOTICE + "\n공통조건 PDF 2MB 이하")
        self.assertEqual(bad["status"], "needs_review")
        self.assertEqual(bad["proposals"], [])
        swapped = [
            {"item_id": "item_01", "input_path": str(self.pdf)},
            {"item_id": "item_02", "input_path": str(self.image)},
        ]
        self.assertEqual(self.suggest(swapped)["status"], "needs_review")

    def test_path_restrictions_and_symlinks(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(ValueError):
                self.suggest(output=outside)
        try:
            alias = self.root / "alias"
            alias.symlink_to(self.output, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(ValueError):
            self.suggest(output=alias)

    def test_batch_dryrun_and_verified_summary(self):
        assignments = [
            {**self.matches[0], "output_path": str(self.output / "photo-ready.jpg")},
            {**self.matches[1], "output_path": str(self.output / "resume-ready.pdf")},
        ]
        dry = prepare_batch(NOTICE, assignments, confine=server._confined)
        self.assertEqual(dry["status"], "planned")
        summary = dry["summary"]
        self.assertEqual(summary["not_verified"], 2)
        self.assertEqual(summary["generated_files"], 0)
        self.assertEqual([x["technical_status"] for x in summary["items"]],
                         ["planned", "planned"])
        self.assertFalse(summary["institutional_submission_confirmed"])
        hold = prepare_batch(NOTICE, assignments, execute=True, confine=server._confined)
        self.assertEqual(hold["status"], "needs_confirmation")
        self.assertEqual(hold["summary"]["items"][0]["technical_status"], "awaiting_confirmation")
        self.assertEqual(list(self.output.iterdir()), [])
        done = prepare_batch(NOTICE, assignments, execute=True,
                             confirm_execution=True, confine=server._confined)
        self.assertEqual(done["status"], "pass", done)
        self.assertEqual(done["summary"]["technically_verified"], 2)
        self.assertEqual(done["summary"]["generated_files"], 2)
        self.assertEqual(done["summary"]["not_verified"], 0)
        self.assertEqual([x["technical_status"] for x in done["summary"]["items"]],
                         ["verified", "verified"])
        self.assertTrue(done["summary"]["manual_review_required"])
        self.assertFalse(done["summary"]["institutional_submission_confirmed"])
        self.assertTrue(self.image.exists())
        self.assertTrue(self.pdf.exists())

    def test_batch_blocked_summary(self):
        assignments = [
            {**self.matches[0], "output_path": str(self.output / "ready.jpg")},
            {**self.matches[1], "output_path": str(self.output / "ready.pdf")},
        ]
        (self.output / "ready.pdf").write_bytes(b"leave-alone")
        blocked = prepare_batch(NOTICE, assignments, confine=server._confined)
        self.assertEqual(blocked["status"], "needs_review")
        self.assertEqual(blocked["summary"]["blocked_items"], 1)
        self.assertEqual(blocked["summary"]["generated_files"], 0)
        self.assertEqual((self.output / "ready.pdf").read_bytes(), b"leave-alone")

    def test_output_planner_mcp_tool(self):
        result = server.suggest_submission_output_paths(NOTICE, self.matches, str(self.output))
        self.assertEqual(result["status"], "suggestions_only")

    async def test_mcp_registration_and_invocation(self):
        async with Client(server.mcp) as client:
            listing = await client.list_tools()
            names = {entry.name for entry in listing.tools}
            self.assertEqual(len(names), 10)
            self.assertIn("suggest_submission_output_paths", names)
            response = await client.call_tool("suggest_submission_output_paths", {
                "notice_text": NOTICE, "assignments": self.matches,
                "output_directory": str(self.output),
            })
            self.assertFalse(response.is_error)
            self.assertEqual(response.structured_content["status"], "suggestions_only")

    async def test_real_stdio_transport(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "scripts" / "mcp_server.py")],
            env={"JECHULOK_ALLOWED_DIRS": str(self.root)},
        )
        async with Client(params) as client:
            names = {entry.name for entry in (await client.list_tools()).tools}
            self.assertIn("suggest_submission_output_paths", names)


if __name__ == "__main__":
    unittest.main()

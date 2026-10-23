"""v1.0 real stdio acceptance path and fail-closed security regression tests.

Fixtures are synthetic images/blank PDFs; no personal data, uploads or network.
"""
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

import jechulok as core
import mcp_server as server
import notice_batch
from notice_batch import prepare_batch

NOTICE = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"


class ReleaseV10Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        self.image = self.root / "증명사진.png"
        Image.new("RGB", (600, 450), "#1675a6").save(self.image)
        self.pdf = self.root / "이력서.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=250, height=350)
        with self.pdf.open("wb") as fp:
            writer.write(fp)
        self.photo_ready = self.root / "제출용_증명사진.jpg"
        self.pdf_ready = self.root / "제출용_이력서.pdf"
        self.html_ready = self.root / "검증보고서.html"
        self.assignments = [
            {"item_id": "item_01", "input_path": str(self.image),
             "output_path": str(self.photo_ready)},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.pdf_ready), "pages_to_extract": "1-3"},
        ]
        self.final_files = [
            {"item_id": "item_01", "file_path": str(self.photo_ready)},
            {"item_id": "item_02", "file_path": str(self.pdf_ready)},
        ]

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _mcp(self):
        return StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "scripts" / "mcp_server.py")],
            env={"JECHULOK_ALLOWED_DIRS": str(self.root)},
        )

    async def test_full_end_to_end_stdio_protocol(self):
        """One real child process, discovery -> approvals -> prepare -> receipt-free verification."""
        async with Client(self._mcp()) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            self.assertEqual(len(names), 20)
            notice = await client.call_tool("analyze_submission_notice", {
                "notice_text": NOTICE
            })
            self.assertFalse(notice.is_error)
            self.assertEqual(notice.structured_content["total_items"], 2)

            candidates = await client.call_tool("suggest_submission_files", {
                "notice_text": NOTICE, "directory_path": str(self.root),
            })
            self.assertFalse(candidates.is_error)
            self.assertEqual(candidates.structured_content["status"], "suggestions_only")

            suggestions = await client.call_tool("suggest_submission_output_paths", {
                "notice_text": NOTICE, "assignments": [
                    {"item_id": "item_01", "input_path": str(self.image)},
                    {"item_id": "item_02", "input_path": str(self.pdf), "pages_to_extract": "1-3"},
                ], "output_directory": str(self.root),
            })
            self.assertFalse(suggestions.is_error)
            self.assertEqual(suggestions.structured_content["status"], "suggestions_only")

            review = await client.call_tool("review_submission_plan", {
                "notice_text": NOTICE, "assignments": self.assignments,
            })
            self.assertEqual(review.structured_content["status"], "awaiting_human_approval")
            self.assertFalse(review.structured_content["execution_permitted"])
            self.assertFalse(self.photo_ready.exists())

            plan = await client.call_tool("prepare_submission_batch", {
                "notice_text": NOTICE, "assignments": self.assignments,
            })
            self.assertEqual(plan.structured_content["status"], "planned")
            self.assertFalse(self.photo_ready.exists())

            no_permission = await client.call_tool("prepare_submission_batch", {
                "notice_text": NOTICE, "assignments": self.assignments,
                "execute": True, "confirm_execution": False,
            })
            self.assertEqual(no_permission.structured_content["status"], "needs_confirmation")
            self.assertFalse(self.photo_ready.exists())

            # Test fixture explicitly grants both flags for the exact plan;
            # a real agent must separately obtain explicit human authorization.
            executed = await client.call_tool("prepare_submission_batch", {
                "notice_text": NOTICE, "assignments": self.assignments,
                "execute": True, "confirm_execution": True,
            })
            self.assertFalse(executed.is_error)
            self.assertEqual(executed.structured_content["status"], "pass", executed.structured_content)
            self.assertEqual(executed.structured_content["summary"]["generated_files"], 2)
            self.assertTrue(self.image.exists())
            self.assertTrue(self.pdf.exists())

            verified = await client.call_tool("verify_submission_package", {
                "notice_text": NOTICE, "files": self.final_files,
            })
            self.assertEqual(verified.structured_content["status"], "technical_pass")
            self.assertFalse(verified.structured_content["ready_to_submit"])
            self.assertFalse(verified.structured_content["institutional_submission_confirmed"])

            preview = await client.call_tool("create_submission_html_report", {
                "notice_text": NOTICE, "files": self.final_files,
                "output_path": str(self.html_ready),
            })
            self.assertEqual(preview.structured_content["status"], "preview")
            self.assertFalse(self.html_ready.exists())

            approved = await client.call_tool("create_submission_html_report", {
                "notice_text": NOTICE, "files": self.final_files,
                "output_path": str(self.html_ready),
                "execute": True, "confirm_execution": True,
            })
            self.assertEqual(approved.structured_content["status"], "report_created")
            html = self.html_ready.read_text("utf-8")
            self.assertNotIn(str(self.root), html)
            self.assertNotIn("<script", html)
            self.assertIn("접수 완료 증명이 아닙니다", html)
            self.assertTrue(self.photo_ready.is_file())
            self.assertTrue(self.pdf_ready.is_file())
            self.assertEqual(len(list(self.root.glob("*.html"))), 1)

    def test_symlinked_parent_inside_root_is_rejected(self):
        folder = self.root / "docs"
        folder.mkdir()
        target = folder / "file.png"
        Image.new("RGB", (20, 20)).save(target)
        alias = self.root / "alias"
        try:
            alias.symlink_to(folder, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unsupported by OS")
        with self.assertRaises(ValueError):
            server._confined(str(alias / "file.png"))
        with self.assertRaises(ValueError):
            server._confined(str(alias / "ready.jpg"), for_output=True)
        with self.assertRaises(ValueError):
            server._confined_directory(str(alias))

    def test_dotdot_alias_inside_root_is_rejected(self):
        child = self.root / "child"
        child.mkdir()
        raw = str(child / ".." / self.image.name)
        with self.assertRaises(ValueError):
            server._confined(raw)
        with self.assertRaises(ValueError):
            server._confined(str(child / ".." / "ready.jpg"), for_output=True)

    def test_unknown_extension_and_corrupt_image_do_not_pass(self):
        fake_ext = self.root / "misnamed.txt"
        fake_ext.write_bytes(self.image.read_bytes())
        extension = core.evaluation(core.info_for(fake_ext), expected_format="png")
        self.assertEqual(extension["status"], "unverified")
        self.assertIn("extension_matches_content", {check["rule"] for check in extension["checks"]})
        broken = self.root / "broken.jpg"
        broken.write_bytes(b"\xff\xd8\xff" + b"malformed content not decodable")
        report = core.evaluation(core.info_for(broken), expected_format="jpg")
        self.assertNotEqual(report["status"], "pass")
        self.assertIn("file_integrity", {check["rule"] for check in report["checks"]})

    def test_batch_rechecks_inputs_after_preflight_and_rolls_back(self):
        """A source replaced with symlink between two operations cannot escape root."""
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "other.pdf"
            external.write_bytes(self.pdf.read_bytes())
            original_prepare = notice_batch.core.prepare_image

            def replacement(source, args):
                outcome = original_prepare(source, args)
                self.pdf.rename(self.root / "original-stashed.pdf")
                self.pdf.symlink_to(external)
                return outcome

            with patch.object(notice_batch.core, "prepare_image", side_effect=replacement):
                result = prepare_batch(NOTICE, self.assignments, execute=True,
                                       confirm_execution=True, confine=server._confined)
            self.assertEqual(result["status"], "error", result)
            self.assertFalse(self.photo_ready.exists())
            self.assertFalse(self.pdf_ready.exists())
            self.assertTrue((self.root / "original-stashed.pdf").exists())

    def test_failed_second_output_rolls_back_and_keeps_originals(self):
        import notice_batch as batch
        original = batch.core.prepare_pdf

        def fail_second(src, args):
            raise ValueError("Simulated PDF processing failure")
        with patch.object(batch.core, "prepare_pdf", side_effect=fail_second):
            result = prepare_batch(NOTICE, self.assignments, execute=True,
                                   confirm_execution=True, confine=server._confined)
        self.assertEqual(result["status"], "error")
        self.assertFalse(self.photo_ready.exists())
        self.assertFalse(self.pdf_ready.exists())
        self.assertTrue(self.image.exists())
        self.assertTrue(self.pdf.exists())


if __name__ == "__main__":
    unittest.main()

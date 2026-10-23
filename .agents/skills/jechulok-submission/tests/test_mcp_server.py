"""MCP v0.2 security and integration tests (the real MCP SDK is required)."""
from __future__ import annotations

import asyncio
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
import mcp_server as server  # noqa: E402


class MCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name).resolve()
        self.png = self.root / "sample.png"
        Image.new("RGB", (640, 480), "#3671ac").save(self.png)
        self.pdf = self.root / "sample.pdf"
        w = PdfWriter()
        for _ in range(7):
            w.add_blank_page(width=200, height=300)
        with self.pdf.open("wb") as fp:
            w.write(fp)
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.folder.cleanup()

    async def test_server_exposes_six_named_tools(self):
        async with Client(server.mcp) as client:
            listing = await client.list_tools()
            names = {item.name for item in listing.tools}
            self.assertEqual(names, {"check_file", "prepare_image", "extract_pdf_pages", "verify_submission", "parse_submission_rules", "prepare_from_requirements", "analyze_submission_notice", "prepare_submission_batch", "suggest_submission_files", "suggest_submission_output_paths", "review_submission_plan", "verify_submission_package", "guide_submission_workflow", "create_submission_html_report"})
            self.assertIsNotNone(next(x for x in listing.tools if x.name == "prepare_image").input_schema)

    async def test_real_stdio_transport(self):
        """Connect through the same child-process transport as an AI host."""
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "scripts" / "mcp_server.py")],
            env={"JECHULOK_ALLOWED_DIRS": str(self.root)},
        )
        async with Client(params) as client:
            tools = await client.list_tools()
            self.assertEqual(len(tools.tools), 14)
            response = await client.call_tool("check_file", {
                "input_path": str(self.pdf),
                "expected_format": "pdf",
                "max_pages": 7,
            })
            self.assertFalse(response.is_error)
            self.assertEqual(response.structured_content["status"], "pass")

    async def test_tool_check_and_verification(self):
        async with Client(server.mcp) as client:
            result = await client.call_tool("check_file", {
                "input_path": str(self.png), "expected_format": "png", "width": 640, "height": 480,
            })
            self.assertFalse(result.is_error)
            self.assertEqual(result.structured_content["status"], "pass")
            wrong = await client.call_tool("verify_submission", {
                "input_path": str(self.png), "expected_format": "jpg",
            })
            self.assertEqual(wrong.structured_content["status"], "fail")
            unspecified = await client.call_tool("verify_submission", {"input_path": str(self.png)})
            self.assertEqual(unspecified.structured_content["status"], "error")

    async def test_prepare_image_and_reverify(self):
        dest = self.root / "ready.jpg"
        async with Client(server.mcp) as client:
            result = await client.call_tool("prepare_image", {
                "input_path": str(self.png), "output_path": str(dest), "width": 300,
                "height": 400, "max_kb": 500, "mode": "contain",
            })
            self.assertEqual(result.structured_content["status"], "pass")
            check = await client.call_tool("verify_submission", {
                "input_path": str(dest), "expected_format": "jpg", "width": 300, "height": 400, "max_kb": 500,
            })
            self.assertEqual(check.structured_content["status"], "pass")
            self.assertTrue(dest.exists())
            self.assertTrue(self.png.exists())
            overwrite = await client.call_tool("prepare_image", {
                "input_path": str(self.png), "output_path": str(dest),
            })
            self.assertEqual(overwrite.structured_content["status"], "error")

    async def test_pdf_extract_and_reverify(self):
        dest = self.root / "selected.pdf"
        async with Client(server.mcp) as client:
            result = await client.call_tool("extract_pdf_pages", {
                "input_path": str(self.pdf), "output_path": str(dest),
                "pages": "2-4,7", "max_pages": 4,
            })
            self.assertEqual(result.structured_content["status"], "pass")
            self.assertEqual(result.structured_content["selected_pages"], [2, 3, 4, 7])
            verification = await client.call_tool("verify_submission", {
                "input_path": str(dest), "expected_format": "pdf", "max_pages": 4,
            })
            self.assertEqual(verification.structured_content["status"], "pass")
            self.assertEqual(verification.structured_content["file"]["pages"], 4)

    async def test_crop_requires_user_approval(self):
        dest = self.root / "crop.jpg"
        async with Client(server.mcp) as client:
            not_approved = await client.call_tool("prepare_image", {
                "input_path": str(self.png), "output_path": str(dest),
                "width": 300, "height": 400, "mode": "cover",
            })
            self.assertEqual(not_approved.structured_content["status"], "error")
            self.assertFalse(dest.exists())
            approved = await client.call_tool("prepare_image", {
                "input_path": str(self.png), "output_path": str(dest),
                "width": 300, "height": 400, "mode": "cover", "crop_approved": True,
            })
            self.assertEqual(approved.structured_content["status"], "pass")

    async def test_reject_outside_root_and_symlink(self):
        with tempfile.TemporaryDirectory() as outside:
            evil = Path(outside) / "secret.png"
            Image.new("RGB", (20, 20), "black").save(evil)
            link = self.root / "fake.png"
            try:
                link.symlink_to(evil)
            except (NotImplementedError, OSError):
                link = None
            async with Client(server.mcp) as client:
                result = await client.call_tool("check_file", {"input_path": str(evil)})
                self.assertEqual(result.structured_content["status"], "error")
                self.assertIn("outside", result.structured_content["message"])
                if link:
                    result = await client.call_tool("check_file", {"input_path": str(link)})
                    self.assertEqual(result.structured_content["status"], "error")
                escaped = await client.call_tool("prepare_image", {
                    "input_path": str(self.png), "output_path": str(Path(outside) / "out.jpg"),
                })
                self.assertEqual(escaped.structured_content["status"], "error")

    async def test_reject_invalid_rules_and_pages(self):
        async with Client(server.mcp) as client:
            negative = await client.call_tool("check_file", {"input_path": str(self.png), "max_kb": -1})
            # Schema-level rejection or application-level rejection is acceptable.
            self.assertTrue(negative.is_error or negative.structured_content.get("status") == "error")
            invalid = await client.call_tool("extract_pdf_pages", {
                "input_path": str(self.pdf), "output_path": str(self.root / "invalid.pdf"), "pages": "9",
            })
            self.assertEqual(invalid.structured_content["status"], "error")
            self.assertFalse((self.root / "invalid.pdf").exists())


if __name__ == "__main__":
    unittest.main()

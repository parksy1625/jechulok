"""JeChulOK v0.5 read-only candidate hints and security regression checks."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server as server

NOTICE = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"


class CandidateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        (self.root / "증명사진_original.png").write_bytes(b"not a real image")
        (self.root / "지원_이력서.pdf").write_bytes(b"not a real PDF")
        (self.root / "random.pdf").write_bytes(b"%PDF-unknown")
        (self.root / "ignored.docx").write_bytes(b"doc")
        (self.root / "folder").mkdir()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_correct_hints_without_opening_files_or_writes(self):
        from file_candidates import suggest_files
        before = {p.name for p in self.root.iterdir()}
        result = suggest_files(NOTICE, str(self.root),
                               confine_directory=server._confined_directory)
        self.assertEqual(result["status"], "suggestions_only", result)
        self.assertEqual(len(result["items"]), 2)
        photo = result["items"][0]["candidates"][0]
        resume = result["items"][1]["candidates"][0]
        self.assertEqual(photo["filename"], "증명사진_original.png")
        self.assertEqual(resume["filename"], "지원_이력서.pdf")
        self.assertEqual(photo["match_type"], "filename_keyword")
        self.assertTrue(photo["requires_manual_review"])
        self.assertTrue(all(p["extension"] in {".pdf"} for p in result["items"][1]["candidates"]))
        self.assertEqual(before, {p.name for p in self.root.iterdir()})
        self.assertEqual(result["items"][1]["total_compatible_files"], 2)

    def test_no_auto_match_with_filename_only(self):
        from file_candidates import suggest_files
        for filename in ("증명사진_original.png", "지원_이력서.pdf"):
            (self.root / filename).unlink()
        result = suggest_files(NOTICE, str(self.root),
                               confine_directory=server._confined_directory)
        self.assertEqual(result["status"], "no_candidates")
        self.assertEqual(result["items"][0]["candidates"], [])
        self.assertEqual(result["items"][1]["candidates"][0]["priority"], "unknown")
        self.assertTrue(result["items"][1]["review_required"])

    def test_ambiguous_notice_always_needs_review(self):
        from file_candidates import suggest_files
        text = NOTICE + "\n공통 제출 규격 PDF 2MB 이하"
        result = suggest_files(text, str(self.root),
                               confine_directory=server._confined_directory)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["notice_status"], "needs_review")

    def test_symlink_directory_and_files_are_not_scanned(self):
        from file_candidates import suggest_files
        try:
            (self.root / "fake_이력서.pdf").symlink_to(self.root / "random.pdf")
            (self.root / "linked").symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("No symlink support")
        result = suggest_files(NOTICE, str(self.root),
                               confine_directory=server._confined_directory)
        self.assertTrue(all(c["filename"] != "fake_이력서.pdf"
                            for item in result["items"] for c in item["candidates"]))
        with self.assertRaises(ValueError):
            server._confined_directory(str(self.root / "linked"))

    def test_outside_allowed_folder_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            result = server.suggest_submission_files(NOTICE, outside)
        self.assertEqual(result["status"], "error")

    def test_max_250_nonrecursive_entries(self):
        from file_candidates import suggest_files
        subdir = self.root / "folder"
        (subdir / "졸업_증명사진.png").touch()
        for i in range(260):
            (self.root / f"unrelated_{i:03}.txt").touch()
        result = suggest_files(NOTICE, str(self.root),
                               confine_directory=server._confined_directory)
        self.assertLessEqual(result["scanned_entries"], 250)
        self.assertTrue(result["truncated"])
        self.assertTrue(all("졸업_증명사진" not in c["filename"]
                            for item in result["items"] for c in item["candidates"]))

    async def test_mcp_registration_and_invocation(self):
        async with Client(server.mcp) as client:
            listing = await client.list_tools()
            names = {tool.name for tool in listing.tools}
            self.assertEqual(len(names), 20)
            self.assertIn("suggest_submission_files", names)
            response = await client.call_tool(
                "suggest_submission_files",
                {"notice_text": NOTICE, "directory_path": str(self.root)},
            )
            self.assertFalse(response.is_error)
            self.assertEqual(response.structured_content["status"], "suggestions_only")

    async def test_stdio_tool_available(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "scripts" / "mcp_server.py")],
            env={"JECHULOK_ALLOWED_DIRS": str(self.root)},
        )
        async with Client(params) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            self.assertIn("suggest_submission_files", names)


if __name__ == "__main__":
    unittest.main()

"""v1.7 user experience: fewer questions, safer hints, specific error evidence."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client, StdioServerParameters
from PIL import Image
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import background_jobs
import mcp_server as server
from guided_clarity import notice_issues, explain_plan_blockers, missing_file_choices
from submission_assistant import assist

NOTICE = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"


class GuideClarityV17Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        self.img = self.root / "증명사진_original.png"
        Image.new("RGB", (600, 800), "white").save(self.img)
        self.pdf = self.root / "이력서_제출.pdf"
        writer = PdfWriter()
        for _ in range(4):
            writer.add_blank_page(width=210, height=297)
        with self.pdf.open("wb") as f:
            writer.write(f)
        self.jobs = background_jobs.LocalJobManager(journal_root=self.root / ".jechulok-jobs")
        self.assignments = [
            {"item_id": "item_01", "input_path": str(self.img),
             "output_path": str(self.root / "ready.jpg")},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.root / "ready.pdf"), "pages_to_extract": "1-3"},
        ]

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def guided(self, **kwargs):
        return assist(confine=server._confined, confine_directory=server._confined_directory,
                      jobs=self.jobs, **kwargs)

    def test_all_missing_items_in_single_prompt_and_no_scan_default(self):
        with patch("guided_clarity.suggest_files", side_effect=AssertionError("unexpected scan")):
            result = self.guided(notice_text=NOTICE)
        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["workflow"]["next_action"], "choose_source")
        self.assertEqual(result["file_selection"]["missing_count"], 2)
        self.assertEqual([x["item_id"] for x in result["file_selection"]["items"]],
                         ["item_01", "item_02"])
        self.assertIn("2개", result["workflow"]["question"])
        self.assertFalse(result["file_selection"]["directory_scan_requested"])
        self.assertFalse(result["file_selection"]["auto_assign"])
        self.assertFalse((self.root / ".jechulok-jobs").exists())

    def test_explicit_folder_returns_ranked_hints_without_assigning(self):
        previous = sorted(p.name for p in self.root.iterdir())
        result = self.guided(notice_text=NOTICE, source_directory=str(self.root))
        hints = result["file_selection"]
        self.assertTrue(hints["directory_scan_requested"])
        self.assertEqual(hints["missing_count"], 2)
        self.assertEqual(hints["items"][0]["candidate_hints"][0]["filename"], self.img.name)
        self.assertEqual(hints["items"][1]["candidate_hints"][0]["filename"], self.pdf.name)
        self.assertEqual(hints["items"][0]["candidate_hints"][0]["match_type"], "filename_keyword")
        self.assertTrue(all(
            item["requires_explicit_user_selection"] for item in hints["items"]
        ))
        self.assertFalse(hints["auto_assign"])
        self.assertEqual(previous, sorted(p.name for p in self.root.iterdir()))
        self.assertFalse(self.jobs._jobs)

    def test_partial_assignment_suggests_only_missing_item(self):
        result = self.guided(
            notice_text=NOTICE, assignments=[self.assignments[0]],
            source_directory=str(self.root),
        )
        self.assertEqual(result["file_selection"]["missing_count"], 1)
        self.assertEqual(result["file_selection"]["items"][0]["item_id"], "item_02")
        self.assertEqual(result["guidance"]["item_id"], "item_02")

    def test_no_scan_for_complete_plan_even_if_directory_requested(self):
        with patch("guided_clarity.suggest_files", side_effect=AssertionError("scan")):
            result = self.guided(
                notice_text=NOTICE, assignments=self.assignments,
                source_directory=str(self.root),
            )
        self.assertEqual(result["workflow"]["next_action"], "approve_exact_plan")
        self.assertEqual(len(result["approval_fingerprint"]), 64)
        self.assertFalse((self.root / "ready.jpg").exists())

    def test_outside_directory_and_symlinked_directory_are_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaisesRegex(ValueError, "outside"):
                # macOS temporary folders often have /var -> /private/var
                # aliases; canonicalize to test the outside-root rule.
                self.guided(notice_text=NOTICE, source_directory=str(Path(outside).resolve()))
        linked = self.root / "linked"
        try:
            linked.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink not supported")
        with self.assertRaises(ValueError):
            self.guided(notice_text=NOTICE, source_directory=str(linked))

    def test_ambiguous_rules_show_grounded_evidence_without_scanning(self):
        text = NOTICE + "\n공통 제출 규격 PDF 2MB 이하"
        with patch("guided_clarity.suggest_files", side_effect=AssertionError("scan")):
            result = self.guided(notice_text=text, source_directory=str(self.root))
        self.assertEqual(result["workflow"]["next_action"], "clarify_notice")
        self.assertEqual(result["notice_explanation"]["issue_count"], 1)
        self.assertEqual(result["notice_explanation"]["issues"][0]["line"], 3)
        self.assertEqual(result["notice_explanation"]["issues"][0]["code"], "unassigned_condition")
        self.assertFalse(result["notice_explanation"]["files_modified"])

    def test_duplicate_document_type_needs_human_decision(self):
        text = "- 증명사진: JPG 300×400px 500KB 이하\n- 증명사진: JPG 300×400px 500KB 이하"
        explanation = notice_issues(text)
        self.assertEqual(explanation["status"], "needs_review")
        self.assertEqual(explanation["issues"][0]["code"], "duplicate_document_type")
        self.assertEqual(explanation["issues"][0]["line"], 2)

    def test_multiple_notice_issues_are_bounded_and_ordered(self):
        text = NOTICE + "".join(f"\n공통 조건 PDF {i}KB 이하" for i in range(14))
        explanation = notice_issues(text)
        self.assertEqual(explanation["issue_count"], 14)
        self.assertEqual(len(explanation["issues"]), 5)
        self.assertTrue(explanation["truncated"])
        self.assertEqual(explanation["issues"][0]["line"], 3)

    def test_invalid_pdf_has_specific_preflight_remedy(self):
        invalid = [dict(x) for x in self.assignments]
        invalid[1].pop("pages_to_extract")
        invalid[1].pop("output_path")
        result = self.guided(notice_text=NOTICE, assignments=invalid)
        self.assertEqual(result["workflow"]["next_action"], "fix_plan")
        self.assertEqual(result["problem_explanation"]["issue_count"], 1)
        self.assertEqual(result["problem_explanation"]["issues"][0]["code"], "pdf_pages")
        self.assertFalse(result["problem_explanation"]["auto_fix"])
        self.assertFalse((self.root / "ready.jpg").exists())

    def test_start_with_bad_plan_is_readonly_even_when_approved_flags_true(self):
        invalid = [dict(x) for x in self.assignments]
        invalid[1].pop("pages_to_extract")
        result = self.guided(
            action="start", notice_text=NOTICE, assignments=invalid,
            execute=True, confirm_execution=True, approval_fingerprint="1" * 64,
        )
        self.assertEqual(result["status"], "needs_review")
        self.assertTrue(result["problem_explanation"]["issues"])
        self.assertFalse((self.root / "ready.jpg").exists())
        self.assertFalse(self.jobs._jobs)

    def test_plan_remedy_mapping_is_bounded(self):
        result = explain_plan_blockers(
            [{"item_id": f"item_{i:02d}", "reason": "Output must be a new file"}
             for i in range(9)]
        )
        self.assertEqual(result["issue_count"], 9)
        self.assertEqual(len(result["issues"]), 5)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["issues"][0]["code"], "output_exists")
        self.assertFalse(result["execution_permitted"])


class GuideClarityRealMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_opt_in_candidate_scanning_default_no_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "photo.png").write_bytes(b"only a filename hint")
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(ROOT / "scripts" / "mcp_server.py")],
                env={"JECHULOK_ALLOWED_DIRS": str(root)},
            )
            async with Client(params) as client:
                tools = {t.name for t in (await client.list_tools()).tools}
                self.assertEqual(len(tools), 20)
                default = await client.call_tool(
                    "assist_submission", {"notice_text": NOTICE},
                )
                self.assertEqual(default.structured_content["file_selection"]["missing_count"], 2)
                self.assertFalse(default.structured_content["file_selection"]["directory_scan_requested"])
                opted_in = await client.call_tool(
                    "assist_submission", {"notice_text": NOTICE, "source_directory": str(root)},
                )
                self.assertTrue(opted_in.structured_content["file_selection"]["directory_scan_requested"])
                self.assertFalse(opted_in.structured_content["file_selection"]["auto_assign"])
                self.assertFalse((root / ".jechulok-jobs").exists())


if __name__ == "__main__":
    unittest.main()

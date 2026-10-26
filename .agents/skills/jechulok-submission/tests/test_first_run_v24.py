"""v2.4 real MCP guided UX behavior and privacy-safe status tests."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client, StdioServerParameters
from PIL import Image
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from first_run_ux_v24 import progress_view
from submission_assistant import assist
from background_jobs import LocalJobManager
import mcp_server

NOTICE = "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하 최대 3페이지"


class FirstRunUXV24Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        self.image = self.root / "private-family-photo.jpg"
        Image.new("RGB", (640, 480), "white").save(self.image)
        self.pdf = self.root / "private-cv.pdf"
        writer = PdfWriter()
        for _ in range(4):
            writer.add_blank_page(width=210, height=297)
        with self.pdf.open("wb") as file:
            writer.write(file)
        self.jobs = LocalJobManager(journal_root=self.root / ".jechulok-jobs")
        self.assignments = [
            {"item_id": "item_01", "input_path": str(self.image),
             "output_path": str(self.root / "prepared.jpg")},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.root / "prepared.pdf"), "pages_to_extract": "1-3"},
        ]

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def call(self, **kwargs):
        return assist(
            confine=mcp_server._confined,
            confine_directory=mcp_server._confined_directory,
            jobs=self.jobs, **kwargs,
        )

    def assert_ux_safe(self, answer):
        card = answer["experience"]
        self.assertEqual(card["schema"], 1)
        self.assertEqual(card["total_stages"], 5)
        self.assertEqual(card["current_stage"], answer["workflow"]["step"])
        self.assertEqual(card["next_action"], answer["workflow"]["next_action"])
        self.assertEqual(card["progress_percent"], (answer["workflow"]["step"] - 1) * 20)
        self.assertTrue(card["progress_is_only_step_indicator"])
        self.assertFalse(card["institutional_submission_verified"])
        self.assertFalse(card["data_transmitted"])
        self.assertFalse(card["telemetry_recorded"])
        self.assertFalse(card["automatic_file_selection"])
        self.assertFalse(card["independent_approval_inferred"])
        raw = json.dumps(card, ensure_ascii=False)
        for name in ("private-family-photo", "private-cv", str(self.root),
                     "prepared.jpg", "prepared.pdf", NOTICE):
            self.assertNotIn(name, raw)
        self.assertFalse((self.root / ".jechulok-jobs").exists())

    def test_missing_notice_prompts_once_without_filesystem_changes(self):
        answer = self.call()
        self.assert_ux_safe(answer)
        self.assertEqual(answer["experience"]["current_stage"], 1)
        self.assertEqual(answer["experience"]["next_action"], "provide_notice")
        self.assertFalse(answer["experience"]["requires_separate_human_approval"])

    def test_two_missing_files_become_one_grouped_request(self):
        answer = self.call(notice_text=NOTICE)
        self.assert_ux_safe(answer)
        self.assertEqual(answer["experience"]["outstanding_file_choices"], 2)
        self.assertEqual(len(answer["experience"]["file_choices"]), 2)
        self.assertEqual(answer["experience"]["file_choices"][0]["item_id"], "item_01")
        self.assertTrue(all(x["requires_explicit_user_selection"]
                            for x in answer["experience"]["file_choices"]))
        self.assertIn("2개", answer["workflow"]["question"])

    def test_partially_selected_files_only_request_remaining_one(self):
        answer = self.call(notice_text=NOTICE, assignments=self.assignments[:1])
        self.assert_ux_safe(answer)
        self.assertEqual(answer["experience"]["outstanding_file_choices"], 1)
        self.assertEqual(answer["experience"]["file_choices"][0]["item_id"], "item_02")

    def test_filenames_are_not_auto_selected_even_with_opt_in(self):
        answer = self.call(notice_text=NOTICE, source_directory=str(self.root))
        self.assert_ux_safe(answer)
        self.assertTrue(answer["file_selection"]["directory_scan_requested"])
        self.assertFalse(answer["file_selection"]["auto_assign"])
        self.assertFalse(answer["experience"]["automatic_file_selection"])

    def test_ambiguous_condition_is_not_counted_as_completed(self):
        bad = NOTICE + "\n공통 제출 규격 PDF 2MB 이하"
        answer = self.call(notice_text=bad)
        self.assert_ux_safe(answer)
        self.assertEqual(answer["experience"]["current_stage"], 1)
        self.assertEqual(answer["experience"]["unresolved_notice_or_plan_issues"], 1)
        self.assertIn("어떤 서류", answer["experience"]["next_step_help"])

    def test_unsupported_pdf_preflight_gets_human_repair(self):
        changed = [dict(x) for x in self.assignments]
        changed[1].pop("pages_to_extract")
        answer = self.call(notice_text=NOTICE, assignments=changed)
        self.assert_ux_safe(answer)
        self.assertEqual(answer["experience"]["current_stage"], 3)
        self.assertEqual(answer["experience"]["next_action"], "fix_plan")
        self.assertFalse(answer["experience"]["requires_separate_human_approval"])

    def test_complete_plan_still_requires_separate_explicit_approval(self):
        answer = self.call(notice_text=NOTICE, assignments=self.assignments)
        self.assert_ux_safe(answer)
        self.assertEqual(answer["status"], "awaiting_human_approval")
        self.assertTrue(answer["experience"]["requires_separate_human_approval"])
        self.assertEqual(len(answer["approval_fingerprint"]), 64)

    def test_start_without_actual_approval_cannot_write(self):
        answer = self.call(
            action="start", notice_text=NOTICE, assignments=self.assignments,
            execute=True, confirm_execution=False, approval_fingerprint="0" * 64,
        )
        self.assert_ux_safe(answer)
        self.assertEqual(answer["experience"]["next_action"], "approve_exact_plan")
        self.assertTrue(answer["experience"]["requires_separate_human_approval"])
        self.assertFalse((self.root / "prepared.jpg").exists())
        self.assertFalse((self.root / "prepared.pdf").exists())

    def test_wrong_approval_has_clear_changed_plan_action(self):
        answer = self.call(
            action="start", notice_text=NOTICE, assignments=self.assignments,
            execute=True, confirm_execution=True, approval_fingerprint="0" * 64,
        )
        self.assert_ux_safe(answer)
        self.assertEqual(answer["status"], "plan_changed")
        self.assertEqual(answer["experience"]["next_action"], "review_changed_plan")
        self.assertTrue(answer["experience"]["requires_separate_human_approval"])

    def test_status_and_verify_missing_information_still_have_progress(self):
        for args, action, step in [
            ({"action": "status"}, "provide_job_id", 4),
            ({"action": "verify", "notice_text": NOTICE}, "choose_final_files", 5),
        ]:
            answer = self.call(**args)
            self.assert_ux_safe(answer)
            self.assertEqual(answer["experience"]["next_action"], action)
            self.assertEqual(answer["experience"]["current_stage"], step)

    def test_unknown_stage_or_action_fails_closed(self):
        with self.assertRaises(ValueError):
            progress_view({"workflow": {"step": 2, "next_action": "auto_submit"}})
        with self.assertRaises(ValueError):
            progress_view({"workflow": {"step": 0, "next_action": "provide_notice"}})


class FirstRunUXRealMCPV24(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_assist_contains_privacy_safe_status_without_new_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(ROOT / "scripts" / "mcp_server.py")],
                env={"JECHULOK_ALLOWED_DIRS": str(root)},
            )
            async with Client(params) as client:
                listing = await client.list_tools()
                self.assertEqual(len(listing.tools), 20)
                output = await client.call_tool(
                    "assist_submission", {"notice_text": NOTICE},
                )
                self.assertFalse(output.is_error)
                self.assertEqual(output.structured_content["experience"]["outstanding_file_choices"], 2)
                self.assertFalse(output.structured_content["experience"]["telemetry_recorded"])
                self.assertFalse((root / ".jechulok-jobs").exists())


if __name__ == "__main__":
    unittest.main()

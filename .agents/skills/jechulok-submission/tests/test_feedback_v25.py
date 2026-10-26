"""v2.5 privacy-first feedback smoke, adversarial input and aggregate boundaries."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import feedback_v25 as feedback


class FeedbackV25Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.sentinel = self.root / "private-source.pdf"
        self.sentinel.write_bytes(b"not an actual PDF; leave untouched")

    def tearDown(self):
        self.tmp.cleanup()

    def capture(self, argv):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            exit_code = feedback.main(argv)
        return exit_code, json.loads(output.getvalue()), output.getvalue()

    def test_preview_is_readonly_needs_no_directory_and_never_uploads(self):
        before = {x.name for x in self.root.iterdir()}
        with patch.object(feedback, "save", side_effect=AssertionError("preview wrote")):
            code, result, text = self.capture([
                "preview", "--stage", "files", "--issue",
                "file_selection_confusing", "--impact", "minor",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "preview_only")
        self.assertEqual(result["feedback"]["schema"], feedback.SCHEMA)
        self.assertEqual(len(result["feedback"]), 4)
        self.assertFalse(result["saved"])
        self.assertFalse(result["uploaded"])
        self.assertEqual(before, {x.name for x in self.root.iterdir()})
        self.assertNotIn(str(self.root), text)

    def test_requires_explicit_local_destination_and_saves_minimal_0600(self):
        item = feedback.record("files", "file_selection_confusing", "minor")
        result = feedback.save(item, self.root)
        self.assertEqual(result["status"], "saved_locally")
        self.assertFalse(result["upload_performed"])
        files = list(self.root.glob("*" + feedback.SUFFIX))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text()), item)
        self.assertLessEqual(files[0].stat().st_size, feedback.MAX_FILE_BYTES)
        if os.name != "nt":
            self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
        for forbidden in ("path", "email", "notice", "timestamp", "user", "session"):
            self.assertNotIn(forbidden, json.dumps(item))
        self.assertEqual(self.sentinel.read_bytes(), b"not an actual PDF; leave untouched")
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_only_allowed_values_accepted_no_free_text_identifiers(self):
        invalid = [
            {"stage": "files", "issue": "look in /Users/alex/private",
             "impact": "blocked"},
            {"stage": "files", "issue": "worked_well", "impact": "minor",
             "email": "test@example.com"},
            {"stage": "files", "issue": "worked_well", "impact": "minor",
             "comment": "confidential job notice"},
            {"stage": "files", "issue": "worked_well", "impact": "1"},
            {"stage": "files", "issue": "worked_well", "impact": "minor",
             "time": "2026-10-26"},
        ]
        for i, entry in enumerate(invalid):
            with self.subTest(i=i):
                with self.assertRaises(ValueError):
                    feedback.check_record({"schema": feedback.SCHEMA, **entry})
        self.assertEqual(list(self.root.glob("*" + feedback.SUFFIX)), [])

    def test_symlinked_directory_and_existing_user_file_not_overwritten(self):
        alias = self.root.parent / (self.root.name + "-alias")
        try:
            alias.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            return  # Symlinks often require elevation on Windows.
        try:
            with self.assertRaises(ValueError):
                feedback.save(feedback.record("notice", "worked_well", "none"), alias)
        finally:
            alias.unlink()
        self.assertEqual(self.sentinel.read_bytes(), b"not an actual PDF; leave untouched")

    def test_fewer_than_five_never_shows_any_breakdown(self):
        for _ in range(4):
            feedback.save(feedback.record("files", "file_selection_confusing", "minor"), self.root)
        output = feedback.summary(self.root)
        self.assertEqual(output["status"], "insufficient_sample")
        self.assertIsNone(output["breakdown"])
        self.assertFalse(output["shareable_summary"])
        self.assertEqual(output["records"], 4)

    def test_five_entries_all_same_can_be_summarized_without_identifiers(self):
        for _ in range(5):
            feedback.save(feedback.record("notice", "unclear_technical_rule", "blocked"), self.root)
        result = feedback.summary(self.root)
        self.assertEqual(result["status"], "summarized")
        self.assertEqual(result["breakdown"]["issues"]["unclear_technical_rule"], 5)
        self.assertEqual(result["breakdown"]["stages"]["notice"], 5)
        self.assertEqual(result["breakdown"]["impacts"]["blocked"], 5)
        self.assertFalse(result["shareable_summary"])
        self.assertFalse(result["network_used"])
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_small_cells_suppressed_in_entire_dimension(self):
        for _ in range(3):
            feedback.save(feedback.record("notice", "unclear_technical_rule", "minor"), self.root)
        for _ in range(2):
            feedback.save(feedback.record("files", "file_selection_confusing", "blocked"), self.root)
        output = feedback.summary(self.root)
        for key in ("stages", "issues", "impacts"):
            self.assertIsNone(output["breakdown"][key])

    def test_corrupt_or_oversized_entries_rejected_without_content_leak(self):
        payload = self.root / ("entry-bad" + feedback.SUFFIX)
        payload.write_text('{"comment":"secret; mail me at foo@example.com"}', encoding="utf-8")
        with self.assertRaises(ValueError) as error:
            feedback.summary(self.root)
        self.assertNotIn("foo@example.com", str(error.exception))
        payload.write_bytes(b"x" * (feedback.MAX_FILE_BYTES + 1))
        with self.assertRaises(ValueError):
            feedback.summary(self.root)
        self.assertEqual(self.sentinel.read_bytes(), b"not an actual PDF; leave untouched")

    def test_symlinked_record_rejected_even_when_points_to_valid_json(self):
        target = self.root / "benign.txt"
        target.write_text(json.dumps(feedback.record("notice", "worked_well", "none")))
        link = self.root / ("entry-link" + feedback.SUFFIX)
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(ValueError):
            feedback.summary(self.root)
        self.assertEqual(target.read_text(), json.dumps(feedback.record("notice", "worked_well", "none")))

    def test_cli_save_and_summary_have_no_network_or_path_echo(self):
        cmd = [
            "save", "--stage", "plan", "--issue",
            "approval_confusing", "--impact", "blocked",
            "--output-dir", str(self.root),
        ]
        with patch("feedback_v25.os.open", wraps=os.open):
            code, output, raw = self.capture(cmd)
        self.assertEqual(code, 0)
        self.assertFalse(output["upload_performed"])
        self.assertNotIn(str(self.root), raw)
        code, report, raw = self.capture(["summary", "--directory", str(self.root)])
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "insufficient_sample")
        self.assertNotIn(str(self.root), raw)


if __name__ == "__main__":
    unittest.main()

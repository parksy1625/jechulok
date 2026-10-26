"""v3.1 real local pipeline rehearsal and explicit-consent regression tests."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import offline_demo_v31 as demo
from offline_demo_audit_v31 import run_audit
from jechulok import detect_format


class OfflineDemoV31Tests(unittest.TestCase):
    def test_synthetic_sources_have_correct_signatures(self):
        self.assertEqual(detect_format(demo._image_bytes()), "png")
        self.assertEqual(detect_format(demo._pdf_bytes()), "pdf")

    def test_full_real_conversion_and_verification(self):
        result = demo.run_rehearsal()
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(len(result["stages"]), 6)
        self.assertTrue(all(s["status"] == "pass" for s in result["stages"]))

    def test_names_are_stable_for_agent_consumption(self):
        self.assertEqual(demo.STAGES, ("requirements", "image_prepare",
                                       "image_recheck", "pdf_prepare", "pdf_recheck", "cleanup"))

    def test_repeated_runs_have_identical_safe_reports(self):
        self.assertEqual(demo.run_rehearsal(), demo.run_rehearsal())

    def test_does_not_return_local_paths_or_file_contents(self):
        report = json.dumps(demo.run_rehearsal(), ensure_ascii=False)
        self.assertNotIn(tempfile.gettempdir(), report)
        self.assertNotIn("invented-illustration.png", report)
        self.assertNotIn("prepared.jpg", report)
        self.assertNotIn("selected.pdf", report)

    def test_explicit_scope_flags_remain_false(self):
        report = demo.run_rehearsal()
        for key in ("personal_documents_read", "client_config_read", "network_used",
                    "telemetry_sent", "external_submission_attempted",
                    "institution_acceptance_verified", "outputs_persisted"):
            self.assertFalse(report[key])

    def test_preview_has_no_tempfile_side_effect(self):
        with (patch.object(demo.tempfile, "TemporaryDirectory",
                           side_effect=AssertionError("should not create files")),
              contextlib.redirect_stdout(io.StringIO()) as output):
            code = demo.main(["--format", "json"])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "not_run")

    def test_explicit_run_cli_returns_clean_json(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = demo.main(["--run", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "pass")

    def test_korean_text_is_accessible(self):
        report = demo.render_text(demo._base_report())
        self.assertIn("오프라인 가상 서류", report)
        self.assertIn("영구 출력 없음", report)
        self.assertNotIn("\x1b", report)

    def test_english_text(self):
        report = demo.render_text(demo._base_report(), language="en")
        self.assertIn("Offline Synthetic Rehearsal", report)
        self.assertIn("No personal documents", report)

    def test_unknown_language_fails(self):
        with self.assertRaises(ValueError):
            demo.render_text({}, language="fr")

    def test_invalid_cli_language_rejected(self):
        with (contextlib.redirect_stderr(io.StringIO()),
              self.assertRaises(SystemExit) as raised):
            demo.main(["--language", "fr"])
        self.assertEqual(raised.exception.code, 2)

    def test_required_files_are_always_exclusive(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic"
            demo._new_file(path, b"first")
            with self.assertRaises(FileExistsError):
                demo._new_file(path, b"second")
            self.assertEqual(path.read_bytes(), b"first")

    def test_source_requirements_error_does_not_escape(self):
        with patch.object(demo, "parse_requirements", side_effect=ValueError("private secret path")):
            report = demo.run_rehearsal()
        self.assertEqual(report["failure_stage"], "requirements")
        self.assertEqual(report["status"], "fail")
        self.assertNotIn("private secret path", json.dumps(report))

    def test_image_failure_does_not_escape(self):
        with patch.object(demo, "prepare_image", side_effect=RuntimeError("private secret path")):
            report = demo.run_rehearsal()
        self.assertEqual(report["failure_stage"], "image_prepare")
        self.assertEqual(report["stages"][-1]["status"], "pass")
        self.assertNotIn("private secret path", json.dumps(report))

    def test_pdf_failure_does_not_escape(self):
        with patch.object(demo, "prepare_pdf", side_effect=RuntimeError("private secret path")):
            report = demo.run_rehearsal()
        self.assertEqual(report["failure_stage"], "pdf_prepare")
        self.assertEqual(report["stages"][-1]["status"], "pass")
        self.assertNotIn("private secret path", json.dumps(report))

    def test_actual_temp_directory_is_removed_after_both_paths(self):
        original = tempfile.TemporaryDirectory
        created: list[Path] = []

        def capture(*args, **kwargs):
            temp = original(*args, **kwargs)
            created.append(Path(temp.name))
            return temp

        with patch.object(demo.tempfile, "TemporaryDirectory", side_effect=capture):
            self.assertEqual(demo.run_rehearsal()["status"], "pass")
            with patch.object(demo, "prepare_pdf", side_effect=OSError("secret")):
                self.assertEqual(demo.run_rehearsal()["status"], "fail")
        self.assertEqual(len(created), 2)
        self.assertFalse(any(path.exists() for path in created))

    def test_fail_closed_when_image_verdict_does_not_pass(self):
        with patch.object(demo, "evaluation", return_value={"status": "unverified"}):
            result = demo.run_rehearsal()
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["failure_stage"], "image_recheck")

    def test_audit_six_synthetic_scenarios(self):
        result = run_audit()
        self.assertEqual(result["scenario_count"], 6)
        self.assertEqual(result["passed_count"], 6, result)
        self.assertTrue(result["synthetic_only"])
        self.assertFalse(result["real_user_documents_tested"])


if __name__ == "__main__":
    unittest.main()

"""v3.0 single-screen local checkup and opt-in boundary tests."""
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

import setup_mcp
from first_run_checkup_v30 import checkup, render_text


def doctor(*bad: str) -> dict:
    names = ("skill_version", "source_manifest", "python_version",
             "allowed_directory", "directory_access", "server_script",
             "python_environment", "mcp_dependencies")
    return {
        "status": "pass" if not bad else "needs_setup",
        "checks": [{"id": x, "passed": x not in bad,
                    "verified": x == "source_manifest"}
                   for x in names],
    }


def probe_ok() -> dict:
    return {"status": "pass", "tool_count": 20}


def config_ok() -> dict:
    return {
        "status": "pass", "reason_code": "config_matches",
        "checks": {"command_matches": True, "args_match": True,
                   "allowed_directory_matches": True},
    }


class FirstRunV30Tests(unittest.TestCase):
    def test_default_gives_one_probe_step(self):
        r = checkup(doctor())
        self.assertEqual(r["status"], "next_step")
        self.assertEqual(r["next_action"], "opt_in_probe")
        self.assertEqual(r["stage"], 2)
        self.assertEqual(r["checks"]["local_mcp_probe"], "not_requested")
        self.assertEqual(r["checks"]["client_config"], "not_requested")
        self.assertFalse(r["mcp_host_registration_verified"])

    def test_broken_environment_has_priority_over_any_optional_check(self):
        r = checkup(doctor("source_manifest"), probe_requested=True,
                    config_requested=True)
        self.assertEqual(r["status"], "needs_setup")
        self.assertEqual(r["stage"], 1)
        self.assertEqual(r["reason_code"], "source_manifest")
        self.assertEqual(r["checks"]["local_mcp_probe"], "skipped_due_to_installation")
        self.assertEqual(r["checks"]["client_config"], "skipped_due_to_installation")
        self.assertIsNone(r["suggested_command"])

    def test_missing_python_prioritized_before_probe(self):
        r = checkup(doctor("python_environment", "mcp_dependencies"))
        self.assertEqual(r["reason_code"], "python_environment")
        self.assertEqual(r["next_action"], "install_dependencies")
        self.assertTrue("install" in r["suggested_command"])

    def test_optional_probe_timeout_stops_config_claims(self):
        r = checkup(doctor(), probe_requested=True,
                    probe={"status": "needs_attention", "code": "connection_timeout"},
                    config_requested=True, config=config_ok())
        self.assertEqual(r["status"], "needs_attention")
        self.assertEqual(r["next_action"], "review_probe")
        self.assertEqual(r["checks"]["client_config"], "pass")
        self.assertNotIn("connection_timeout", json.dumps(r))

    def test_probe_tool_count_mismatch_stops_progress(self):
        r = checkup(doctor(), probe_requested=True,
                    probe={"status": "pass", "tool_count": 19})
        self.assertEqual(r["checks"]["local_mcp_probe"], "needs_attention")
        self.assertEqual(r["stage"], 2)

    def test_probe_passes_but_config_missing_requests_optin(self):
        r = checkup(doctor(), probe_requested=True, probe=probe_ok(),
                    client="claude-desktop", language="en")
        self.assertEqual(r["next_action"], "opt_in_config_audit")
        self.assertEqual(r["stage"], 3)
        self.assertIn("--client claude-desktop", r["suggested_command"])
        self.assertNotIn("/tmp/", json.dumps(r))

    def test_config_only_never_claims_probe_passed(self):
        r = checkup(doctor(), config_requested=True, config=config_ok())
        self.assertEqual(r["checks"]["client_config"], "pass")
        self.assertEqual(r["checks"]["local_mcp_probe"], "not_requested")
        self.assertEqual(r["next_action"], "opt_in_probe")

    def test_config_mismatch_gives_safe_repair(self):
        r = checkup(doctor(), probe_requested=True, probe=probe_ok(),
                    config_requested=True,
                    config={"status": "needs_attention", "reason_code": "args_mismatch"},
                    client="cursor")
        self.assertEqual(r["stage"], 3)
        self.assertEqual(r["next_action"], "review_client_config")
        self.assertIn("--client cursor", r["suggested_command"])

    def test_both_pass_requires_manual_host_check(self):
        r = checkup(doctor(), probe_requested=True, probe=probe_ok(),
                    config_requested=True, config=config_ok())
        self.assertEqual(r["status"], "ready_for_manual_host_check")
        self.assertEqual(r["stage"], 4)
        self.assertEqual(r["next_action"], "manually_verify_host")
        self.assertIsNone(r["suggested_command"])
        self.assertFalse(r["submission_accepted_or_verified"])

    def test_crafted_fake_config_pass_without_checks_fails_closed(self):
        r = checkup(doctor(), probe_requested=True, probe=probe_ok(),
                    config_requested=True,
                    config={"status": "pass", "reason_code": "config_matches"})
        self.assertEqual(r["next_action"], "review_client_config")

    def test_false_check_value_is_not_truthy_pass(self):
        cfg = config_ok()
        cfg["checks"]["command_matches"] = 1
        r = checkup(doctor(), probe_requested=True, probe=probe_ok(),
                    config_requested=True, config=cfg)
        self.assertEqual(r["next_action"], "review_client_config")

    def test_no_implicit_consent_from_unrequested_observations(self):
        with self.assertRaises(ValueError):
            checkup(doctor(), probe=probe_ok())
        with self.assertRaises(ValueError):
            checkup(doctor(), config=config_ok())

    def test_unsupported_language_and_client_rejected(self):
        with self.assertRaises(ValueError):
            checkup(doctor(), client="bad")
        with self.assertRaises(ValueError):
            checkup(doctor(), language="bad")

    def test_plain_text_is_no_color_and_accessible(self):
        r = render_text(checkup(doctor(), language="ko"))
        self.assertIn("1. 설치: pass", r)
        self.assertIn("3. 클라이언트 설정: not_requested", r)
        self.assertIn("자동 실행 안 함", r)
        self.assertNotIn("\x1b", r)

    def test_english_plain_text(self):
        r = render_text(checkup(doctor(), language="en"))
        self.assertIn("First-run Checkup", r)
        self.assertIn("Step 2/4", r)
        self.assertIn("No configuration changes", r)


class FirstRunCLIV30Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def run_check(self, *args: str) -> dict:
        with contextlib.redirect_stdout(io.StringIO()) as output:
            rc = setup_mcp.main(["checkup", "--allowed-dir", str(self.folder),
                                 "--format", "json", *args])
        self.assertEqual(rc, 0)
        return json.loads(output.getvalue())

    def test_default_cli_is_offline_and_does_not_open_config_or_probe(self):
        before = set(self.folder.iterdir())
        with (
            patch.object(setup_mcp, "environment_report", return_value=doctor()),
            patch.object(setup_mcp, "probe_connection", side_effect=AssertionError("unexpected probe")),
            patch.object(setup_mcp, "audit_client_config", side_effect=AssertionError("unexpected read")),
            patch.object(setup_mcp, "install", side_effect=AssertionError("unexpected install")),
        ):
            result = self.run_check()
        self.assertEqual(result["next_action"], "opt_in_probe")
        self.assertFalse(result["network_used"])
        self.assertEqual(before, set(self.folder.iterdir()))

    def test_bad_doctor_skips_both_even_when_flags_requested(self):
        with (
            patch.object(setup_mcp, "environment_report", return_value=doctor("source_manifest")),
            patch.object(setup_mcp, "probe_connection", side_effect=AssertionError("must skip")),
            patch.object(setup_mcp, "audit_client_config", side_effect=AssertionError("must skip")),
        ):
            result = self.run_check("--probe", "--config-file", str(self.folder / "fake.json"))
        self.assertEqual(result["next_action"], "upgrade")
        self.assertEqual(result["checks"]["client_config"], "skipped_due_to_installation")

    def test_both_explicit_checks_invoke_only_approved_functions(self):
        with (
            patch.object(setup_mcp, "environment_report", return_value=doctor()),
            patch.object(setup_mcp, "probe_connection", return_value=probe_ok()) as p,
            patch.object(setup_mcp, "audit_client_config", return_value=config_ok()) as c,
        ):
            result = self.run_check("--probe", "--config-file", str(self.folder / "mcp.json"),
                                    "--client", "cursor", "--language", "en")
        self.assertEqual(result["status"], "ready_for_manual_host_check")
        p.assert_called_once()
        c.assert_called_once()
        self.assertFalse(result["automatic_host_registration"])

    def test_real_uninstalled_cli_has_no_directory_side_effect(self):
        before = set(self.folder.iterdir())
        with patch.object(setup_mcp, "VENV_PATH", self.folder / "never-created-venv"):
            result = self.run_check()
        self.assertEqual(result["stage"], 1)
        self.assertEqual(before, set(self.folder.iterdir()))


if __name__ == "__main__":
    unittest.main()

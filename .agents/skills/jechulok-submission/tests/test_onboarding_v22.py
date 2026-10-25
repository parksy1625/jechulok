"""v2.2 setup UX regression: accessibility, recovery ordering and no implicit changes."""
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
from onboarding_v22 import guide, render_text


def doctor(*failed: str, manifest_verified: bool = False) -> dict:
    names = (
        "python_version", "allowed_directory", "directory_access",
        "server_script", "python_environment", "mcp_dependencies",
        "skill_version", "source_manifest",
    )
    return {
        "status": "pass" if not failed else "needs_setup",
        "checks": [
            {"id": name, "passed": name not in failed,
             "verified": manifest_verified if name == "source_manifest" else None}
            for name in names
        ],
    }


class OnboardingV22Tests(unittest.TestCase):
    def test_uninstalled_environment_has_one_explicit_next_action(self):
        r = guide(doctor("python_environment", "mcp_dependencies"))
        self.assertEqual(r["status"], "needs_setup")
        self.assertEqual(r["stage"], 2)
        self.assertEqual(r["next_action"], "install_dependencies")
        self.assertEqual(r["reason_code"], "python_environment")
        self.assertEqual(len(r["failed_checks"]), 2)
        self.assertIn("install", r["suggested_command"])
        self.assertTrue("명시적" in r["instruction"])
        self.assertFalse(r["command_executed"])
        self.assertFalse(r["original_documents_read"])
        self.assertFalse(r["automatic_repair"])

    def test_broken_manifest_precedes_missing_virtual_environment(self):
        r = guide(doctor("mcp_dependencies", "source_manifest"))
        self.assertEqual(r["reason_code"], "source_manifest")
        self.assertEqual(r["next_action"], "upgrade")
        self.assertEqual(r["stage"], 1)
        self.assertIn("NEW_FOLDER", r["suggested_command"])
        self.assertFalse(r["packaged_manifest_verified"])
        self.assertFalse(r["automatic_permission_change"])
        self.assertFalse(r["client_config_modified"])

    def test_plain_text_has_numbered_checks_and_no_ansi(self):
        r = guide(doctor("directory_access", "mcp_dependencies"))
        output = render_text(r)
        self.assertIn("단계 1/4", output)
        self.assertIn("1. 작업 폴더 접근 권한", output)
        self.assertIn("2. MCP 필수 패키지", output)
        self.assertIn("파일 생성·설정 변경·문서 업로드 없음", output)
        self.assertNotIn("\x1b", output)

    def test_english_accessibility_and_client_specific_config(self):
        r = guide(doctor(manifest_verified=True), client="cursor",
                  language="en", probe={"status": "pass", "tool_count": 20})
        self.assertEqual(r["status"], "ready_for_client_config")
        self.assertTrue(r["packaged_manifest_verified"])
        self.assertIn("--client cursor", r["suggested_command"])
        self.assertIn("Step 4 of 4", render_text(r))
        self.assertNotIn("\x1b", render_text(r))
        self.assertFalse(r["mcp_host_registration_verified"])

    def test_ready_environment_asks_permission_before_stdio_probe(self):
        r = guide(doctor(manifest_verified=True))
        self.assertEqual(r["status"], "ready_for_probe")
        self.assertEqual(r["stage"], 3)
        self.assertEqual(r["next_action"], "probe")
        self.assertFalse(r["command_executed"])

    def test_failed_probe_never_claims_host_registered(self):
        for p, expected in [
            ({"status": "needs_attention", "code": "connection_timeout"},
             "mcp_probe_failed"),
            ({"status": "pass", "tool_count": 19}, "unexpected_tool_count"),
        ]:
            with self.subTest(p=p):
                r = guide(doctor(), probe=p)
                self.assertEqual(r["status"], "needs_attention")
                self.assertEqual(r["reason_code"], expected)
                self.assertFalse(r["mcp_host_registration_verified"])
                self.assertFalse(r["automatic_repair"])

    def test_no_package_manifest_explicitly_not_verified(self):
        r = guide(doctor())
        self.assertFalse(r["packaged_manifest_verified"])
        self.assertIn("무결성 확인이 수행되지", render_text(r))

    def test_reject_invalid_localization_or_client(self):
        with self.assertRaises(ValueError):
            guide(doctor(), language="xx")
        with self.assertRaises(ValueError):
            guide(doctor(), client="other")

    def test_conservative_result_when_unknown_doctor_failure(self):
        r = guide({"status": "needs_setup", "checks": []})
        self.assertEqual(r["status"], "needs_attention")
        self.assertEqual(r["reason_code"], "unrecognized_diagnostic_failure")


class OnboardingCLIV22Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def execute(self, argv: list[str]) -> tuple[int, str]:
        with contextlib.redirect_stdout(io.StringIO()) as out:
            status = setup_mcp.main(["guide", "--allowed-dir", str(self.work), *argv])
        return status, out.getvalue()

    def test_default_guide_does_not_probe_write_or_use_network(self):
        before = sorted(p.name for p in self.work.iterdir())
        with (
            patch.object(setup_mcp, "environment_report",
                         return_value=doctor("python_environment")),
            patch.object(setup_mcp, "probe_connection",
                         side_effect=AssertionError("must not probe")),
            patch.object(setup_mcp, "check_latest",
                         side_effect=AssertionError("must not use network")),
            patch.object(setup_mcp, "install",
                         side_effect=AssertionError("must not install")),
        ):
            code, output = self.execute([])
        self.assertEqual(code, 0)
        self.assertIn("설치 안내", output)
        self.assertIn("YOUR_FOLDER", output)
        self.assertNotIn(str(self.work), output)
        self.assertEqual(before, sorted(p.name for p in self.work.iterdir()))

    def test_json_option_has_stable_privacy_safe_keys(self):
        with patch.object(setup_mcp, "environment_report", return_value=doctor()):
            code, output = self.execute(["--format", "json", "--language", "en"])
        report = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(report["stage"], 3)
        self.assertEqual(report["schema"], 1)
        self.assertFalse(report["files_created"])
        self.assertFalse(report["network_used"])
        self.assertFalse(report["mcp_host_registration_verified"])
        self.assertNotIn(str(self.work), output)

    def test_probe_requires_explicit_flag_then_ready_for_manual_config(self):
        with (
            patch.object(setup_mcp, "environment_report", return_value=doctor()),
            patch.object(setup_mcp, "probe_connection",
                         return_value={"status": "pass", "tool_count": 20}) as fake,
        ):
            code, output = self.execute(["--probe", "--format", "json", "--client", "claude-desktop"])
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertEqual(result["status"], "ready_for_client_config")
        self.assertIn("--client claude-desktop", result["suggested_command"])
        fake.assert_called_once()

    def test_broken_doctor_skips_even_requested_probe(self):
        with (
            patch.object(setup_mcp, "environment_report",
                         return_value=doctor("source_manifest")),
            patch.object(setup_mcp, "probe_connection",
                         side_effect=AssertionError("unsafe probe must be skipped")),
        ):
            code, output = self.execute(["--probe", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["next_action"], "upgrade")

    def test_real_source_no_venv_guide_unchanged(self):
        # Real doctor is allowed to inspect standard metadata, but no install
        # or other file writes are authorized by guide.
        before = sorted(p.name for p in self.work.iterdir())
        with patch.object(setup_mcp, "VENV_PATH", self.work / "not_installed"):
            code, text = self.execute([])
        self.assertEqual(code, 0)
        self.assertIn("단계 2/4", text)
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), before)


if __name__ == "__main__":
    unittest.main()

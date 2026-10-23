"""JeChulOK v1.1 local MCP probe and setup error handling tests."""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import connection_probe
import setup_mcp


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_local_stdio_connection_and_synthetic_rules(self):
        before = set(self.root.iterdir())
        result = setup_mcp.probe_connection(self.root, Path(sys.executable))
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["code"], "mcp_handshake_ok")
        self.assertEqual(result["tool_count"], 20)
        self.assertFalse(result["client_config_modified"])
        self.assertEqual(result["files_processed"], 0)
        self.assertEqual(before, set(self.root.iterdir()))

    def test_missing_venv_no_side_effects(self):
        missing = self.root / "missing" / "python"
        result = setup_mcp.probe_connection(self.root, missing)
        self.assertEqual(result["status"], "needs_setup")
        self.assertEqual(result["code"], "venv_missing")
        self.assertFalse(missing.exists())

    def test_probe_timeout_has_bounded_actionable_error(self):
        with patch.object(
            setup_mcp.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(["python"], timeout=35),
        ):
            result = setup_mcp.probe_connection(self.root, Path(sys.executable))
        self.assertEqual(result["status"], "needs_attention")
        self.assertEqual(result["code"], "connection_timeout")
        self.assertFalse(result["client_config_modified"])

    def test_probe_launch_failure(self):
        with patch.object(setup_mcp.subprocess, "run", side_effect=OSError("sensitive/path")):
            result = setup_mcp.probe_connection(self.root, Path(sys.executable))
        self.assertEqual(result["code"], "python_launch_failed")
        self.assertNotIn("sensitive/path", json.dumps(result))

    def test_invalid_json_and_mismatched_exit_rejected(self):
        with patch.object(
            setup_mcp.subprocess, "run",
            return_value=subprocess.CompletedProcess([], 1, stdout="garbage", stderr="secret"),
        ):
            result = setup_mcp.probe_connection(self.root, Path(sys.executable))
        self.assertEqual(result["code"], "unexpected_probe_output")
        self.assertNotIn("secret", json.dumps(result))
        with patch.object(
            setup_mcp.subprocess, "run",
            return_value=subprocess.CompletedProcess(
                [], 1, stdout=json.dumps({"status": "pass", "code": "mcp_handshake_ok"}),
            ),
        ):
            result = setup_mcp.probe_connection(self.root, Path(sys.executable))
        self.assertEqual(result["code"], "probe_exit_mismatch")

    def test_child_output_is_allowlisted_no_path_leak(self):
        output = json.dumps({
            "status": "needs_attention",
            "code": "tools_missing",
            "missing_tools": ["parse_submission_rules"],
            "path": "/VERY_SENSITIVE/private/file.pdf",
            "secret": "not for user",
        })
        with patch.object(
            setup_mcp.subprocess, "run",
            return_value=subprocess.CompletedProcess([], 1, stdout=output),
        ):
            result = setup_mcp.probe_connection(self.root, Path(sys.executable))
        self.assertEqual(result["missing_tools"], ["parse_submission_rules"])
        self.assertNotIn("VERY_SENSITIVE", json.dumps(result))
        self.assertNotIn("not for user", json.dumps(result))

    def test_setup_cli_probe_exit_code_and_json(self):
        with (
            patch.object(setup_mcp, "VENV_PATH", self.root / "venv"),
            patch.object(
                setup_mcp, "probe_connection",
                return_value={"status": "needs_setup", "code": "venv_missing"},
            ),
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            exit_code = setup_mcp.main(["probe", "--allowed-dir", str(self.root)])
        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(out.getvalue())["code"], "venv_missing")

    def test_single_status_skips_probe_when_doctor_fails(self):
        with (
            patch.object(setup_mcp, "VENV_PATH", self.root / "nonexistent-venv"),
            patch.object(setup_mcp, "probe_connection") as probed,
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            exit_code = setup_mcp.main(["status", "--allowed-dir", str(self.root)])
        result = json.loads(out.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "needs_attention")
        self.assertEqual(result["doctor"]["status"], "needs_setup")
        self.assertEqual(result["connection"]["code"], "doctor_first")
        probed.assert_not_called()

    def test_single_status_uses_real_handshake_after_good_doctor(self):
        with (
            patch.object(setup_mcp, "VENV_PATH", self.root / "fake-venv"),
            patch.object(setup_mcp, "environment_report", return_value={
                "status": "pass", "checks": [],
            }),
            patch.object(setup_mcp, "probe_connection", return_value={
                "status": "pass", "tool_count": 20,
            }) as probed,
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            exit_code = setup_mcp.main(["status", "--allowed-dir", str(self.root)])
        self.assertEqual(exit_code, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["status"], "pass")
        self.assertEqual(data["connection"]["tool_count"], 20)
        self.assertFalse(data["client_config_modified"])
        probed.assert_called_once()

    def test_cli_probe_does_not_modify_files(self):
        before = set(self.root.iterdir())
        with patch.object(setup_mcp, "VENV_PATH", self.root / "virtualenv"):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = setup_mcp.main(["probe", "--allowed-dir", str(self.root)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue())["status"], "needs_setup")
        self.assertEqual(before, set(self.root.iterdir()))

    def test_probe_script_rejects_unauthorized_directory(self):
        with tempfile.TemporaryDirectory() as outside:
            nonexistent = Path(outside) / "missing"
            with contextlib.redirect_stdout(io.StringIO()) as out:
                result = connection_probe.main(["--allowed-dir", str(nonexistent)])
        self.assertEqual(result, 1)
        data = json.loads(out.getvalue())
        self.assertEqual(data["code"], "connection_failed")
        self.assertNotIn(str(nonexistent), out.getvalue())


if __name__ == "__main__":
    unittest.main()

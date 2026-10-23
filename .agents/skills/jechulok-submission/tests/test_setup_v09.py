"""JeChulOK v0.9 installer/config/diagnostics regression tests."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import setup_mcp as setup


class SetupV09Tests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.root = Path(self.work.name).resolve()
        self.venv = self.root / "isolated-venv"

    def tearDown(self):
        self.work.cleanup()

    def test_generated_codex_toml_is_parseable_and_absolute(self):
        python = self.root / "venv" / "bin" / "python"
        content = setup.client_configuration("codex", python, self.root)
        config = tomllib.loads(content)["mcp_servers"]["jechulok"]
        self.assertEqual(config["command"], str(python))
        self.assertEqual(config["args"], [str(setup.SERVER_SCRIPT)])
        self.assertEqual(config["env"]["JECHULOK_ALLOWED_DIRS"], str(self.root))
        self.assertNotIn("http", content)

    def test_generated_config_escapes_quotes_and_backslashes(self):
        odd_root = Path('/tmp/a"b\\windows\\path')
        for client in setup.CLIENTS:
            content = setup.client_configuration(client, self.root / 'my"python', odd_root)
            obj = (
                tomllib.loads(content)["mcp_servers"]["jechulok"]
                if client == "codex" else
                json.loads(content)["mcpServers"]["jechulok"]
            )
            self.assertEqual(obj["env"]["JECHULOK_ALLOWED_DIRS"], str(odd_root))
            self.assertEqual(obj["command"], str(self.root / 'my"python'))

    def test_cursor_and_claude_configs_use_local_stdio(self):
        for client in ("cursor", "claude-desktop"):
            obj = json.loads(setup.client_configuration(
                client, setup.venv_python(self.venv), self.root
            ))
            server = obj["mcpServers"]["jechulok"]
            self.assertEqual(len(server["args"]), 1)
            self.assertTrue(server["args"][0].endswith("scripts/mcp_server.py"))
            self.assertTrue(server["command"].startswith(str(self.venv)))
            self.assertEqual(server["env"]["JECHULOK_ALLOWED_DIRS"], str(self.root))
            self.assertNotIn("url", server)

    def test_allowed_root_rejects_outside_missing_symlink_and_traversal(self):
        self.assertEqual(setup.allowed_directory(str(self.root)), self.root)
        with self.assertRaises(ValueError):
            setup.allowed_directory("")
        with self.assertRaises(FileNotFoundError):
            setup.allowed_directory(str(self.root / "missing"))
        sub = self.root / "sub"
        sub.mkdir()
        with self.assertRaises(ValueError):
            setup.allowed_directory(str(sub / ".."))
        try:
            alias = self.root / "link"
            alias.symlink_to(sub, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(ValueError):
            setup.allowed_directory(str(alias))

    def test_diagnostics_missing_venv_has_fixes_without_writes(self):
        before = set(self.root.iterdir())
        result = setup.environment_report(self.root, setup.venv_python(self.venv))
        self.assertEqual(result["status"], "needs_setup")
        self.assertEqual(before, set(self.root.iterdir()))
        checks = {entry["id"]: entry for entry in result["checks"]}
        self.assertFalse(checks["python_environment"]["passed"])
        self.assertFalse(checks["mcp_dependencies"]["passed"])
        self.assertFalse(result["config_modified"])

    def test_diagnostics_valid_interpreter_import_probe(self):
        report = setup.environment_report(self.root, Path(sys.executable))
        self.assertEqual(report["status"], "pass", report)
        self.assertTrue(all(check["passed"] for check in report["checks"]))

    def test_install_is_opt_in_isolated_and_never_edits_client_config(self):
        root = self.root
        fake_venv = root / "test-venv"
        fake_python = fake_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        def fake_create(path):
            self.assertEqual(Path(path), fake_venv)
            fake_python.parent.mkdir(parents=True)
            fake_python.write_text("not a real interpreter")
        def fake_subprocess(command, **kwargs):
            self.assertEqual(command[0], str(fake_python))
            return subprocess.CompletedProcess(command, 0, stdout='{"imports":"ok"}', stderr="")
        with (
            patch.object(setup, "VENV_PATH", fake_venv),
            patch.object(setup.venv.EnvBuilder, "create", side_effect=fake_create),
            patch.object(setup.subprocess, "run", side_effect=fake_subprocess) as spawned,
        ):
            installed = setup.install(root)
            self.assertEqual(installed["status"], "installed")
            self.assertFalse(installed["client_settings_modified"])
            self.assertEqual(spawned.call_count, 2)
            first_call = spawned.call_args_list[0].args[0]
            self.assertEqual(first_call[1:4], ["-m", "pip", "install"])
            self.assertIn(str(setup.REQUIREMENTS), first_call)
            self.assertNotIn("codex", " ".join(first_call))

    def test_install_fails_cleanly_when_pip_fails(self):
        fake_python = setup.venv_python(self.venv)
        fake_python.parent.mkdir(parents=True)
        fake_python.write_text("not real")
        with (
            patch.object(setup, "VENV_PATH", self.venv),
            patch.object(setup.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)),
        ):
            with self.assertRaises(RuntimeError):
                setup.install(self.root)

    def test_cli_config_outputs_only_config_no_file_changes(self):
        before = {p.name for p in self.root.iterdir()}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            status = setup.main(["config", "--allowed-dir", str(self.root), "--client", "codex"])
        self.assertEqual(status, 0)
        self.assertIn("JECHULOK_ALLOWED_DIRS", out.getvalue())
        self.assertEqual(before, {p.name for p in self.root.iterdir()})

    def test_cli_doctor_fails_when_not_installed(self):
        with patch.object(setup, "VENV_PATH", self.venv):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                exit_status = setup.main(["doctor", "--allowed-dir", str(self.root)])
        self.assertEqual(exit_status, 1)
        self.assertEqual(json.loads(out.getvalue())["status"], "needs_setup")

    def test_invalid_client_and_version_checks(self):
        with self.assertRaises(ValueError):
            setup.client_configuration("unknown", Path(sys.executable), self.root)
        self.assertTrue(setup.SERVER_SCRIPT.is_file())
        self.assertTrue(setup.REQUIREMENTS.is_file())


if __name__ == "__main__":
    unittest.main()

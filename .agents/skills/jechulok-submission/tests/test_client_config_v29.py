"""v2.9 explicit MCP client config inspection, local-only and secret-redacted."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import setup_mcp
from client_config_audit_v29 import audit_client_config, MAX_CONFIG_BYTES


class ClientConfigV29Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name).resolve()
        self.interpreter = self.work / "venv" / "bin" / "python"
        self.expected = {
            "command": str(self.interpreter),
            "args": [str(setup_mcp.SERVER_SCRIPT)],
            "env": {"JECHULOK_ALLOWED_DIRS": str(self.work)},
        }

    def tearDown(self):
        self.temp.cleanup()

    def config(self, client: str, *, extra: str = "") -> Path:
        path = self.work / ("config.toml" if client == "codex" else "mcp.json")
        value = setup_mcp.client_configuration(client, self.interpreter, self.work)
        if client == "codex" and extra:
            value = extra + "\n" + value
        if client != "codex" and extra:
            document = json.loads(value)
            document["mcpServers"]["unrelated"] = {"env": {"SECRET": extra}}
            value = json.dumps(document)
        path.write_text(value, encoding="utf-8")
        return path

    def check(self, client: str, path: Path) -> dict:
        return audit_client_config(client, path, self.expected)

    def test_matching_configs_all_clients_and_no_host_claim(self):
        for client in setup_mcp.CLIENTS:
            with self.subTest(client=client):
                result = self.check(client, self.config(client))
                self.assertEqual(result["status"], "pass")
                self.assertEqual(result["reason_code"], "config_matches")
                self.assertTrue(all(result["checks"].values()))
                self.assertFalse(result["mcp_host_registration_verified"])
                self.assertFalse(result["mcp_connection_verified"])
                self.assertFalse(result["network_used"])
                self.assertFalse(result["client_settings_modified"])

    def test_unrelated_entries_allowed_but_never_disclosed(self):
        secret = "TOP_SECRET_TOKEN_DO_NOT_ECHO"
        for client in setup_mcp.CLIENTS:
            with self.subTest(client=client):
                data = self.config(client, extra=(
                    '[mcp_servers.another]\ncommand="program"\n'
                    '[mcp_servers.another.env]\nSECRET="' + secret + '"'
                    if client == "codex" else secret
                ))
                outcome = self.check(client, data)
                self.assertEqual(outcome["status"], "pass")
                self.assertNotIn(secret, json.dumps(outcome))
                self.assertNotIn(str(self.work), json.dumps(outcome))

    def test_wrong_command_needs_explicit_user_review(self):
        for client in setup_mcp.CLIENTS:
            path = self.config(client)
            if client == "codex":
                # TOML uses JSON-compatible escaped Windows path literals.
                path.write_text(path.read_text().replace(
                    json.dumps(str(self.interpreter)), json.dumps("python")))
            else:
                parsed = json.loads(path.read_text())
                parsed["mcpServers"]["jechulok"]["command"] = "python"
                path.write_text(json.dumps(parsed))
            result = self.check(client, path)
            self.assertEqual(result["reason_code"], "command_mismatch")
            self.assertEqual(result["status"], "needs_attention")
            self.assertFalse(result["checks"]["command_matches"])

    def test_wrong_server_script(self):
        path = self.config("cursor")
        data = json.loads(path.read_text())
        data["mcpServers"]["jechulok"]["args"] = ["different_server.py"]
        path.write_text(json.dumps(data))
        self.assertEqual(self.check("cursor", path)["reason_code"], "args_mismatch")

    def test_wrong_allowed_folder(self):
        path = self.config("cursor")
        parsed = json.loads(path.read_text())
        parsed["mcpServers"]["jechulok"]["command"] = "python"
        parsed["mcpServers"]["jechulok"]["env"]["JECHULOK_ALLOWED_DIRS"] = "other_path"
        path.write_text(json.dumps(parsed))
        result = self.check("cursor", path)
        self.assertEqual(result["reason_code"], "command_mismatch")
        self.assertFalse(result["checks"]["allowed_directory_matches"])

    def test_wrong_env_with_valid_command(self):
        path = self.config("claude-desktop")
        data = json.loads(path.read_text())
        data["mcpServers"]["jechulok"]["env"] = {"JECHULOK_ALLOWED_DIRS": "elsewhere"}
        path.write_text(json.dumps(data))
        self.assertEqual(self.check("claude-desktop", path)["reason_code"], "allowed_directory_mismatch")

    def test_missing_server_entry(self):
        for client in setup_mcp.CLIENTS:
            p = self.config(client)
            p.write_text("[mcp_servers.other]\ncommand='elsewhere'\n" if client == "codex"
                         else '{"mcpServers":{"another":{}}}')
            self.assertEqual(self.check(client, p)["reason_code"], "server_entry_missing")

    def test_missing_config_file_returns_repair_not_stacktrace(self):
        result = self.check("codex", self.work / "absent.toml")
        self.assertEqual(result["reason_code"], "config_file_missing")
        self.assertFalse(result["explicit_config_file_read"])

    def test_non_mapping_server_entry_fails_closed(self):
        p = self.work / "mcp.json"
        p.write_text('{"mcpServers":{"jechulok":42}}')
        self.assertEqual(self.check("cursor", p)["reason_code"], "server_entry_invalid")

    def test_malformed_json_and_toml(self):
        p = self.work / "mcp.json"
        p.write_text('{"mcpServers":')
        self.assertEqual(self.check("cursor", p)["reason_code"], "config_format_invalid")
        p.write_text("[mcp_servers.jechulok\n")
        self.assertEqual(self.check("codex", p)["reason_code"], "config_format_invalid")

    def test_duplicate_json_fields_rejected(self):
        p = self.work / "mcp.json"
        p.write_text('{"mcpServers":{},"mcpServers":{"jechulok":{}}}')
        self.assertEqual(self.check("cursor", p)["reason_code"], "config_format_invalid")

    def test_oversized_file_is_not_parsed_or_echoed(self):
        p = self.work / "mcp.json"
        p.write_bytes(b"X" * (MAX_CONFIG_BYTES + 1))
        self.assertEqual(self.check("cursor", p)["reason_code"], "config_file_unsafe")

    def test_symlink_rejected_without_following(self):
        actual = self.config("codex")
        link = self.work / "linked.toml"
        try:
            link.symlink_to(actual)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink unsupported")
        result = self.check("codex", link)
        self.assertEqual(result["reason_code"], "config_file_unsafe")
        self.assertFalse(result["explicit_config_file_read"])

    def test_path_dotdot_alias_rejected(self):
        path = self.config("codex")
        alias = self.work / "nested" / ".." / path.name
        (self.work / "nested").mkdir()
        self.assertEqual(self.check("codex", alias)["reason_code"], "config_file_unsafe")

    def test_nonregular_directory_is_rejected(self):
        self.assertEqual(self.check("codex", self.work)["reason_code"], "config_file_unsafe")

    def test_invalid_client_rejected(self):
        with self.assertRaises(ValueError):
            self.check("unknown", self.work / "mcp.json")

    def test_cli_does_not_probe_install_or_scan_other_files(self):
        path = self.config("codex")
        before = set(self.work.iterdir())
        with (
            patch.object(setup_mcp, "venv_python", return_value=self.interpreter),
            patch.object(setup_mcp, "probe_connection", side_effect=AssertionError("no probe")),
            patch.object(setup_mcp, "install", side_effect=AssertionError("no install")),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            code = setup_mcp.main(["config-check", "--client", "codex",
                                   "--allowed-dir", str(self.work), "--config-file", str(path)])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(before, set(self.work.iterdir()))
        self.assertNotIn(str(self.work), output.getvalue())

    def test_cli_bad_config_returns_failure_without_raw_secret(self):
        path = self.work / "mcp.json"
        path.write_text('{"mcpServers":{"jechulok":{"command":"VERY_PRIVATE_SECRET"}}}')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = setup_mcp.main(["config-check", "--client", "cursor",
                                   "--allowed-dir", str(self.work), "--config-file", str(path)])
        self.assertEqual(code, 1)
        self.assertNotIn("VERY_PRIVATE_SECRET", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["reason_code"], "command_mismatch")


if __name__ == "__main__":
    unittest.main()

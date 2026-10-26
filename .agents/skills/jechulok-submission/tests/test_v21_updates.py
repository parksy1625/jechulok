"""v2.1: opt-in release check, packaged integrity and privacy-safe beta diagnostics."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from version_check_v21 import check_latest, version_tuple
from diagnostics_v21 import installation_checks
from release_v20 import build, extract
import setup_mcp


class StubResponse:
    def __init__(self, obj):
        self.content = json.dumps(obj).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return None
    def read(self, size):
        return self.content[:size]


class UpdateCheckV21Tests(unittest.TestCase):
    def test_check_is_offline_by_default_even_if_network_fails(self):
        with patch("version_check_v21.urlopen", side_effect=AssertionError("Unexpected network")):
            out = check_latest("2.6.0")
        self.assertEqual(out["status"], "offline")
        self.assertIsNone(out["latest_version"])
        self.assertFalse(out["download_performed"])
        self.assertFalse(out["client_config_changed"])

    def test_online_has_fixed_https_endpoint_and_no_auto_install(self):
        def fetch(request, timeout):
            self.assertEqual(request.full_url, "https://api.github.com/repos/parksy1625/jechulok/releases/latest")
            self.assertGreater(timeout, 0)
            return StubResponse({"tag_name": "v2.7.0", "html_url": "https://malicious.example"})

        with patch("version_check_v21.urlopen", side_effect=fetch):
            result = check_latest("2.6.0", online=True)
        self.assertEqual(result["status"], "update_available")
        self.assertEqual(result["latest_version"], "2.7.0")
        self.assertEqual(result["release_page"], "https://github.com/parksy1625/jechulok/releases")
        self.assertNotIn("malicious", json.dumps(result))
        self.assertFalse(result["automatic_update"])
        self.assertFalse(result["download_performed"])
        self.assertFalse(result["user_documents_transmitted"])

    def test_version_comparison_and_untrusted_values(self):
        for latest, expected in (("v2.6.0", "up_to_date"),
                                 ("v2.0.9", "local_newer"),
                                 ("v12.0.0", "update_available")):
            with self.subTest(latest=latest):
                with patch("version_check_v21.urlopen", return_value=StubResponse({"tag_name": latest})):
                    self.assertEqual(check_latest("2.6.0", online=True)["status"], expected)
        for bad in ("v2.6.0-beta", "https://x", "2.1", "v02.6.0;rm", {}, None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    version_tuple(bad)
        with patch("version_check_v21.urlopen", return_value=StubResponse({"tag_name": "v2.6.0-beta"})):
            self.assertEqual(check_latest("2.6.0", online=True)["status"], "unavailable")

    def test_404_no_published_release_and_network_errors(self):
        with patch("version_check_v21.urlopen", side_effect=HTTPError("x", 404, "not found", {}, None)):
            self.assertEqual(check_latest("2.6.0", online=True)["status"], "no_published_release")
        with patch("version_check_v21.urlopen", side_effect=HTTPError("x", 403, "rate limit", {}, None)):
            self.assertEqual(check_latest("2.6.0", online=True)["status"], "unavailable")
        with patch("version_check_v21.urlopen", side_effect=URLError("offline")):
            self.assertEqual(check_latest("2.6.0", online=True)["status"], "unavailable")
        with patch("version_check_v21.urlopen", return_value=StubResponse({"tag_name": "x" * 70000})):
            self.assertEqual(check_latest("2.6.0", online=True)["status"], "unavailable")

    def test_setup_cli_updates_is_offline_and_returns_structured_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with patch("version_check_v21.urlopen", side_effect=AssertionError("network")):
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    code = setup_mcp.main(["updates", "--allowed-dir", str(root)])
            self.assertEqual(code, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result["status"], "offline")
            self.assertEqual(result["current_version"], "2.9.0")


class LocalIntegrityV21Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        build(self.root)
        self.archive = self.root / "jechulok-agent-skill-v2.9.0.zip"
        self.extracted = self.root / "unpacked"
        extract(self.archive, self.extracted, execute=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_installation_manifest_and_version_pass_without_personal_files(self):
        checks = installation_checks(self.extracted)
        self.assertEqual([c["id"] for c in checks], ["skill_version", "source_manifest"])
        self.assertTrue(all(c["passed"] for c in checks), checks)
        self.assertTrue(checks[1]["verified"])
        self.assertTrue((self.extracted / "MANIFEST.json").is_file())
        self.assertIn("not publisher authentication", checks[1]["detail"])
        # Source checkout does not have a manifest and must NOT say verified.
        source = installation_checks(ROOT)
        self.assertTrue(source[0]["passed"], source)
        self.assertFalse(source[1]["verified"], source)

    def test_tampered_extracted_script_is_detected_with_no_modifications(self):
        path = self.extracted / "scripts" / "mcp_server.py"
        path.write_bytes(path.read_bytes() + b"\n# changed\n")
        before = path.read_bytes()
        checks = installation_checks(self.extracted)
        self.assertFalse(checks[1]["passed"])
        self.assertFalse(checks[1]["verified"])
        self.assertEqual(path.read_bytes(), before)

    def test_modified_version_and_invalid_manifest_path_fail_closed(self):
        (self.extracted / "VERSION").write_text("0.0.0\n", encoding="utf-8")
        self.assertFalse(installation_checks(self.extracted)[0]["passed"])
        (self.extracted / "VERSION").write_text("2.9.0\n", encoding="utf-8")
        manifest = self.extracted / "MANIFEST.json"
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        doc["files"]["../../outside"] = {"bytes": 5, "sha256": "0" * 64}
        manifest.write_text(json.dumps(doc), encoding="utf-8")
        self.assertFalse(installation_checks(self.extracted)[1]["passed"])

    def test_beta_check_returns_only_sanitized_aggregate(self):
        with (
            patch.object(setup_mcp, "VENV_PATH", self.root / "fake-env"),
            patch.object(setup_mcp, "probe_connection",
                         return_value={"status": "pass", "tool_count": 20}),
            patch.object(setup_mcp, "environment_report",
                         return_value={"status": "pass", "checks": [
                             {"id": "skill_version", "passed": True, "fix": None},
                             {"id": "source_manifest", "passed": True, "fix": None},
                         ]}),
        ):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                result = setup_mcp.main(["beta-check", "--allowed-dir", str(self.root)])
        self.assertEqual(result, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["version"], "2.9.0")
        self.assertEqual(data["tool_count"], 20)
        self.assertFalse(data["network_used"])
        self.assertFalse(data["documents_read"])
        self.assertNotIn(str(self.root), out.getvalue())


if __name__ == "__main__":
    unittest.main()

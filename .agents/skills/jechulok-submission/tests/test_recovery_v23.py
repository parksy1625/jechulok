"""v2.3 recovery preview and synthetic installation lifecycle tests."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from recovery_plan_v23 import plan_recovery
from release_v20 import build, extract, RELEASE_VERSION
import setup_mcp


class RecoveryPreviewV23Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.work = self.root / "test-work"
        self.work.mkdir()
        self.sentinel = self.work / "personal-sentinel.txt"
        self.sentinel.write_bytes(b"synthetic sentinel")
        build(self.root)
        self.archive = self.root / f"jechulok-agent-skill-v{RELEASE_VERSION}.zip"
        self.destination = self.root / "new-skill"

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_never_writes_and_returned_fields_are_privacy_safe(self):
        before = {p.name for p in self.root.iterdir()}
        r = plan_recovery(self.archive, self.destination, installed_root=ROOT)
        self.assertEqual(r["status"], "planned")
        self.assertEqual(r["archive_version"], "2.8.0")
        self.assertFalse(r["publisher_authenticated"])
        self.assertFalse(r["existing_installation_modified"])
        self.assertTrue(r["requires_manual_client_switch"])
        self.assertFalse(r["automatic_rollback"])
        self.assertEqual(r["files_created"], 0)
        self.assertEqual(before, {p.name for p in self.root.iterdir()})
        self.assertFalse(self.destination.exists())
        self.assertNotIn(str(self.root), json.dumps(r))
        self.assertEqual(self.sentinel.read_bytes(), b"synthetic sentinel")

    def test_cli_entry_returns_sanitized_json_with_no_side_effects(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            exit_code = setup_mcp.main([
                "recovery-plan", "--allowed-dir", str(self.work),
                "--archive", str(self.archive),
                "--destination", str(self.destination),
            ])
        self.assertEqual(exit_code, 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["status"], "planned")
        self.assertFalse(result["client_config_modified"])
        self.assertFalse(result["network_used"])
        self.assertFalse(self.destination.exists())
        self.assertNotIn(str(self.work), out.getvalue())

    def test_malicious_archive_and_existing_target_blocked_without_deleting(self):
        self.destination.mkdir()
        child = self.destination / "existing.bin"
        child.write_bytes(b"untouched")
        r = plan_recovery(self.archive, self.destination, installed_root=ROOT)
        self.assertEqual(r["status"], "blocked")
        self.assertEqual(child.read_bytes(), b"untouched")
        bad = self.root / "bad.zip"
        bad.write_bytes(b"corrupted")
        r2 = plan_recovery(bad, self.root / "another", installed_root=ROOT)
        self.assertEqual(r2["status"], "blocked")
        self.assertFalse((self.root / "another").exists())

    def test_current_corrupt_install_is_not_executed(self):
        original = self.root / "old"
        extract(self.archive, original, execute=True)
        script = original / "scripts" / "mcp_server.py"
        script.write_bytes(script.read_bytes() + b"\n# corrupted\n")
        r = plan_recovery(self.archive, self.destination, installed_root=original)
        self.assertIn("source_manifest", r["current_source_issues"])
        self.assertEqual(r["status"], "planned")
        self.assertIn("Do not execute", r["warning"])
        self.assertTrue(script.read_bytes().endswith(b"# corrupted\n"))
        self.assertFalse(self.destination.exists())


class RecoveryHarnessV23Tests(unittest.TestCase):
    def test_full_14_synthetic_scenarios_cli(self):
        p = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "recovery_scenarios_v23.py"),
            "--check",
        ], capture_output=True, text=True, timeout=90)
        self.assertEqual(p.returncode, 0, p.stderr[-1000:] + p.stdout[-3000:])
        result = json.loads(p.stdout)
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["scenario_count"], 14)
        self.assertEqual(result["passed_count"], 14)
        self.assertEqual(len({r["id"] for r in result["scenarios"]}), 14)
        self.assertTrue(result["real_stdio_handshake_tested"])
        self.assertFalse(result["user_client_settings_changed"])
        self.assertFalse(result["actual_user_installation_tested"])
        self.assertEqual(result["external_testers"], 0)
        self.assertFalse(result["network_used_by_harness"])


if __name__ == "__main__":
    unittest.main()

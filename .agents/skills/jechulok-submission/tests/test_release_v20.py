"""2.0 release contract: reproducible package, offline upgrade and real stdio MCP."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

from mcp import Client, StdioServerParameters

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from release_v20 import ARCHIVE_ROOT, MANIFEST_NAME, build, verify, extract
import setup_mcp


class ReleaseV20Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name).resolve()
        self.archive_name = "jechulok-agent-skill-v3.2.0.zip"

    def tearDown(self):
        self.temporary.cleanup()

    def test_release_bundle_manifest_checksum_and_private_data_exclusion(self):
        result = build(self.directory)
        archive = self.directory / self.archive_name
        self.assertEqual(result["status"], "built")
        self.assertEqual(result["version"], "3.2.0")
        self.assertTrue(archive.is_file())
        self.assertTrue((self.directory / "jechulok-agent-skill-v3.2.0.sha256").is_file())
        checked = verify(archive)
        self.assertEqual(checked["archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(checked["status"], "verified")
        self.assertFalse(checked["authenticity_verified"])
        with zipfile.ZipFile(archive) as z:
            names = set(z.namelist())
            self.assertIn(f"{ARCHIVE_ROOT}/scripts/mcp_server.py", names)
            self.assertIn(f"{ARCHIVE_ROOT}/scripts/release_v20.py", names)
            self.assertIn(f"{ARCHIVE_ROOT}/scripts/feedback_insights_v27.py", names)
            self.assertIn(f"{ARCHIVE_ROOT}/RELEASE_NOTES_v27.md", names)
            self.assertIn(f"{ARCHIVE_ROOT}/scripts/beta_protocol_v28.py", names)
            self.assertIn(f"{ARCHIVE_ROOT}/RELEASE_NOTES_v28.md", names)
            self.assertIn(f"{ARCHIVE_ROOT}/scripts/client_config_audit_v29.py", names)
            self.assertIn(f"{ARCHIVE_ROOT}/RELEASE_NOTES_v29.md", names)
            self.assertIn(f"{ARCHIVE_ROOT}/scripts/first_run_checkup_v30.py", names)
            self.assertIn(f"{ARCHIVE_ROOT}/RELEASE_NOTES_v30.md", names)
            self.assertIn(f"{ARCHIVE_ROOT}/RELEASE_NOTES_v31.md", names)
            self.assertIn(f"{ARCHIVE_ROOT}/scripts/offline_demo_v31.py", names)
            self.assertIn(f"{ARCHIVE_ROOT}/RELEASE_NOTES_v32.md", names)
            self.assertIn(f"{ARCHIVE_ROOT}/scripts/preview_prepare_v32.py", names)
            self.assertIn(MANIFEST_NAME, names)
            self.assertFalse(any("private-evaluation" in x or "/.venv" in x
                                 or "/tests/" in x or "pycache" in x
                                 or ".jechulok-jobs" in x for x in names))
            manifest = json.loads(z.read(MANIFEST_NAME))
            self.assertEqual(manifest["version"], "3.2.0")
            self.assertEqual(len(manifest["files"]), checked["file_count"])
        lines = (self.directory / "jechulok-agent-skill-v3.2.0.sha256").read_text()
        self.assertEqual(lines, f"{checked['archive_sha256']}  {archive.name}\n")

    def test_rebuilding_from_unchanged_sources_is_byte_identical(self):
        first = build(self.directory)
        next_output = self.directory / "second"
        next_output.mkdir()
        second = build(next_output)
        self.assertEqual(first["archive_sha256"], second["archive_sha256"])
        self.assertEqual(first["file_count"], second["file_count"])

    def test_upgrade_preview_is_read_only_then_explicit_side_by_side_extract(self):
        build(self.directory)
        archive = self.directory / self.archive_name
        destination = self.directory / "new-v2"
        original_marker = self.directory / "my-client-config.json"
        original_marker.write_text("DO NOT REPLACE", encoding="utf-8")
        planned = setup_mcp.prepare_upgrade(archive, destination, execute=False)
        self.assertEqual(planned["status"], "planned")
        self.assertEqual(planned["files_created"], 0)
        self.assertFalse(destination.exists())
        self.assertTrue(planned["confirmation_required"])
        installed = setup_mcp.prepare_upgrade(archive, destination, execute=True)
        self.assertEqual(installed["status"], "extracted")
        self.assertFalse(installed["old_virtualenv_changed"])
        self.assertFalse(installed["automatic_client_reregistration"])
        self.assertTrue((destination / "scripts" / "mcp_server.py").exists())
        self.assertTrue((destination / "scripts" / "setup_mcp.py").exists())
        self.assertEqual((destination / "VERSION").read_text().strip(), "3.2.0")
        self.assertEqual(original_marker.read_text(), "DO NOT REPLACE")
        with self.assertRaises(ValueError):
            extract(archive, destination, execute=True)

    def test_existing_destination_is_never_overwritten(self):
        build(self.directory)
        destination = self.directory / "new-v2"
        destination.mkdir()
        marker = destination / "private.pdf"
        marker.write_bytes(b"do not overwrite")
        with self.assertRaises(ValueError):
            extract(self.directory / self.archive_name, destination, execute=True)
        self.assertEqual(marker.read_bytes(), b"do not overwrite")
        with self.assertRaises(ValueError):
            build(self.directory)
        self.assertEqual(marker.read_bytes(), b"do not overwrite")

    def test_modified_archive_member_is_rejected(self):
        build(self.directory)
        source = self.directory / self.archive_name
        tampered = self.directory / "tampered.zip"
        with zipfile.ZipFile(source) as zin, zipfile.ZipFile(tampered, "w") as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.endswith("/VERSION"):
                    data = b"2.0.1\n"
                zout.writestr(info, data)
        with self.assertRaises(ValueError):
            verify(tampered)

    def test_zip_slip_and_symlink_injection_rejected(self):
        for malicious in (f"{ARCHIVE_ROOT}/../../private.txt",
                          f"{ARCHIVE_ROOT}/scripts/../private.txt"):
            with self.subTest(name=malicious):
                path = self.directory / "bad.zip"
                with zipfile.ZipFile(path, "w") as z:
                    z.writestr(malicious, "bad")
                with self.assertRaises(ValueError):
                    verify(path)
                path.unlink()
        with zipfile.ZipFile(self.directory / "link.zip", "w") as z:
            info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/scripts/payload.py")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, "../private")
        with self.assertRaises(ValueError):
            verify(self.directory / "link.zip")

    def test_upgrade_cli_needs_execute_for_extraction(self):
        build(self.directory)
        archive = self.directory / self.archive_name
        destination = self.directory / "from-cli"
        work_folder = self.directory / "authorized-work"
        work_folder.mkdir()
        cmd = [
            sys.executable, str(SKILL / "scripts" / "setup_mcp.py"),
            "upgrade", "--allowed-dir", str(work_folder),
            "--archive", str(archive), "--destination", str(destination),
        ]
        plan = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertEqual(json.loads(plan.stdout)["status"], "planned")
        self.assertFalse(destination.exists())
        applied = subprocess.run([*cmd, "--execute"], capture_output=True, text=True, timeout=20)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertTrue((destination / "SKILL.md").exists())
        self.assertEqual(json.loads(applied.stdout)["status"], "extracted")
        self.assertFalse((destination / ".venv").exists())


class ExtractedMCPV20Tests(unittest.IsolatedAsyncioTestCase):
    async def test_packaged_server_supports_real_stdio_and_20_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp).resolve()
            build(directory)
            destination = directory / "installed"
            extract(directory / "jechulok-agent-skill-v3.2.0.zip", destination, execute=True)
            work_folder = directory / "user-work"
            work_folder.mkdir()
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(destination / "scripts" / "mcp_server.py")],
                env={"JECHULOK_ALLOWED_DIRS": str(work_folder)},
            )
            async with Client(params) as client:
                names = {tool.name for tool in (await client.list_tools()).tools}
                self.assertEqual(len(names), 20)
                self.assertIn("assist_submission", names)
                response = await client.call_tool("parse_submission_rules", {
                    "requirements_text": "JPG 300×400px 500KB 이하",
                })
                self.assertFalse(response.is_error)
                self.assertEqual(response.structured_content["status"], "parsed")
                self.assertFalse((work_folder / ".jechulok-jobs").exists())


if __name__ == "__main__":
    unittest.main()

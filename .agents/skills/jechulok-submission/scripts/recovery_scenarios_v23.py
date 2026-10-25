#!/usr/bin/env python3
"""JeChulOK v2.3 — 14 synthetic lifecycle/recovery regressions.

This is an *automated local functional test*, not evidence of external
people successfully installing the skill. It builds and extracts a
portable archive only in a disposable temp directory, simulates a
damaged previous copy, verifies a new side-by-side copy and tests one
real MCP stdio handshake with synthetic rule text.

No private files, user home scan, network calls by this script, pip
installation, automatic client registration or institutional uploads.
Dependencies for the MCP test must already be installed by the caller.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import zipfile

from diagnostics_v21 import installation_checks
from recovery_plan_v23 import plan_recovery
from release_v20 import build, verify, extract, MANIFEST_NAME, RELEASE_VERSION
from mcp import Client, StdioServerParameters


def _run_probe(path: Path, work: Path) -> bool:
    async def check():
        async with Client(StdioServerParameters(
            command=sys.executable, args=[str(path / "scripts" / "mcp_server.py")],
            env={"JECHULOK_ALLOWED_DIRS": str(work)},
        )) as client:
            listing = await client.list_tools()
            names = {tool.name for tool in listing.tools}
            if len(names) != 20 or "assist_submission" not in names:
                return False
            response = await client.call_tool(
                "parse_submission_rules",
                {"requirements_text": "JPG 300×400px 500KB 이하"},
            )
            return (
                not response.is_error
                and (response.structured_content or {}).get("status") == "parsed"
            )
    return asyncio.run(check())


def evaluate() -> dict:
    scenarios: list[dict] = []

    def case(name: str, passed: bool) -> None:
        # Constant curated names, never exceptions, temp paths or file content.
        scenarios.append({"id": name, "passed": bool(passed)})

    with tempfile.TemporaryDirectory(prefix="jechulok-v23-synthetic-") as temporary:
        root = Path(temporary).resolve()
        data = root / "simulated-user-documents"
        data.mkdir()
        private = data / "DO-NOT-TOUCH.txt"
        private.write_bytes(b"synthetic user-file sentinel: leave unchanged")
        sentinel = private.read_bytes()
        host = root / "simulated-client-settings.json"
        host.write_bytes(b'{"mcpServers":{"old":{"command":"unchanged"}}}')
        host_data = host.read_bytes()

        release = build(root)
        archive = root / f"jechulok-agent-skill-v{RELEASE_VERSION}.zip"
        sidecar = root / f"jechulok-agent-skill-v{RELEASE_VERSION}.sha256"
        case("01_release_bundle_created", release["status"] == "built"
             and archive.exists() and sidecar.exists())
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        case("02_full_and_member_checksums", verify(archive)["archive_sha256"] == checksum
             and sidecar.read_text().startswith(checksum + "  "))

        previous = root / "previous-version-copy"
        preview = extract(archive, previous, execute=False)
        case("03_install_preview_creates_nothing",
             preview["status"] == "planned" and not previous.exists())
        installed = extract(archive, previous, execute=True)
        case("04_explicit_extract_creates_isolated_copy",
             installed["status"] == "extracted"
             and (previous / "scripts" / "mcp_server.py").is_file()
             and (previous / "MANIFEST.json").is_file())
        healthy = installation_checks(previous)
        case("05_original_install_manifest_valid",
             bool(healthy) and all(x["passed"] for x in healthy)
             and any(x["id"] == "source_manifest" and x.get("verified") for x in healthy))

        # The extracted distribution deliberately contains no venv.
        old_venv_untouched = not (previous / ".venv").exists()

        # Corrupt a disposable OLD copy, then verify diagnosis *without*
        # executing any script from that damaged copy.
        old_script = previous / "scripts" / "mcp_server.py"
        old_script.write_bytes(old_script.read_bytes() + b"\n# synthetic corruption\n")
        broken = installation_checks(previous)
        case("06_tampered_old_copy_detected",
             any(x["id"] == "source_manifest" and x["passed"] is False for x in broken))

        replacement = root / "new-skill-install"
        repair = plan_recovery(archive, replacement, installed_root=previous)
        case("07_recovery_plan_read_only_and_warns",
             repair["status"] == "planned"
             and repair["ready_for_explicit_extraction"]
             and "source_manifest" in repair["current_source_issues"]
             and repair["files_created"] == repair["files_deleted"] == 0
             and not replacement.exists()
             and repair["requires_manual_client_switch"]
             and repair["publisher_authenticated"] is False)

        # Existing paths must not be overwritten, including the old,
        # intentionally corrupted skill and a new destination containing data.
        occupied = root / "occupied-target"
        occupied.mkdir()
        marker = occupied / "dont-overwrite"
        marker.write_bytes(b"occupied and owned by someone else")
        blocked = plan_recovery(archive, occupied, installed_root=previous)
        case("08_existing_destination_rejected_without_deletion",
             blocked["status"] == "blocked"
             and marker.read_bytes() == b"occupied and owned by someone else")
        tampered_archive = root / "tampered.zip"
        with zipfile.ZipFile(archive) as original, zipfile.ZipFile(tampered_archive, "w") as destination:
            for member in original.infolist():
                raw = original.read(member.filename)
                if member.filename.endswith("/VERSION"):
                    raw = b"999.0.0\n"
                destination.writestr(member, raw)
        invalid = plan_recovery(tampered_archive, root / "bad-source-target", installed_root=previous)
        case("09_modified_archive_refused",
             invalid["status"] == "blocked"
             and not (root / "bad-source-target").exists())
        bad_zip = root / "invalid.zip"
        bad_zip.write_bytes(b"synthetic invalid archive")
        corrupt = plan_recovery(bad_zip, root / "invalid-target", installed_root=previous)
        case("10_corrupt_zip_rejected_without_traceback",
             corrupt["status"] == "blocked"
             and not (root / "invalid-target").exists())

        new_copy = extract(archive, replacement, execute=True)
        fresh = installation_checks(replacement)
        case("11_recover_into_new_verified_folder",
             new_copy["status"] == "extracted"
             and all(x["passed"] for x in fresh)
             and any(x["id"] == "source_manifest" and x.get("verified") for x in fresh)
             and not (replacement / ".venv").exists())

        config_cmd = [
            sys.executable, str(replacement / "scripts" / "setup_mcp.py"),
            "config", "--allowed-dir", str(data), "--client", "codex",
        ]
        config = subprocess.run(config_cmd, capture_output=True, text=True, timeout=15)
        cfg = tomllib.loads(config.stdout)["mcp_servers"]["jechulok"] if config.returncode == 0 else {}
        case("12_new_copy_client_config_is_copy_only",
             config.returncode == 0 and cfg.get("command", "").startswith(str(replacement))
             and cfg.get("args") == [str(replacement / "scripts" / "mcp_server.py")]
             and cfg.get("env", {}).get("JECHULOK_ALLOWED_DIRS") == str(data)
             and host.read_bytes() == host_data)
        case("13_recovered_copy_real_20_tool_mcp_connection",
             _run_probe(replacement, data))
        case("14_rollback_sources_and_user_docs_intact",
             old_script.read_bytes().endswith(b"# synthetic corruption\n")
             and old_venv_untouched and not (previous / ".venv").exists()
             and host.read_bytes() == host_data and private.read_bytes() == sentinel
             and not (replacement / ".venv").exists()
             and not (data / ".jechulok-jobs").exists())

    passed = sum(1 for c in scenarios if c["passed"])
    return {
        "suite": "jechulok_v23_disposable_lifecycle_recovery",
        "status": "pass" if passed == len(scenarios) == 14 else "fail",
        "scenario_count": len(scenarios),
        "passed_count": passed,
        "scenarios": scenarios,
        "fixture_type": "synthetic_tempfiles_only",
        "actual_user_installation_tested": False,
        "external_testers": 0,
        "local_pip_install_performed": False,
        "real_stdio_handshake_tested": True,
        "real_client_host_registration_tested": False,
        "user_data_processed": False,
        "user_client_settings_changed": False,
        "network_used_by_harness": False,
        "caveat": "This proves a 14-case disposable regression, not end-user acceptance, offline dependency installation, or publisher authenticity.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.check and report["status"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())

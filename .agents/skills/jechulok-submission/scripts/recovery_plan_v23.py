"""JeChulOK v2.3 — local read-only recovery preflight.

Inspect the current skill's VERSION/manifest and a USER-SUPPLIED offline
archive/new destination. Never install dependencies, remove files, edit
client configuration, probe MCP, or claim publisher authentication.
Run this command from a TRUSTED copy of the setup scripts (not an
installation already identified as tampered).
"""
from __future__ import annotations

from pathlib import Path
import zipfile
import json
from typing import Any

from diagnostics_v21 import installation_checks
from release_v20 import extract


def plan_recovery(archive: Path, new_directory: Path, *, installed_root: Path) -> dict[str, Any]:
    # Information about current installation is inspectable, never repaired.
    checks = installation_checks(installed_root)
    unsafe = [
        c["id"] for c in checks if c["passed"] is False
    ]
    manifest_unverified = any(
        c["id"] == "source_manifest" and not c.get("verified", False)
        for c in checks
    )
    common = {
        "schema": 1,
        "mode": "read_only_recovery_preview",
        "current_source_issues": unsafe,
        "current_source_manifest_verified": not manifest_unverified,
        "publisher_authenticated": False,
        "network_used": False,
        "files_created": 0,
        "files_deleted": 0,
        "existing_installation_modified": False,
        "client_config_modified": False,
        "dependencies_installed": False,
        "automatic_rollback": False,
        "requires_new_install_confirmation": True,
        "requires_manual_client_switch": True,
        "manual_recovery_steps": [
            "Obtain the release ZIP from a trusted repository independently; checksums alone do not authenticate the publisher.",
            "Preview the archive and check the destination, then explicitly approve extraction into a NEW folder.",
            "From the new installation, explicitly install dependencies and run doctor/probe before use.",
            "Only after confirming the 20 local MCP tools, review and manually switch the client configuration.",
            "Keep the old installation and client configuration so you can manually restore the previous setup.",
        ],
    }
    try:
        # Underlying verification rejects invalid archives, existing targets,
        # symlinks and noncanonical parent paths without extracting anything.
        preview = extract(archive, new_directory, execute=False)
    except (ValueError, OSError, KeyError, RuntimeError, TypeError, zipfile.BadZipFile, json.JSONDecodeError):
        return {
            **common, "status": "blocked",
            "blocker": "invalid_archive_or_destination",
            "archive_verified": False, "ready_for_explicit_extraction": False,
            "next_action": "obtain_trusted_archive_or_new_destination",
        }
    return {
        **common, "status": "planned",
        "archive_verified": preview["status"] == "planned",
        "archive_version": preview["version"],
        "manifest_file_count": preview["file_count"],
        "archive_checksum": preview["archive_sha256"],
        "ready_for_explicit_extraction": True,
        "next_action": "review_then_explicitly_extract_new_copy",
        "warning": (
            "Current installation reports source-integrity problems. "
            "Do not execute its scripts; run recovery only from a separate trusted copy."
            if unsafe else
            "This plan does not switch a running MCP client or prove that an institution will accept documents."
        ),
    }

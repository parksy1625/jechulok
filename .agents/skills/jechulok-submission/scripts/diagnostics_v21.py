"""JeChulOK v2.1 read-only local installation diagnostics.

A packaged MANIFEST.json detects accidental edits of extracted files, but
is not an authenticated publisher signature. Source checkouts have no
manifest and are explicitly classified as unverified-by-manifest.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re

MAX_MANIFEST = 128 * 1024
MAX_FILES = 128
MAX_FILE_SIZE = 2 * 1024 * 1024


def _check_manifest(root: Path, installed_version: str) -> dict:
    manifest = root / "MANIFEST.json"
    if not manifest.exists() and not manifest.is_symlink():
        return {
            "id": "source_manifest", "passed": True, "verified": False,
            "detail": "Source checkout or legacy installation; no bundled file integrity manifest",
            "fix": "Use a versioned ZIP install to enable local file-consistency checking.",
        }
    try:
        if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > MAX_MANIFEST:
            raise ValueError("Missing, linked or oversized manifest")
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        if (type(doc) is not dict or doc.get("version") != installed_version
                or doc.get("schema") != 1
                or doc.get("name") != "jechulok-submission"
                or type(doc.get("files")) is not dict
                or not 1 <= len(doc["files"]) <= MAX_FILES):
            raise ValueError("Manifest schema/version mismatch")
        for name, expected in doc["files"].items():
            if type(name) is not str:
                raise ValueError("Invalid manifest filename")
            path = PurePosixPath(name)
            if (not name or path.is_absolute() or ".." in path.parts
                    or "\\" in name or path.as_posix() != name
                    or type(expected) is not dict
                    or set(expected) != {"sha256", "bytes"}
                    or type(expected["sha256"]) is not str
                    or not re.fullmatch(r"[0-9a-f]{64}", expected["sha256"])
                    or type(expected["bytes"]) is not int
                    or not 0 <= expected["bytes"] <= MAX_FILE_SIZE):
                raise ValueError("Invalid manifest member")
            actual_path = root.joinpath(*path.parts)
            if (actual_path.is_symlink() or not actual_path.is_file()
                    or not actual_path.resolve().is_relative_to(root)):
                raise ValueError("Unexpected or missing installed file")
            if actual_path.stat().st_size != expected["bytes"]:
                raise ValueError("Installed file changed length")
            actual = actual_path.read_bytes()
            if (len(actual) != expected["bytes"]
                    or hashlib.sha256(actual).hexdigest() != expected["sha256"]):
                raise ValueError("Installed file checksum mismatch")
        return {
            "id": "source_manifest", "passed": True, "verified": True,
            "detail": "Local source files match the extracted manifest; not publisher authentication",
            "fix": None,
        }
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return {
            "id": "source_manifest", "passed": False, "verified": False,
            "detail": "Missing or modified file in extracted installation",
            "fix": "Do not run untrusted edited sources. Verify a trusted archive and extract it to a NEW folder.",
        }


def installation_checks(root: Path) -> list[dict]:
    root = root.resolve()
    checks = []
    version_file = root / "VERSION"
    skill_file = root / "SKILL.md"
    version = None
    try:
        if (version_file.is_symlink() or not version_file.is_file()
                or version_file.stat().st_size > 100
                or skill_file.is_symlink() or not skill_file.is_file()
                or skill_file.stat().st_size > 100_000):
            raise ValueError("Missing or linked version metadata")
        version = version_file.read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"\d{1,4}\.\d{1,4}\.\d{1,4}", version):
            raise ValueError("Unexpected version")
        content = skill_file.read_text(encoding="utf-8")
        if not content.startswith("---\n") or f'version: "{version}"' not in content.split("---", 2)[1]:
            raise ValueError("SKILL.md metadata differs from VERSION")
        checks.append({
            "id": "skill_version", "passed": True, "detail": f"Version {version} matches SKILL.md",
            "fix": None,
        })
    except (ValueError, OSError, UnicodeError):
        checks.append({
            "id": "skill_version", "passed": False,
            "detail": "VERSION and SKILL.md metadata do not match",
            "fix": "Restore a consistent trusted package; do not edit installed source files manually.",
        })
    if version is not None and checks[0]["passed"]:
        checks.append(_check_manifest(root, version))
    return checks

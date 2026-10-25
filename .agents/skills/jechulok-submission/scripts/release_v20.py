#!/usr/bin/env python3
"""JeChulOK 2.3: deterministic, local-only release ZIP and safe side-by-side extraction.

Standard library only. Not a publisher, network client, digital signature
or a magic upgrade of running MCP hosts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
ARCHIVE_ROOT = "jechulok-submission"
RELEASE_VERSION = "2.3.0"
MANIFEST_NAME = f"{ARCHIVE_ROOT}/MANIFEST.json"
MAX_ARCHIVE_SIZE = 32 * 1024 * 1024
MAX_MEMBER_SIZE = 2 * 1024 * 1024
MAX_UNCOMPRESSED_SIZE = 32 * 1024 * 1024
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
ROOT_FILES = (
    "VERSION", "SKILL.md", "MCP.md", "QUICKSTART.md",
    "EVALUATION.md", "REAL_EVALUATION.md", "RELEASE_NOTES_v2.md", "RELEASE_NOTES_v21.md", "RELEASE_NOTES_v22.md", "RELEASE_NOTES_v23.md", "BETA_GUIDE.md", "LICENSE",
    "requirements.txt", "requirements-mcp.txt",
)


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_target(path: Path) -> Path:
    """Require a non-alias path and an existing canonical parent."""
    target = path.expanduser().absolute()
    if target.name in {"", ".", ".."} or not target.name:
        raise ValueError("Choose a new named destination directory")
    parent = target.parent.resolve(strict=True)
    if parent != target.parent or not parent.is_dir():
        raise ValueError("Destination parent must be an existing canonical directory")
    if target.exists() or target.is_symlink():
        raise ValueError("Destination already exists; never overwrite or merge installations")
    return target


def _members() -> list[tuple[str, bytes]]:
    if not VERSION_FILE.is_file() or VERSION_FILE.read_text(encoding="utf-8").strip() != RELEASE_VERSION:
        raise ValueError("VERSION does not match release builder")
    files = [Path(name) for name in ROOT_FILES]
    files.extend(sorted(Path("scripts") / p.name for p in (ROOT / "scripts").glob("*.py")))
    files.extend(sorted(Path("references") / p.name for p in (ROOT / "references").glob("*.md")))
    if len(files) < 20:
        raise ValueError("Expected source files missing")
    result = []
    for relative in files:
        source = ROOT / relative
        if source.is_symlink() or not source.is_file() or source.resolve() != source:
            raise ValueError("Release source must be a regular, non-symlink file")
        if source.stat().st_size > MAX_MEMBER_SIZE:
            raise ValueError("Release source file too large")
        content = source.read_bytes()
        if len(content) > MAX_MEMBER_SIZE:
            raise ValueError("Release source changed size during packaging")
        result.append((relative.as_posix(), content))
    if len({name for name, _ in result}) != len(result):
        raise ValueError("Duplicate release file")
    return result


def _zipinfo(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def _manifest(entries: list[tuple[str, bytes]]) -> bytes:
    document = {
        "schema": 1,
        "name": ARCHIVE_ROOT,
        "version": RELEASE_VERSION,
        "security_notice": "SHA256 detects changes but is not a digital signature or proof of publisher identity.",
        "files": {name: {"sha256": _sha(data), "bytes": len(data)}
                  for name, data in entries},
    }
    return (json.dumps(document, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def build(destination: Path) -> dict:
    """Write exclusive artifact files; no installed environment is touched."""
    entries = _members()
    output_dir = destination.expanduser().resolve(strict=True)
    if not output_dir.is_dir():
        raise ValueError("Output must be an existing directory")
    target = output_dir / f"jechulok-agent-skill-v{RELEASE_VERSION}.zip"
    sidecar = output_dir / f"jechulok-agent-skill-v{RELEASE_VERSION}.sha256"
    if target.exists() or sidecar.exists() or target.is_symlink() or sidecar.is_symlink():
        raise ValueError("Release artifact exists; never overwrite it")
    if sum(len(data) for _, data in entries) > MAX_UNCOMPRESSED_SIZE:
        raise ValueError("Release would exceed safe uncompressed limit")
    created_zip = False
    created_checksum = False
    try:
        # Exclusive create avoids replacing pre-existing files.
        with target.open("xb") as fp:
            created_zip = True
            with zipfile.ZipFile(fp, "w") as archive:
                for name, content in entries:
                    archive.writestr(_zipinfo(f"{ARCHIVE_ROOT}/{name}"), content)
                archive.writestr(_zipinfo(MANIFEST_NAME), _manifest(entries))
        checked = verify(target)
        with sidecar.open("x", encoding="utf-8", newline="\n") as fp:
            created_checksum = True
            fp.write(f"{checked['archive_sha256']}  {target.name}\n")
    except BaseException:
        # Never delete a concurrently created user file if exclusive open
        # failed before this process owned the artifact.
        if created_zip:
            target.unlink(missing_ok=True)
        if created_checksum:
            sidecar.unlink(missing_ok=True)
        raise
    return {**checked, "status": "built", "archive": str(target), "checksum_file": str(sidecar),
            "client_settings_changed": False, "user_files_read": False}


def verify(archive_path: Path) -> dict:
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ValueError("Archive missing or is a symlink")
    if archive_path.stat().st_size > MAX_ARCHIVE_SIZE:
        raise ValueError("Archive exceeds size limit")
    with zipfile.ZipFile(archive_path, "r") as z:
        infos = z.infolist()
        if len(infos) > 128 or not infos or len({i.filename for i in infos}) != len(infos):
            raise ValueError("Invalid release entry count or duplicated paths")
        if sum(i.file_size for i in infos) > MAX_UNCOMPRESSED_SIZE:
            raise ValueError("Archive exceeds uncompressed size limit")
        for info in infos:
            path = PurePosixPath(info.filename)
            if (info.is_dir() or path.is_absolute() or ".." in path.parts
                    or not info.filename.startswith(ARCHIVE_ROOT + "/")
                    or "\\" in info.filename
                    or info.file_size > MAX_MEMBER_SIZE
                    or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK):
                raise ValueError("Archive has an unsafe path, oversized or symlink entry")
        if MANIFEST_NAME not in z.namelist():
            raise ValueError("Missing release manifest")
        meta = json.loads(z.read(MANIFEST_NAME))
        if (type(meta) is not dict or meta.get("schema") != 1
                or meta.get("name") != ARCHIVE_ROOT
                or meta.get("version") != RELEASE_VERSION
                or type(meta.get("files")) is not dict):
            raise ValueError("Unexpected release manifest")
        files = meta["files"]
        if set(z.namelist()) != ({MANIFEST_NAME} | {f"{ARCHIVE_ROOT}/{n}" for n in files}):
            raise ValueError("Archive files do not match its manifest")
        if "VERSION" not in files or "scripts/mcp_server.py" not in files:
            raise ValueError("Incomplete release")
        if z.read(f"{ARCHIVE_ROOT}/VERSION").strip() != RELEASE_VERSION.encode():
            raise ValueError("Archive version mismatch")
        for relative, declared in files.items():
            path = PurePosixPath(relative)
            if (type(relative) is not str or not relative
                    or path.is_absolute() or ".." in path.parts or "\\" in relative
                    or path.as_posix() != relative
                    or type(declared) is not dict
                    or set(declared) != {"bytes", "sha256"}
                    or type(declared["bytes"]) is not int
                    or declared["bytes"] > MAX_MEMBER_SIZE
                    or type(declared["sha256"]) is not str):
                raise ValueError("Invalid archive manifest path or length")
            actual = z.read(f"{ARCHIVE_ROOT}/{relative}")
            if len(actual) != declared["bytes"] or _sha(actual) != declared["sha256"]:
                raise ValueError("Checksum mismatch")
    return {
        "status": "verified", "version": RELEASE_VERSION,
        "file_count": len(files),
        "archive_sha256": _sha(archive_path.read_bytes()),
        "authenticity_verified": False,
        "note": "Checksum checks consistency only. Obtain artifacts from a trusted repository release.",
    }


def extract(archive_path: Path, destination: Path, *, execute: bool = False) -> dict:
    checked = verify(archive_path)
    target = _canonical_target(destination)
    if not execute:
        return {**checked, "status": "planned", "destination": str(target),
                "files_created": 0, "confirmation_required": True}
    # Never extract into the original skill root itself or modify an
    # existing working directory. Rollback the staging folder on errors.
    stage = Path(tempfile.mkdtemp(prefix=".jechulok-release-", dir=str(target.parent)))
    try:
        with zipfile.ZipFile(archive_path, "r") as z:
            verified_manifest = z.read(MANIFEST_NAME)
            files = json.loads(verified_manifest)["files"]
            for rel in sorted(files):
                path = stage / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as fp:
                    fp.write(z.read(f"{ARCHIVE_ROOT}/{rel}"))
        # Persist the exact manifest from the verified archive for local
        # read-only doctor checks. This attests file consistency only.
        with (stage / "MANIFEST.json").open("xb") as fp:
            fp.write(verified_manifest)
        if target.exists() or target.is_symlink():
            raise ValueError("Destination changed during extraction")
        stage.rename(target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {
        "status": "extracted", "version": RELEASE_VERSION,
        "file_count": checked["file_count"], "destination": str(target),
        "old_installation_modified": False, "client_settings_modified": False,
        "dependencies_installed": False,
        "next_step": "Run scripts/setup_mcp.py install --allowed-dir YOUR_FOLDER from the NEW destination, then review its new client config. Keep the old install to roll back.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="JeChulOK v2.3 offline release packaging / verification")
    sub = p.add_subparsers(dest="command", required=True)
    pack = sub.add_parser("build")
    pack.add_argument("--output-dir", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--archive", type=Path, required=True)
    unpack = sub.add_parser("extract")
    unpack.add_argument("--archive", type=Path, required=True)
    unpack.add_argument("--destination", type=Path, required=True)
    unpack.add_argument("--execute", action="store_true",
                        help="Explicitly create a NEW installation; never change an existing one")
    args = p.parse_args(argv)
    try:
        result = (
            build(args.output_dir) if args.command == "build"
            else verify(args.archive) if args.command == "verify"
            else extract(args.archive, args.destination, execute=args.execute)
        )
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        result = {"status": "error", "message": str(exc)}
        print(json.dumps(result, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

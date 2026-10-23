#!/usr/bin/env python3
"""JeChulOK v0.9 installation, local diagnostics and opt-in MCP client config.

Standard-library only. Importing the module never installs dependencies,
edits Codex/Claude/Cursor settings, or launches the MCP server.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

SKILL_ROOT = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = SKILL_ROOT / "scripts" / "mcp_server.py"
REQUIREMENTS = SKILL_ROOT / "requirements-mcp.txt"
VENV_PATH = SKILL_ROOT / ".venv"
CLIENTS = ("codex", "cursor", "claude-desktop")


def venv_python(root: Path = VENV_PATH) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def allowed_directory(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("--allowed-dir must be a non-empty directory")
    original = Path(value).expanduser().absolute()
    canonical = original.resolve(strict=True)
    if canonical != original:
        raise ValueError("Allowed directory must be canonical, without symlinks or '..' aliases")
    if not canonical.is_dir():
        raise ValueError("Allowed directory must exist")
    return canonical


def client_configuration(client: str, python_path: Path, allowed_root: Path) -> str:
    """Render a standalone, COPY-ONLY config snippet; never edits app settings."""
    if client not in CLIENTS:
        raise ValueError("Unsupported MCP client")
    command = str(python_path.resolve(strict=False))
    script = str(SERVER_SCRIPT)
    environment = {"JECHULOK_ALLOWED_DIRS": str(allowed_root)}
    if client == "codex":
        # JSON string literals are valid TOML basic strings and properly quote
        # Windows paths, tabs, newlines and embedded quotation marks.
        return (
            "[mcp_servers.jechulok]\n"
            "command = " + json.dumps(command, ensure_ascii=False) + "\n"
            "args = [" + json.dumps(script, ensure_ascii=False) + "]\n"
            "[mcp_servers.jechulok.env]\n"
            "JECHULOK_ALLOWED_DIRS = "
            + json.dumps(str(allowed_root), ensure_ascii=False) + "\n"
        )
    config = {
        "mcpServers": {
            "jechulok": {
                "command": command,
                "args": [script],
                "env": environment,
            }
        }
    }
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"


def environment_report(allowed_root: Path, python_path: Path) -> dict[str, object]:
    """Only read local interpreter and folder metadata: no files are created."""
    checks: list[dict[str, object]] = []
    checks.append({
        "id": "python_version", "passed": sys.version_info >= (3, 11),
        "detail": f"{sys.version_info.major}.{sys.version_info.minor}",
        "fix": "Install Python 3.11 or newer." if sys.version_info < (3, 11) else None,
    })
    checks.append({
        "id": "allowed_directory", "passed": allowed_root.is_dir(),
        "detail": "Exists" if allowed_root.is_dir() else "Missing",
        "fix": None if allowed_root.is_dir() else "Create your allowed work directory first.",
    })
    checks.append({
        "id": "directory_access",
        "passed": os.access(allowed_root, os.R_OK | os.X_OK | os.W_OK),
        "detail": "OS-level read/write/traversal permission check only",
        "fix": "Choose a directory you can read and write; permissions are not guaranteed at runtime.",
    })
    checks.append({
        "id": "server_script", "passed": SERVER_SCRIPT.is_file(),
        "detail": "Present" if SERVER_SCRIPT.is_file() else "Missing",
        "fix": "Reinstall or restore the JeChulOK source files.",
    })
    checks.append({
        "id": "python_environment", "passed": python_path.is_file(),
        "detail": "Virtual environment interpreter available" if python_path.is_file() else "Virtual environment interpreter missing",
        "fix": "Run 'install --allowed-dir YOUR_FOLDER' to create the isolated environment.",
    })
    if python_path.is_file():
        snippet = (
            "import json\n"
            "import PIL, pypdf\n"
            "from mcp.server import MCPServer\n"
            "print(json.dumps({'imports':'ok'}))\n"
        )
        try:
            outcome = subprocess.run(
                [str(python_path), "-c", snippet], capture_output=True,
                text=True, timeout=15, check=False,
            )
            ready = outcome.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ready = False
        checks.append({
            "id": "mcp_dependencies", "passed": ready,
            "detail": "Pillow, pypdf and MCPServer import test",
            "fix": None if ready else "Run 'install --allowed-dir YOUR_FOLDER' to install MCP dependencies.",
        })
    else:
        checks.append({
            "id": "mcp_dependencies", "passed": False,
            "detail": "Skipped: Python virtual environment missing",
            "fix": "Install the dependencies in the isolated virtual environment.",
        })
    return {
        "status": "pass" if all(x["passed"] for x in checks) else "needs_setup",
        "checks": checks,
        "server_transport": "local_stdio_only",
        "config_modified": False,
        "remote_files_uploaded": False,
        "limits": "This diagnostics tool checks the environment only; it never verifies a real institutional submission.",
    }


def install(allowed_root: Path) -> dict[str, object]:
    """Perform user-requested installation only; never register an MCP client."""
    if sys.version_info < (3, 11):
        raise ValueError("Python 3.11 or newer is required")
    if VENV_PATH.is_symlink():
        raise ValueError("Refusing to use a symlinked virtual environment")
    if not REQUIREMENTS.is_file() or not SERVER_SCRIPT.is_file():
        raise ValueError("Skill requirements or MCP server is missing")
    if not VENV_PATH.exists():
        venv.EnvBuilder(with_pip=True, clear=False).create(str(VENV_PATH))
    python_path = venv_python()
    if not python_path.is_file():
        raise ValueError("Virtual environment Python executable was not created")
    completed = subprocess.run(
        [str(python_path), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        cwd=str(SKILL_ROOT), check=False,
    )
    if completed.returncode:
        raise RuntimeError("Dependency installation failed; inspect pip output above")
    report = environment_report(allowed_root, python_path)
    if report["status"] != "pass":
        raise RuntimeError("Dependencies were installed but diagnostics reported a problem")
    return {
        "status": "installed",
        "isolated_python": str(python_path),
        "allowed_directory": str(allowed_root),
        "client_settings_modified": False,
        "next_step": "Run the config command and manually add the generated snippet to your MCP client.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="JeChulOK local-only MCP setup. Never changes client settings."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "doctor", "config"):
        cmd = sub.add_parser(command)
        cmd.add_argument("--allowed-dir", required=True,
                         help="Existing canonical local directory containing your submission files")
        if command == "config":
            cmd.add_argument("--client", choices=CLIENTS, default="codex")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = allowed_directory(args.allowed_dir)
        if args.command == "install":
            result = install(root)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "doctor":
            result = environment_report(root, venv_python())
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "pass" else 1
        if args.command == "config":
            print(client_configuration(args.client, venv_python(), root), end="")
            return 0
        return 2
    except (ValueError, OSError, RuntimeError) as exc:
        print("JeChulOK setup: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

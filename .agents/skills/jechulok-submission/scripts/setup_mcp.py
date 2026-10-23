#!/usr/bin/env python3
"""JeChulOK v1.1 installation, local diagnostics and opt-in MCP client config.

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
PROBE_SCRIPT = SKILL_ROOT / "scripts" / "connection_probe.py"


def venv_python(root: Path | None = None) -> Path:
    root = VENV_PATH if root is None else root
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
    # Do not resolve interpreter symlinks: venv/bin/python often points to the
    # global Python binary, but must be invoked through the venv path.
    command = str(python_path.absolute())
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



def probe_connection(allowed_root: Path, python_path: Path, *, timeout: int = 35) -> dict[str, object]:
    """Invoke isolated subprocess; probe never reads user files or changes config."""
    if not python_path.is_file():
        return {
            "status": "needs_setup", "code": "venv_missing",
            "fix": "Run install --allowed-dir YOUR_FOLDER first.",
            "client_config_modified": False, "files_processed": 0,
        }
    if not PROBE_SCRIPT.is_file() or not SERVER_SCRIPT.is_file():
        return {
            "status": "needs_setup", "code": "server_missing",
            "fix": "Restore JeChulOK local scripts and retry.",
            "client_config_modified": False, "files_processed": 0,
        }
    try:
        outcome = subprocess.run(
            [str(python_path), str(PROBE_SCRIPT), "--allowed-dir", str(allowed_root)],
            cwd=str(SKILL_ROOT), capture_output=True, text=True,
            encoding="utf-8", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "needs_attention", "code": "connection_timeout",
            "fix": "MCP server did not answer in time. Verify your virtual environment and local security policies.",
            "client_config_modified": False, "files_processed": 0,
        }
    except OSError:
        return {
            "status": "needs_attention", "code": "python_launch_failed",
            "fix": "The virtualenv Python could not launch. Recreate the .venv using install.",
            "client_config_modified": False, "files_processed": 0,
        }
    try:
        result = json.loads(outcome.stdout.strip())
    except (json.JSONDecodeError, TypeError):
        return {
            "status": "needs_attention", "code": "unexpected_probe_output",
            "fix": "The child process returned no valid JSON. Confirm the correct Python/MCP SDK and reinstall if needed.",
            "client_config_modified": False, "files_processed": 0,
        }
    if not isinstance(result, dict) or result.get("status") not in {
        "pass", "needs_attention", "needs_setup"
    }:
        return {
            "status": "needs_attention", "code": "invalid_probe_result",
            "fix": "The local MCP handshake returned an invalid result. Check installation.",
            "client_config_modified": False, "files_processed": 0,
        }
    if outcome.returncode != 0 and result.get("status") == "pass":
        return {
            "status": "needs_attention", "code": "probe_exit_mismatch",
            "fix": "The probe exited abnormally. Check installation.",
            "client_config_modified": False, "files_processed": 0,
        }
    # Never expose arbitrary child-process fields (including potential paths).
    return {
        "status": result["status"],
        "code": str(result.get("code", "probe_unknown"))[:64],
        "tool_count": result.get("tool_count"),
        "missing_tools": result.get("missing_tools", [])[:20] if isinstance(result.get("missing_tools", []), list) else [],
        "fix": str(result.get("fix", ""))[:300] or None,
        "mcp_transport": "local_stdio",
        "client_config_modified": False,
        "files_processed": 0,
        "limitation": "Local MCP handshake only. Does not verify whether Codex/Cursor/Claude Desktop loaded its configuration.",
    }

def prepare_upgrade(archive: Path, destination: Path, *, execute: bool) -> dict[str, object]:
    """Offline side-by-side upgrade: never patch live venv or MCP client settings."""
    from release_v20 import extract
    result = extract(archive, destination, execute=execute)
    return {
        **result,
        "upgrade_method": "side_by_side_local_archive",
        "old_virtualenv_changed": False,
        "live_mcp_sessions_changed": False,
        "automatic_client_reregistration": False,
        "rollback": "Keep the old installation and original MCP client config unchanged until the new local server has passed doctor/probe and explicit client config review.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="JeChulOK local-only MCP setup. Never changes client settings."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "doctor", "config", "probe", "status", "upgrade"):
        cmd = sub.add_parser(command)
        cmd.add_argument("--allowed-dir", required=True,
                         help="Existing canonical local directory containing your submission files")
        if command == "config":
            cmd.add_argument("--client", choices=CLIENTS, default="codex")
        if command == "upgrade":
            cmd.add_argument("--archive", type=Path, required=True,
                             help="Trusted locally downloaded v2.0 release ZIP")
            cmd.add_argument("--destination", type=Path, required=True,
                             help="NEW empty/nonexistent destination folder, never the current installation")
            cmd.add_argument("--execute", action="store_true",
                             help="Create the new side-by-side copy after preview")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = allowed_directory(args.allowed_dir)
        if args.command == "upgrade":
            result = prepare_upgrade(args.archive, args.destination, execute=args.execute)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
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
        if args.command == "probe":
            result = probe_connection(root, venv_python())
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "pass" else 1
        if args.command == "status":
            doctor = environment_report(root, venv_python())
            connection = (
                probe_connection(root, venv_python())
                if doctor["status"] == "pass"
                else {
                    "status": "skipped",
                    "code": "doctor_first",
                    "fix": "Resolve the failing doctor checks before attempting a connection.",
                }
            )
            passed = doctor["status"] == "pass" and connection["status"] == "pass"
            result = {
                "status": "pass" if passed else "needs_attention",
                "doctor": doctor, "connection": connection,
                "client_config_modified": False,
                "files_processed": 0,
                "limitations": "Local health check only; not proof of host client registration or real submission.",
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if passed else 1
        return 2
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print("JeChulOK setup: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""v2.9: strictly opt-in, read-only local MCP client config diagnostics.

Only a file explicitly named by the operator is opened. Configs may contain
secrets for other MCP services: never echo their values, paths or raw errors.
This is a file comparison, NOT proof that an app loaded or started the server.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tomllib
from typing import Any

CLIENTS = ("codex", "cursor", "claude-desktop")
MAX_CONFIG_BYTES = 128 * 1024
FIELDS = ("command", "args", "env")


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Repeated JSON field")
        result[key] = value
    return result


def _read_explicit_config(filename: Path) -> str:
    """Reject linked, noncanonical, oversized and nonregular inputs."""
    target = filename.expanduser().absolute()
    if not target.is_absolute() or target.is_symlink() or target.resolve(strict=True) != target:
        raise ValueError("Unsafe explicit config file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(target, flags)
    with os.fdopen(fd, "rb") as stream:
        details = os.fstat(stream.fileno())
        if not stat.S_ISREG(details.st_mode) or details.st_size > MAX_CONFIG_BYTES:
            raise ValueError("Config input type/size not allowed")
        data = stream.read(MAX_CONFIG_BYTES + 1)
    if len(data) > MAX_CONFIG_BYTES:
        raise ValueError("Config input too large")
    return data.decode("utf-8-sig")


def _result(status: str, code: str, client: str, *, read: bool,
            checks: dict[str, bool] | None = None) -> dict[str, Any]:
    advice = {
        "config_file_missing": "Choose the actual MCP configuration file in your client and retry.",
        "config_file_unsafe": "Choose an existing canonical, regular, non-symlink file (at most 128 KiB).",
        "config_format_invalid": "Review the TOML/JSON syntax locally; do not share config values or tokens.",
        "server_entry_missing": "Generate a copy-only snippet and merge the jechulok entry manually.",
        "server_entry_invalid": "The jechulok server entry must be an object/table. Review its structure.",
        "command_mismatch": "Compare the server command with the isolated .venv Python in the generated snippet.",
        "args_mismatch": "The server args must contain only the installed mcp_server.py script.",
        "allowed_directory_mismatch": "Verify JECHULOK_ALLOWED_DIRS matches the folder explicitly chosen for this installation.",
        "config_matches": "Restart the MCP host and check its own server status. Use probe separately for local stdio.",
    }
    return {
        "schema": "jechulok-client-config-audit-v29", "status": status,
        "reason_code": code, "client": client,
        "checks": checks if checks is not None else {},
        "instruction": advice[code],
        "suggested_command": (
            f"python scripts/setup_mcp.py config --client {client} --allowed-dir YOUR_FOLDER"
            if code not in {"config_matches", "config_file_missing", "config_file_unsafe"}
            else None
        ),
        "explicit_config_file_read": read,
        "config_values_disclosed": False, "config_file_modified": False,
        "client_settings_modified": False, "server_launched": False,
        "network_used": False, "submission_documents_read": False,
        "mcp_host_registration_verified": False, "mcp_connection_verified": False,
        "note": "A matching file does not prove the client loaded it or that the local MCP server works.",
    }


def audit_client_config(client: str, filename: Path,
                        expected: dict[str, Any]) -> dict[str, Any]:
    """Compare exact local stdio registration without leaking config data."""
    if client not in CLIENTS:
        raise ValueError("Unsupported MCP client")
    if (type(expected) is not dict or type(expected.get("command")) is not str
            or type(expected.get("args")) is not list
            or type(expected.get("env")) is not dict):
        raise ValueError("Invalid expected client configuration")
    try:
        raw = _read_explicit_config(filename)
    except FileNotFoundError:
        return _result("needs_setup", "config_file_missing", client, read=False)
    except (OSError, ValueError, UnicodeError, RuntimeError):
        return _result("needs_attention", "config_file_unsafe", client, read=False)
    try:
        if client == "codex":
            parsed = tomllib.loads(raw)
            group = parsed.get("mcp_servers")
        else:
            parsed = json.loads(raw, object_pairs_hook=_unique_keys,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            group = parsed.get("mcpServers") if type(parsed) is dict else None
    except (ValueError, TypeError, tomllib.TOMLDecodeError):
        return _result("needs_attention", "config_format_invalid", client, read=True)
    if type(group) is not dict or "jechulok" not in group:
        return _result("needs_setup", "server_entry_missing", client, read=True)
    actual = group["jechulok"]
    if type(actual) is not dict:
        return _result("needs_attention", "server_entry_invalid", client, read=True)
    env = actual.get("env")
    checks = {
        "command_matches": type(actual.get("command")) is str
                          and actual["command"] == expected["command"],
        "args_match": type(actual.get("args")) is list
                      and actual["args"] == expected["args"],
        "allowed_directory_matches": type(env) is dict
                      and type(env.get("JECHULOK_ALLOWED_DIRS")) is str
                      and env["JECHULOK_ALLOWED_DIRS"] == expected["env"].get("JECHULOK_ALLOWED_DIRS"),
    }
    code = "config_matches"
    for name, mismatch_code in (
        ("command_matches", "command_mismatch"),
        ("args_match", "args_mismatch"),
        ("allowed_directory_matches", "allowed_directory_mismatch"),
    ):
        if not checks[name]:
            code = mismatch_code
            break
    return _result("pass" if code == "config_matches" else "needs_attention",
                   code, client, read=True, checks=checks)

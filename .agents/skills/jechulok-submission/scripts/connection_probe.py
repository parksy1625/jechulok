#!/usr/bin/env python3
"""JeChulOK v1.1: probe an actual local stdio MCP connection (read only).

Run this under the isolated .venv Python. No personal files are opened,
client configuration is never changed, and no file tools are invoked.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters
from setup_mcp import allowed_directory, SERVER_SCRIPT

EXPECTED_TOOLS = frozenset({
    "check_file", "prepare_image", "extract_pdf_pages", "verify_submission",
    "parse_submission_rules", "prepare_from_requirements",
    "analyze_submission_notice", "prepare_submission_batch",
    "suggest_submission_files", "suggest_submission_output_paths",
    "review_submission_plan", "verify_submission_package",
    "guide_submission_workflow", "create_submission_html_report",
    "start_submission_job", "get_submission_job", "cancel_submission_job",
    "list_interrupted_submission_jobs", "resolve_interrupted_submission_job",
    "assist_submission",
})
PROBE_RULE = "JPG 300×400px 500KB 이하"


async def probe(allowed_root: Path) -> dict[str, object]:
    """Handshake, discover public tool metadata, and parse only synthetic text."""
    config = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        env={"JECHULOK_ALLOWED_DIRS": str(allowed_root)},
    )
    async with asyncio.timeout(15):
        async with Client(config) as client:
            listing = await client.list_tools()
            names = {tool.name for tool in listing.tools}
            missing = sorted(EXPECTED_TOOLS - names)
            response = await client.call_tool(
                "parse_submission_rules", {"requirements_text": PROBE_RULE}
            ) if not missing else None

    if missing:
        return {
            "status": "needs_attention", "code": "tools_missing",
            "mcp_transport": "local_stdio",
            "tool_count": len(names),
            "missing_tools": missing,
            "fix": "Check that the MCP server comes from the same JeChulOK version; update the local skill and retry.",
            "client_config_modified": False, "files_processed": 0,
        }
    if response is None or response.is_error or (
        response.structured_content or {}
    ).get("status") != "parsed":
        return {
            "status": "needs_attention", "code": "tool_call_failed",
            "mcp_transport": "local_stdio",
            "tool_count": len(names),
            "fix": "MCP connected but its synthetic rule parser failed. Confirm compatible dependencies and retry installation.",
            "client_config_modified": False, "files_processed": 0,
        }
    return {
        "status": "pass", "code": "mcp_handshake_ok",
        "mcp_transport": "local_stdio",
        "tool_count": len(names), "synthetic_rule_parse": "pass",
        "client_config_modified": False, "files_processed": 0,
        "limitation": (
            "This proves this local subprocess responds to MCP calls, not that Codex, "
            "Cursor or Claude Desktop have loaded their configuration."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only JeChulOK local MCP handshake")
    parser.add_argument("--allowed-dir", required=True)
    args = parser.parse_args(argv)
    try:
        root = allowed_directory(args.allowed_dir)
        result = asyncio.run(probe(root))
    except (OSError, RuntimeError, ValueError, TimeoutError, ExceptionGroup) as exc:
        result = {
            "status": "needs_attention",
            "code": "connection_failed",
            "error_type": type(exc).__name__,
            "fix": "Check the allowed directory, isolated Python environment, and MCP server; run doctor and retry.",
            "client_config_modified": False,
            "files_processed": 0,
        }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

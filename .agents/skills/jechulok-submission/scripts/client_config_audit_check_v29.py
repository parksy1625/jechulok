#!/usr/bin/env python3
"""Deterministic synthetic v2.9 audit. Never reads actual MCP settings."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from client_config_audit_v29 import audit_client_config


def check() -> dict:
    expected = {"command": "/FAKE/venv/bin/python",
                "args": ["/FAKE/scripts/mcp_server.py"],
                "env": {"JECHULOK_ALLOWED_DIRS": "/FAKE/allowed"}}
    results = []
    with tempfile.TemporaryDirectory(prefix="jechulok-v29-synthetic-") as temporary:
        folder = Path(temporary).resolve()
        p = folder / "fake-mcp.json"
        valid = {"mcpServers": {"jechulok": {**expected},
                                "another": {"token": "SYNTHETIC_NOT_A_REAL_SECRET"}}}
        p.write_text(json.dumps(valid), encoding="utf-8")
        matched = audit_client_config("cursor", p, expected)
        results.append(("synthetic_match", matched["status"] == "pass"
                        and not matched["mcp_host_registration_verified"]))
        results.append(("secret_not_reported", "SYNTHETIC_NOT_A_REAL_SECRET" not in json.dumps(matched)))
        valid["mcpServers"]["jechulok"]["command"] = "wrong-command"
        p.write_text(json.dumps(valid), encoding="utf-8")
        wrong = audit_client_config("cursor", p, expected)
        results.append(("wrong_command_hold", wrong["reason_code"] == "command_mismatch"))
        p.write_text('{"mcpServers":{},"mcpServers":{"jechulok":{}}}', encoding="utf-8")
        duplicate = audit_client_config("cursor", p, expected)
        results.append(("duplicate_json_rejected", duplicate["reason_code"] == "config_format_invalid"))
        results.append(("missing_file_hold", audit_client_config(
            "cursor", folder / "missing.json", expected)["reason_code"] == "config_file_missing"))
        results.append(("no_automatic_actions", all(
            not report[key] for report in (matched, wrong, duplicate)
            for key in ("network_used", "server_launched", "client_settings_modified", "submission_documents_read")
        )))
    return {
        "suite": "jechulok_v29_client_config_synthetic", "status": "pass" if all(v for _, v in results) else "fail",
        "scenario_count": len(results), "passed_cases": sum(v for _, v in results),
        "scenarios": [{"id": k, "passed": v} for k, v in results],
        "actual_client_configurations_opened": 0, "host_registration_verified": False,
        "network_used": False, "telemetry_sent": False, "user_documents_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args()
    result = check()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

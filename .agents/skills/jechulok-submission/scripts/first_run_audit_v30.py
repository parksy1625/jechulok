#!/usr/bin/env python3
"""v3.0 synthetic-only, no-host no-file first-run protocol verification."""
from __future__ import annotations

import argparse
import json

from first_run_checkup_v30 import checkup, render_text


def run() -> dict:
    names = ("skill_version", "source_manifest", "python_version",
             "allowed_directory", "directory_access", "server_script",
             "python_environment", "mcp_dependencies")
    healthy = {"status": "pass", "checks": [
        {"id": n, "passed": True, "verified": n == "source_manifest"} for n in names]}
    corrupted = {"status": "needs_setup", "checks": [
        {"id": n, "passed": n != "source_manifest"} for n in names]}
    probe = {"status": "pass", "tool_count": 20}
    config = {"status": "pass", "reason_code": "config_matches", "checks": {
        "command_matches": True, "args_match": True, "allowed_directory_matches": True}}
    normal = checkup(healthy)
    guarded = checkup(corrupted, probe_requested=True, config_requested=True)
    middle = checkup(healthy, probe_requested=True, probe=probe)
    ready = checkup(healthy, probe_requested=True, probe=probe,
                    config_requested=True, config=config)
    tampered = checkup(healthy, probe_requested=True, probe=probe,
                      config_requested=True, config={"status": "pass"})
    scenarios = (
        ("no_implicit_check", normal["next_action"] == "opt_in_probe"
         and normal["checks"]["client_config"] == "not_requested"),
        ("corruption_gate", guarded["next_action"] == "upgrade"
         and guarded["checks"]["local_mcp_probe"] == "skipped_due_to_installation"),
        ("explicit_probe_only", middle["next_action"] == "opt_in_config_audit"),
        ("host_confirmation_required", ready["status"] == "ready_for_manual_host_check"
         and ready["mcp_host_registration_verified"] is False),
        ("fake_success_rejected", tampered["next_action"] == "review_client_config"),
        ("redacted_accessible_output", "\x1b" not in render_text(ready)
         and "/home/" not in json.dumps(ready)
         and not ready["client_config_modified"]),
    )
    return {
        "suite": "jechulok_v30_first_run_synthetic",
        "status": "pass" if all(ok for _, ok in scenarios) else "fail",
        "scenario_count": len(scenarios), "passed_cases": sum(ok for _, ok in scenarios),
        "scenarios": [{"id": name, "passed": ok} for name, ok in scenarios],
        "real_mcp_host_launched": False, "client_configuration_files_read": 0,
        "network_used": False, "telemetry_sent": False, "user_files_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", required=True, action="store_true")
    parser.parse_args()
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

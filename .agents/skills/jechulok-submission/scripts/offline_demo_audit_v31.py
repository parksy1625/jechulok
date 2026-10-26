#!/usr/bin/env python3
"""Six entirely synthetic v3.1 smoke/audit cases; no personal inputs."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
from unittest.mock import patch

from offline_demo_v31 import STAGES, main, run_rehearsal


def run_audit() -> dict:
    results: list[dict[str, object]] = []

    def case(name: str, passed: bool) -> None:
        results.append({"id": name, "status": "pass" if passed else "fail"})

    first = run_rehearsal()
    second = run_rehearsal()
    case("real_local_jpg_pdf_pipeline", first["status"] == "pass")
    case("deterministic_without_paths", first == second and "/tmp" not in json.dumps(first))
    case("six_stages_and_cleanup", [s["id"] for s in first["stages"]] == list(STAGES)
         and all(s["status"] == "pass" for s in first["stages"]))
    with patch("offline_demo_v31.parse_requirements", side_effect=ValueError("private-path-secret")):
        failure = run_rehearsal()
    case("requirements_fail_closed", failure["status"] == "fail"
         and failure.get("failure_stage") == "requirements"
         and failure["stages"][-1]["status"] == "pass"
         and "private-path-secret" not in json.dumps(failure))
    with patch("offline_demo_v31.prepare_image", side_effect=OSError("private-path-secret")):
        failure = run_rehearsal()
    case("converter_fail_closed", failure["status"] == "fail"
         and failure.get("failure_stage") == "image_prepare"
         and failure["stages"][-1]["status"] == "pass"
         and "private-path-secret" not in json.dumps(failure))
    with contextlib.redirect_stdout(io.StringIO()) as preview:
        code = main(["--format", "json"])
    no_run = json.loads(preview.getvalue())
    case("preview_does_not_run", code == 0 and no_run["status"] == "not_run"
         and all(s["status"] == "not_run" for s in no_run["stages"]))
    return {
        "schema": "jechulok-v31-synthetic-audit", "status": "pass" if all(
            r["status"] == "pass" for r in results) else "fail",
        "scenario_count": len(results), "passed_count": sum(
            r["status"] == "pass" for r in results), "cases": results,
        "synthetic_only": True, "real_user_documents_tested": False,
        "client_configs_accessed": False, "network_used": False,
        "outputs_persisted": False, "external_submission_tested": False,
    }


def main_cli() -> int:
    parser = argparse.ArgumentParser(description="Explicit synthetic-only offline rehearsal audit")
    parser.add_argument("--check", action="store_true", help="Run six safe synthetic cases")
    args = parser.parse_args()
    if not args.check:
        parser.error("--check is required to create disposable synthetic files")
    report = run_audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())

"""v3.0 one-screen, read-only first-run checkup from existing diagnostics.

This module does not execute probes, open config files, install packages,
change permissions or register MCP clients. Callers explicitly collect only
the authorized checks, then pass their curated results here.
"""
from __future__ import annotations

from typing import Any

from onboarding_v22 import guide

CLIENTS = ("codex", "cursor", "claude-desktop")
LANGUAGES = ("ko", "en")

MESSAGES = {
    "doctor_failed": ("설치 환경 문제를 먼저 해결하세요.", "Fix the installation environment first."),
    "stdio_failed": ("로컬 MCP 통신이 실패했어요. probe 오류를 검토하세요.", "Local stdio MCP failed; review the probe error."),
    "config_failed": ("클라이언트 설정에 문제가 있어요. 설정값을 직접 검토하세요.", "Review the mismatched MCP client registration."),
    "run_probe": ("다음으로 로컬 MCP 연결 검사를 직접 승인하고 실행하세요.", "Next, explicitly authorize the local stdio probe."),
    "review_config": ("앱의 실제 MCP 설정 파일 경로를 직접 지정해 확인하세요. 토큰을 공유하지 마세요.", "Provide the actual client config path explicitly. Never share its tokens."),
    "check_host": ("준비 검사를 통과했어요. 앱을 재시작하고 MCP 도구 목록과 합성 문장 호출을 직접 확인하세요.", "Local checks passed. Restart the app and verify tools and a synthetic call in the MCP host."),
}

KNOWN_PROBE = {"pass", "needs_attention", "needs_setup"}
KNOWN_CONFIG = {"pass", "needs_attention", "needs_setup"}


def checkup(doctor: dict[str, Any], *, client: str = "codex", language: str = "ko",
            probe_requested: bool = False, probe: dict[str, Any] | None = None,
            config_requested: bool = False, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Select exactly one manual next step; never claim the MCP host is ready."""
    if client not in CLIENTS or language not in LANGUAGES:
        raise ValueError("Unsupported client or language")
    if (type(probe_requested) is not bool or type(config_requested) is not bool
            or (not probe_requested and probe is not None)
            or (not config_requested and config is not None)):
        raise ValueError("Invalid authorization state")

    guidance = guide(doctor, client=client, language=language)
    doctor_passed = doctor.get("status") == "pass" and guidance["status"] == "ready_for_probe"
    # Missing or invalid observations are never interpreted as a pass.
    connection_ok = (probe_requested and type(probe) is dict
                     and probe.get("status") == "pass" and probe.get("tool_count") == 20)
    config_ok = (config_requested and type(config) is dict and config.get("status") == "pass"
                 and config.get("reason_code") == "config_matches"
                 and type(config.get("checks")) is dict
                 and set(config["checks"]) == {
                     "command_matches", "args_match", "allowed_directory_matches"
                 } and all(config["checks"].get(k) is True for k in config["checks"]))
    flags = {
        "installation": "pass" if doctor_passed else "needs_setup",
        "local_mcp_probe": ("skipped_due_to_installation" if not doctor_passed and probe_requested
                            else "not_requested" if not probe_requested else
                            "pass" if connection_ok else "needs_attention"),
        "client_config": ("skipped_due_to_installation" if not doctor_passed and config_requested
                          else "not_requested" if not config_requested else
                          "pass" if config_ok else "needs_attention"),
    }
    if not doctor_passed:
        code = "doctor_failed"
        reason = guidance["reason_code"] if guidance["status"] == "needs_setup" else "unrecognized_doctor_failure"
        stage, status, action = 1, "needs_setup", guidance["next_action"]
        command = guidance["suggested_command"]
    elif probe_requested and not connection_ok:
        code, reason = "stdio_failed", "local_probe_incomplete"
        stage, status, action = 2, "needs_attention", "review_probe"
        command = "python scripts/setup_mcp.py probe --allowed-dir YOUR_FOLDER"
    elif config_requested and not config_ok:
        code, reason = "config_failed", "client_config_incomplete"
        stage, status, action = 3, "needs_attention", "review_client_config"
        command = f"python scripts/setup_mcp.py config --client {client} --allowed-dir YOUR_FOLDER"
    elif not probe_requested:
        code, reason = "run_probe", "probe_not_requested"
        stage, status, action = 2, "next_step", "opt_in_probe"
        command = "python scripts/setup_mcp.py checkup --probe --allowed-dir YOUR_FOLDER"
    elif not config_requested:
        code, reason = "review_config", "config_not_provided"
        stage, status, action = 3, "next_step", "opt_in_config_audit"
        command = (f"python scripts/setup_mcp.py checkup --probe --client {client} "
                   "--config-file YOUR_CONFIG_FILE --allowed-dir YOUR_FOLDER")
    else:
        code, reason = "check_host", None
        stage, status, action = 4, "ready_for_manual_host_check", "manually_verify_host"
        command = None

    return {
        "schema": "jechulok-first-run-v30", "status": status,
        "stage": stage, "total_stages": 4, "client": client,
        "language": language, "checks": flags,
        "reason_code": reason, "next_action": action,
        "instruction": MESSAGES[code][0 if language == "ko" else 1],
        "suggested_command": command,
        "probe_explicitly_requested": probe_requested,
        "config_explicitly_requested": config_requested,
        "source_manifest_verified": guidance["packaged_manifest_verified"],
        "network_used": False, "files_written": 0,
        "documents_read": False, "client_config_modified": False,
        "installation_performed": False, "automatic_host_registration": False,
        "mcp_host_registration_verified": False,
        "submission_accepted_or_verified": False,
        "limitation": "Local preflight only. Client-side MCP registration and real submissions require separate human verification.",
    }


def render_text(result: dict[str, Any]) -> str:
    """Accessible, no-color and no-path terminal summary."""
    ko = result["language"] == "ko"
    labels = (
        ("설치", "installation"), ("로컬 MCP", "local_mcp_probe"),
        ("클라이언트 설정", "client_config"),
    ) if ko else (
        ("Installation", "installation"), ("Local MCP", "local_mcp_probe"),
        ("Client config", "client_config"),
    )
    lines = ["제출OK 첫 실행 점검" if ko else "JeChulOK First-run Checkup",
             f"{'단계' if ko else 'Step'} {result['stage']}/{result['total_stages']}",
             f"{'상태' if ko else 'Status'}: {result['status']}"]
    for index, (label, key) in enumerate(labels, 1):
        lines.append(f"{index}. {label}: {result['checks'][key]}")
    lines.extend([result["instruction"],
                  f"{'다음 행동' if ko else 'Next action'}: {result['next_action']}"])
    if result["suggested_command"]:
        lines.append(("참고 명령(자동 실행 안 함): " if ko else "Suggested command (NOT executed): ")
                     + result["suggested_command"])
    lines.append("설정 변경·서류 업로드 없음" if ko else "No configuration changes or document uploads")
    return "\n".join(lines) + "\n"

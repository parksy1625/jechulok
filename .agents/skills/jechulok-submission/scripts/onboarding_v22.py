"""JeChulOK v2.2: deterministic, screen-reader-friendly setup/repair guide.

This module only interprets *existing* local doctor/probe observations.
It performs no writes, downloads, client configuration changes or scans
of application documents. All messages are curated; no arbitrary paths,
exceptions, subprocess logs or source filenames are copied into output.
"""
from __future__ import annotations

from typing import Any

ISSUE_PRIORITY = (
    "skill_version", "source_manifest", "python_version",
    "allowed_directory", "directory_access", "server_script",
    "python_environment", "mcp_dependencies",
)

# Each entry: Korean, English; fixed labels avoid echoing private paths.
LABELS = {
    "skill_version": ("설치 버전 정보", "Installation version metadata"),
    "source_manifest": ("배포 파일 무결성", "Release file consistency"),
    "python_version": ("Python 버전", "Python version"),
    "allowed_directory": ("허용 작업 폴더", "Allowed work folder"),
    "directory_access": ("작업 폴더 접근 권한", "Work folder permissions"),
    "server_script": ("MCP 서버 파일", "MCP server files"),
    "python_environment": ("전용 Python 환경", "Isolated Python environment"),
    "mcp_dependencies": ("MCP 필수 패키지", "MCP dependencies"),
}

# All repair instructions require a separate human decision; no repair
# command ever runs from this module. No actual path appears in commands.
ACTIONS = {
    "skill_version": (
        "버전 정보가 일치하지 않습니다. 실행을 중단하고 신뢰할 수 있는 ZIP을 새 폴더에 검증·설치하세요.",
        "VERSION and skill metadata disagree. Stop; verify a trusted ZIP and install into a NEW folder.",
        "upgrade", 1,
    ),
    "source_manifest": (
        "배포 파일이 변경됐거나 누락됐습니다. 실행하지 말고 원본 ZIP을 검증해 새 폴더에 설치하세요. 현재 설치를 자동 삭제하지 않습니다.",
        "Packaged files changed or are missing. Do not run them; verify the trusted ZIP and install into a NEW folder. The current installation is not deleted.",
        "upgrade", 1,
    ),
    "python_version": (
        "Python 3.11 이상을 설치한 뒤 새 터미널에서 다시 점검하세요.",
        "Install Python 3.11 or later, reopen the terminal, and check again.",
        "install_python", 1,
    ),
    "allowed_directory": (
        "개인 문서가 없는 전용 테스트 폴더를 직접 만든 뒤 해당 폴더로 다시 실행하세요.",
        "Create a dedicated test folder without personal documents and rerun against it.",
        "choose_folder", 1,
    ),
    "directory_access": (
        "읽기·쓰기 권한이 있는 별도 테스트 폴더를 선택하세요. 파일 권한을 자동으로 변경하지 않습니다.",
        "Choose another writable test folder. This tool never changes filesystem permissions.",
        "choose_folder", 1,
    ),
    "server_script": (
        "MCP 서버 소스가 누락됐습니다. 신뢰할 수 있는 ZIP을 검증한 후 새 폴더에 압축을 해제하세요.",
        "MCP server source files are missing. Verify a trusted ZIP and extract to a new folder.",
        "upgrade", 1,
    ),
    "python_environment": (
        "명시적 동의 후 install 명령으로 전용 환경을 만드세요. pip 패키지 설치에는 인터넷이 필요할 수 있습니다.",
        "After explicit approval, run install to create an isolated environment. pip may require internet access.",
        "install_dependencies", 2,
    ),
    "mcp_dependencies": (
        "전용 환경의 패키지 설치가 불완전합니다. 원인을 확인하고 install 명령으로 재설치하세요. 기존 사용자 문서는 변경하지 않습니다.",
        "Isolated dependencies are incomplete. Inspect the issue, then explicitly rerun install. User documents are unchanged.",
        "install_dependencies", 2,
    ),
}

COMMANDS = {
    "install_dependencies": "python scripts/setup_mcp.py install --allowed-dir YOUR_FOLDER",
    "probe": "python scripts/setup_mcp.py probe --allowed-dir YOUR_FOLDER",
    "client_config": "python scripts/setup_mcp.py config --client CLIENT --allowed-dir YOUR_FOLDER",
    "recheck": "python scripts/setup_mcp.py guide --allowed-dir YOUR_FOLDER",
    # Intentionally no executable suggestion for corrupt/untrusted sources:
    # even a local setup_mcp.py could have been modified with the package.
}


def _localized(pair: tuple[str, str], language: str) -> str:
    return pair[0 if language == "ko" else 1]


def guide(
    doctor: dict[str, Any],
    *,
    language: str = "ko",
    client: str = "codex",
    probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map a doctor/probe snapshot into one safe next action.

    Designed for native CLI and third-party terminals. No ANSI colors,
    interactive prompts, system-specific shell commands or absolute paths.
    """
    if language not in {"ko", "en"}:
        raise ValueError("Unsupported language")
    if client not in {"codex", "cursor", "claude-desktop"}:
        raise ValueError("Unsupported client")
    checks = doctor.get("checks")
    if type(checks) is not list:
        raise ValueError("Doctor checks are required")
    bad = {
        c["id"] for c in checks
        if type(c) is dict and c.get("passed") is False and c.get("id") in LABELS
    }
    manifest_unverified = any(
        type(c) is dict and c.get("id") == "source_manifest"
        and c.get("verified") is False and c.get("passed") is True
        for c in checks
    )
    common = {
        "schema": 1,
        "client": client,
        "language": language,
        "failed_checks": [
            {"id": code, "label": _localized(LABELS[code], language)}
            for code in ISSUE_PRIORITY if code in bad
        ],
        "packaged_manifest_verified": not manifest_unverified
            and any(type(c) is dict and c.get("id") == "source_manifest"
                    and c.get("verified") is True and c.get("passed") is True
                    for c in checks),
        "network_used": False,
        "files_created": 0,
        "original_documents_read": False,
        "client_config_modified": False,
        "automatic_repair": False,
        "automatic_permission_change": False,
        "mcp_host_registration_verified": False,
        "institutional_submission_verified": False,
    }
    if bad:
        code = next(x for x in ISSUE_PRIORITY if x in bad)
        ko, en, action, stage = ACTIONS[code]
        return {
            **common, "status": "needs_setup", "stage": stage, "total_stages": 4,
            "next_action": action, "reason_code": code,
            "instruction": ko if language == "ko" else en,
            "suggested_command": COMMANDS.get(action),
            "command_executed": False,
            "next_steps": [_localized((
                "안내를 검토한 뒤 사용자가 별도로 명령을 실행해야 합니다.",
                "Review the instructions, then run any repair command separately."
            ), language)],
        }
    if doctor.get("status") != "pass":
        return {
            **common, "status": "needs_attention", "stage": 1,
            "total_stages": 4, "next_action": "review_doctor",
            "reason_code": "unrecognized_diagnostic_failure",
            "instruction": _localized((
                "진단 정보가 완전하지 않습니다. doctor 결과를 로컬에서 직접 확인하세요.",
                "The diagnostic result is incomplete. Review doctor locally."
            ), language),
            "suggested_command": None,
            "command_executed": False, "next_steps": [],
        }
    if probe is None:
        return {
            **common, "status": "ready_for_probe", "stage": 3,
            "total_stages": 4, "next_action": "probe",
            "reason_code": None,
            "instruction": _localized((
                "설치 환경 검사를 통과했습니다. 로컬 MCP 연결 시험을 명시적으로 실행하세요.",
                "Local environment checks passed. Explicitly test the MCP stdio connection."
            ), language),
            "suggested_command": COMMANDS["probe"],
            "command_executed": False, "next_steps": [],
        }
    if probe.get("status") != "pass" or probe.get("tool_count") != 20:
        return {
            **common, "status": "needs_attention", "stage": 3,
            "total_stages": 4, "next_action": "review_connection",
            "reason_code": "mcp_probe_failed" if probe.get("status") != "pass"
                           else "unexpected_tool_count",
            "instruction": _localized((
                "MCP 연결 확인에 실패했습니다. 수동으로 probe를 재실행하고 필요하면 의존성을 점검하세요.",
                "MCP connectivity did not pass. Rerun probe manually and inspect dependencies."
            ), language),
            "suggested_command": COMMANDS["probe"],
            "command_executed": False, "next_steps": [],
        }
    return {
        **common, "status": "ready_for_client_config", "stage": 4,
        "total_stages": 4, "next_action": "client_config",
        "reason_code": None,
        "instruction": _localized((
            "20개 MCP 도구 연결을 확인했습니다. 설정 문구를 검토하고 선택한 클라이언트에 직접 등록하세요. 앱이 실제로 등록했는지는 별도 확인이 필요합니다.",
            "All 20 MCP tools responded. Review the config snippet and manually register it with your client. Verify host registration separately."
        ), language),
        "suggested_command": COMMANDS["client_config"].replace("CLIENT", client),
        "command_executed": False, "next_steps": [],
    }


def render_text(report: dict[str, Any]) -> str:
    """Plain, numbered and color-free terminal output suitable for screen readers."""
    korean = report["language"] == "ko"
    lines = [
        ("제출OK 설치 안내" if korean else "JeChulOK Setup Guide"),
        (f"단계 {report['stage']}/{report['total_stages']}" if korean
         else f"Step {report['stage']} of {report['total_stages']}"),
        ("상태: " if korean else "Status: ") + report["status"],
        ("다음 작업: " if korean else "Next action: ") + report["next_action"],
        report["instruction"],
    ]
    if report["failed_checks"]:
        lines.append("문제가 발견된 검사:" if korean else "Failed checks:")
        for i, item in enumerate(report["failed_checks"], 1):
            lines.append(f"{i}. {item['label']} ({item['id']})")
    if report["suggested_command"]:
        lines.append("참고 명령(자동 실행 안 함):" if korean else "Suggested command (NOT executed):")
        lines.append(report["suggested_command"])
    if not report["packaged_manifest_verified"]:
        lines.append(
            "참고: 패키지 무결성 확인이 수행되지 않았거나 통과하지 않았습니다."
            if korean else
            "Note: Packaged manifest integrity was not verified."
        )
    lines.append(
        "파일 생성·설정 변경·문서 업로드 없음"
        if korean else "No file writes, config changes or document uploads"
    )
    return "\n".join(lines) + "\n"

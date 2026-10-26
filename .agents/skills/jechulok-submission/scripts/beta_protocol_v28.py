#!/usr/bin/env python3
"""Read-only beta-study preparation: fixed tasks and self-attested preflight.

No participant recruitment, tracking, identifiable records, consent capture,
network traffic, file conversion or uploads. A completed checklist is not
evidence that real participants consented or any study was conducted.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

SCHEMA = "jechulok-beta-preflight-v28"
TASK_SET = "v28_synthetic_five_tasks"
QUESTIONNAIRE = "v25_stage_issue_impact"
MAX_MANIFEST_BYTES = 2048
RECRUITMENT = ("invited_volunteers", "open_volunteers", "internal_staff")
MODERATION = ("moderated", "self_guided")
CHECKS = (
    "consent_notice_presented", "voluntary_and_withdrawable",
    "synthetic_files_only", "identifiers_excluded", "feedback_optional",
)
KEYS = {"schema", "cohort", "task_set", "questionnaire", "recruitment", "moderation", *CHECKS}

TASKS_KO = (
    ("installation", "설치 안내 확인", "신뢰할 수 있는 로컬 스킬의 안내를 읽고 MCP 연결 방법을 설명해 주세요."),
    ("notice", "합성 공고 해석", "연습용 조건 'JPG 300×400px, 500KB 이하'에서 확인할 규격을 말해 주세요."),
    ("files", "원본 선택", "연습용 파일 후보 중 어떤 원본을 선택해야 하는지 직접 결정해 주세요."),
    ("plan", "실행 승인", "준비 계획의 원본·출력·변경 사항을 검토하고 승인할지 판단해 주세요."),
    ("check", "결과 확인", "연습용 결과의 픽셀·용량·형식을 어떻게 재검증할지 설명해 주세요."),
)
TASKS_EN = (
    ("installation", "Review setup", "Read the trusted local setup guide and explain how to connect the MCP client."),
    ("notice", "Interpret sample notice", "Identify checks in the invented requirement 'JPG 300x400 px, at most 500 KB'."),
    ("files", "Choose source", "Manually decide which synthetic candidate file should be selected."),
    ("plan", "Decide approval", "Review the exact input, output, and changes; decide whether to approve execution."),
    ("check", "Verify output", "Explain how to verify the synthetic result's dimensions, bytes, and file format."),
)


def _common() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "read_only": True, "network_used": False,
        "telemetry_enabled": False, "user_files_modified": False,
        "personal_documents_read": False, "participants_contacted": False,
        "consent_independently_verified": False, "real_study_performed": False,
        "shareable_without_review": False,
    }


def protocol(language: str = "ko") -> dict[str, Any]:
    if language not in ("ko", "en"):
        raise ValueError("Unsupported language")
    korean = language == "ko"
    tasks = TASKS_KO if korean else TASKS_EN
    return {
        **_common(), "status": "protocol_preview_only", "language": language,
        "task_set": TASK_SET, "questionnaire": QUESTIONNAIRE,
        "participant_notice": (
            "참여는 자발적이며 언제든 중단할 수 있습니다. 연습용 파일만 사용하며 실명·연락처·공고 원문을 기록하지 않습니다. "
            "피드백도 선택 사항입니다. 담당자에게 별도로 동의·철회 방법을 확인하세요."
            if korean else
            "Participation is voluntary and can stop at any time. Use synthetic files only. "
            "Do not record names, contact details or original notices. Feedback is optional. "
            "Confirm consent and withdrawal procedures separately with the organizer."
        ),
        "tasks": [
            {"id": f"task_{i}", "stage": stage, "title": title, "prompt": prompt}
            for i, (stage, title, prompt) in enumerate(tasks, 1)
        ],
        "feedback_categories": {
            "stage": "v25 fixed stages", "issue": "v25 fixed issues",
            "impact": "v25 fixed impact levels",
        },
        "instructions": (
            "The organizer must recruit and document informed consent separately. "
            "Use only synthetic examples. Do not automatically run tools or capture participant data."
        ),
    }


def template(cohort: str = "baseline") -> dict[str, Any]:
    if cohort not in ("baseline", "current"):
        raise ValueError("Unsupported cohort")
    return {
        "schema": SCHEMA, "cohort": cohort, "task_set": TASK_SET,
        "questionnaire": QUESTIONNAIRE, "recruitment": "invited_volunteers",
        "moderation": "moderated", **{key: False for key in CHECKS},
    }


def check_manifest(value: Any) -> dict[str, Any]:
    if type(value) is not dict or set(value) != KEYS:
        raise ValueError("Invalid preflight fields")
    if (value["schema"] != SCHEMA or value["cohort"] not in ("baseline", "current")
            or value["task_set"] != TASK_SET or value["questionnaire"] != QUESTIONNAIRE
            or value["recruitment"] not in RECRUITMENT or value["moderation"] not in MODERATION
            or any(type(value[key]) is not bool for key in CHECKS)):
        raise ValueError("Invalid preflight value")
    return value


def read_manifest(path: Path) -> dict[str, Any]:
    target = path.expanduser().absolute()
    try:
        if target.suffix.lower() != ".json" or target.is_symlink() or target.resolve(strict=True) != target:
            raise ValueError("Invalid local manifest")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(target, flags)
        with os.fdopen(descriptor, "rb") as handle:
            meta = os.fstat(handle.fileno())
            if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_MANIFEST_BYTES:
                raise ValueError("Invalid local manifest")
            content = handle.read(MAX_MANIFEST_BYTES + 1)
        if len(content) > MAX_MANIFEST_BYTES:
            raise ValueError("Invalid local manifest")
        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate preflight key")
                result[key] = value
            return result

        return check_manifest(json.loads(content.decode("utf-8"), object_pairs_hook=reject_duplicate_keys))
    except (OSError, ValueError, UnicodeError, TypeError, RuntimeError):
        raise ValueError("Invalid local manifest") from None


def audit(path: Path) -> dict[str, Any]:
    value = read_manifest(path)
    missing = [name for name in CHECKS if not value[name]]
    return {
        **_common(), "status": (
            "self_attested_checklist_complete" if not missing else "hold_for_manual_review"
        ),
        "cohort": value["cohort"], "incomplete_checklist_items": missing,
        "operator_attestation_only": True,
        "note": "No actual consent, participation, or study execution was verified.",
    }


def compare_preflight(baseline: Path, current: Path) -> dict[str, Any]:
    old = baseline.expanduser().absolute()
    new = current.expanduser().absolute()
    if old.resolve(strict=True) == new.resolve(strict=True):
        raise ValueError("Two different manifests required")
    a, b = read_manifest(old), read_manifest(new)
    same_settings = all(a[key] == b[key] for key in (
        "task_set", "questionnaire", "recruitment", "moderation",
    ))
    complete = all(a[key] and b[key] for key in CHECKS)
    roles_correct = a["cohort"] == "baseline" and b["cohort"] == "current"
    return {
        **_common(), "status": (
            "self_attested_protocols_match" if same_settings and complete and roles_correct
            else "hold_for_manual_review"
        ),
        "task_and_recruitment_settings_match": same_settings,
        "self_attested_checklists_complete": complete,
        "roles_correct": roles_correct,
        "participants_and_collection_comparable_verified": False,
        "product_improvement_measured": False,
        "note": "Matching manifest settings are unverified operator statements, not comparable participant samples.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("protocol")
    p.add_argument("--language", choices=("ko", "en"), default="ko")
    t = commands.add_parser("template")
    t.add_argument("--cohort", choices=("baseline", "current"), default="baseline")
    a = commands.add_parser("audit")
    a.add_argument("--manifest", required=True, type=Path)
    c = commands.add_parser("compare-preflight")
    c.add_argument("--baseline-manifest", required=True, type=Path)
    c.add_argument("--current-manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "protocol":
            result = protocol(args.language)
        elif args.command == "template":
            result = template(args.cohort)
        elif args.command == "audit":
            result = audit(args.manifest)
        else:
            result = compare_preflight(args.baseline_manifest, args.current_manifest)
    except (ValueError, OSError, TypeError, RuntimeError):
        print(json.dumps({"status": "error", "reason_code": "invalid_preflight_input",
                          "network_used": False, "documents_uploaded": False}))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

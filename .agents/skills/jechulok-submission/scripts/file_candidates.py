"""Read-only, conservative local filename suggestions for JeChulOK v0.5.

No OCR, semantic claims, recursion, content uploads, writes, or automatic assignment.
Only immediate children of an explicitly authorized directory are inspected.
"""
from __future__ import annotations

import os
import re
import stat
import unicodedata
from pathlib import Path
from typing import Any, Callable

from notice_batch import analyze_notice

MAX_DIRECTORY_ENTRIES = 250
MAX_CANDIDATES_PER_ITEM = 5

_ALIASES: dict[str, tuple[str, ...]] = {
    "photo": ("증명사진", "반명함", "사진", "photo", "portrait", "profile"),
    "resume": ("이력서", "입사지원서", "resume", "curriculumvitae"),
    "cover_letter": ("자기소개서", "자소서", "coverletter", "personalstatement"),
    "graduation": ("졸업증명서", "졸업예정", "graduation", "diploma"),
    "employment": ("재직증명서", "경력증명서", "employment", "career"),
    "transcript": ("성적증명서", "transcript", "grades"),
    "portfolio": ("포트폴리오", "portfolio"),
    "certificate": ("자격증", "certificate", "certification"),
}


def _normalized(value: str) -> str:
    return re.sub(r"[\s_.-]+", "", unicodedata.normalize("NFKC", value).casefold())


def _keyword_hit(filename: str, aliases: tuple[str, ...]) -> bool:
    normalized = _normalized(filename)
    for alias in aliases:
        needle = _normalized(alias)
        if len(needle) < 2:
            continue
        if needle.isascii() and len(needle) <= 3:
            # Short English words such as CV must not match unrelated filenames.
            if re.search(rf"(?<![a-z]){re.escape(needle)}(?![a-z])", filename.casefold()):
                return True
        elif needle in normalized:
            return True
    return False


def suggest_files(
    notice_text: str,
    directory_path: str,
    *,
    confine_directory: Callable[[str], Path],
) -> dict[str, Any]:
    """Return filename/type candidates; the caller MUST manually confirm assignments."""
    notice = analyze_notice(notice_text)
    directory = confine_directory(directory_path)

    files: list[dict[str, Any]] = []
    examined = 0
    truncated = False
    with os.scandir(directory) as listing:
        for entry in listing:
            if examined >= MAX_DIRECTORY_ENTRIES:
                truncated = True
                break
            examined += 1
            try:
                if entry.is_symlink():
                    continue
                info = entry.stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    continue
            except OSError:
                continue
            extension = Path(entry.name).suffix.casefold()
            if extension not in {".pdf", ".jpg", ".jpeg", ".png", ".webp"}:
                continue
            files.append({
                "input_path": str(directory / entry.name),
                "filename": entry.name,
                "extension": extension,
                "size_bytes": info.st_size,
            })
    files.sort(key=lambda item: (item["filename"].casefold(), item["filename"]))

    output: list[dict[str, Any]] = []
    for item in notice["items"]:
        fmt = item["parsed"]["rules"]["expected_format"]
        extensions = ({".jpg", ".jpeg", ".png", ".webp"} if fmt == "jpg"
                      else {".pdf"} if fmt == "pdf" else set())
        candidates: list[dict[str, Any]] = []
        for entry in files:
            if entry["extension"] not in extensions:
                continue
            filename_match = _keyword_hit(entry["filename"], _ALIASES.get(item["category"], ()))
            candidates.append({
                **entry,
                "match_type": "filename_keyword" if filename_match else "file_extension_only",
                "priority": "name_hint" if filename_match else "unknown",
                "requires_manual_review": True,
            })
        candidates.sort(key=lambda c: (c["match_type"] != "filename_keyword",
                                      c["filename"].casefold(), c["filename"]))
        output.append({
            "item_id": item["item_id"],
            "label": item["label"],
            "expected_format": fmt,
            "candidates": candidates[:MAX_CANDIDATES_PER_ITEM],
            "total_compatible_files": len(candidates),
            "review_required": True,
        })

    result_status = ("needs_review" if notice["status"] != "parsed"
                     else "no_candidates" if any(not item["candidates"] for item in output)
                     else "suggestions_only")
    return {
        "status": result_status,
        "directory": str(directory),
        "items": output,
        "notice_status": notice["status"],
        "scanned_entries": examined,
        "truncated": truncated,
        "notes": [
            "파일 내용은 열지 않습니다. 확장자와 파일명 문자열만 비교한 후보이며 내용·적합성·정확도를 확인한 것이 아닙니다.",
            "최대 250개 디렉터리 항목만 비재귀 탐색합니다. truncated=true면 다른 후보가 누락될 수 있습니다.",
            "파일은 자동 배정되지 않습니다. 사용자가 item_id와 input_path를 확인한 후 prepare_submission_batch에 직접 전달해야 합니다.",
            "공고 조건이 모호하거나 공통 조건이 미배정이면 후보가 있더라도 파일 처리는 중단해야 합니다.",
        ],
    }

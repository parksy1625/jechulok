#!/usr/bin/env python3
"""JeChulOK local MCP server (v0.5). Only stdio; never listens on a network port.

The file-processing logic is shared with the CLI in jechulok.py. Inputs and
outputs are confined to JECHULOK_ALLOWED_DIRS (default: current working directory).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer

import jechulok as core
from submission_rules import parse_requirements as extract_submission_rules

mcp = MCPServer(
    "JeChulOK Submission",
    instructions=(
        "Local-only submission-file tooling. Call check_file before modifying. "
        "Use explicit institution requirements, do not invent them. "
        "Never overwrite inputs. cover/crop requires user approval. "
        "Treat 'unverified' and 'info' as NOT compliant. "
        "Call verify_submission on every generated output. "
        "Do not auto-edit needs_review requirements. "
        "Paths must be under JECHULOK_ALLOWED_DIRS. No file contents are uploaded."
    ),
)

Format = Literal["any", "jpg", "png", "webp", "gif", "pdf"]
Mode = Literal["contain", "cover"]


def _roots() -> list[Path]:
    raw = os.environ.get("JECHULOK_ALLOWED_DIRS")
    values = raw.split(os.pathsep) if raw else [str(Path.cwd())]
    roots: list[Path] = []
    for value in values:
        if not value.strip():
            continue
        root = Path(value).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Configured allowed root must be a directory")
        roots.append(root)
    if not roots:
        raise ValueError("JECHULOK_ALLOWED_DIRS must contain at least one directory")
    return roots


def _confined(path_string: str, *, for_output: bool = False) -> Path:
    if not path_string or not str(path_string).strip():
        raise ValueError("A nonempty local file path is required")
    candidate = Path(path_string).expanduser().absolute()
    # Deny symbolic links anywhere between an allowed root and the target.
    # Resolving first disallows aliases that point outside a permitted root.
    resolved = candidate.resolve(strict=False)
    roots = _roots()
    matched = None
    for root in roots:
        try:
            resolved.relative_to(root)
            matched = root
            break
        except ValueError:
            continue
    if matched is None:
        raise ValueError("File path is outside JECHULOK_ALLOWED_DIRS")
    current = matched
    for part in resolved.relative_to(matched).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symbolic-link paths are not allowed")
    if candidate.is_symlink():
        raise ValueError("Symbolic-link file paths are not allowed")
    if for_output:
        if resolved.exists() or not resolved.parent.is_dir():
            raise ValueError("Output must be a new file in an existing allowed directory")
    else:
        if not resolved.is_file():
            raise ValueError("Input must be an existing regular file")
    return resolved



def _confined_directory(path_string: str) -> Path:
    """Authorize a real directory, disallowing symlinks and traversal aliases."""
    if not isinstance(path_string, str) or not path_string.strip():
        raise ValueError("A nonempty local directory path is required")
    candidate = Path(path_string).expanduser().absolute()
    resolved = candidate.resolve(strict=False)
    # Reject symlinks and noncanonical /.. aliases before scanning any names.
    if candidate != resolved:
        raise ValueError("Directory aliases, traversal and symbolic links are not allowed")
    if not any(resolved == root or root in resolved.parents for root in _roots()):
        raise ValueError("Directory is outside JECHULOK_ALLOWED_DIRS")
    if not resolved.is_dir():
        raise ValueError("Directory does not exist or is not a directory")
    return resolved


def _positive(name: str, value: int | None) -> int | None:
    if value is not None and (type(value) is not int or value <= 0):
        raise ValueError(f"{name} must be a positive integer")
    return value


def _result(call: Any) -> dict[str, Any]:
    try:
        return call()
    except (ValueError, OSError, core.Image.DecompressionBombError, core.UnidentifiedImageError) as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": f"File processing failed: {type(exc).__name__}: {str(exc)[:180]}"}


def _inspect(
    input_path: str,
    expected_format: Format = "any",
    max_kb: int | None = None,
    width: int | None = None,
    height: int | None = None,
    max_pages: int | None = None,
    *,
    require_rules: bool = False,
) -> dict[str, Any]:
    if expected_format not in ("any", "jpg", "png", "webp", "gif", "pdf"):
        raise ValueError("Unsupported expected_format")
    for key, value in (("max_kb", max_kb), ("width", width), ("height", height), ("max_pages", max_pages)):
        _positive(key, value)
    if require_rules and expected_format == "any" and all(x is None for x in (max_kb, width, height, max_pages)):
        raise ValueError("Verification requires at least one explicit rule")
    path = _confined(input_path)
    return core.evaluation(
        core.info_for(core.safe_file(str(path))),
        expected_format=expected_format,
        max_kb=max_kb,
        width=width,
        height=height,
        max_pages=max_pages,
    )


@mcp.tool()
def check_file(
    input_path: str,
    expected_format: Format = "any",
    max_kb: int | None = None,
    width: int | None = None,
    height: int | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """Inspect an existing local image/PDF: signature, size, dimensions, pages and explicit rules. No files are modified. Status 'info' or 'unverified' is not acceptance."""
    return _result(lambda: _inspect(input_path, expected_format, max_kb, width, height, max_pages))


@mcp.tool()
def prepare_image(
    input_path: str,
    output_path: str,
    width: int | None = None,
    height: int | None = None,
    max_kb: int | None = None,
    mode: Mode = "contain",
    crop_approved: bool = False,
) -> dict[str, Any]:
    """Create a new JPG from JPG/PNG/WebP and verify its requested pixels/size. Defaults to white padding. Center cropping needs crop_approved=true and explicit user permission. Never overwrite."""
    def perform() -> dict[str, Any]:
        if mode not in ("contain", "cover"):
            raise ValueError("mode must be contain or cover")
        if mode == "cover" and crop_approved is not True:
            raise ValueError("Center cropping requires explicit user approval (crop_approved=true)")
        for key, value in (("width", width), ("height", height), ("max_kb", max_kb)):
            _positive(key, value)
        src = _confined(input_path)
        dest = _confined(output_path, for_output=True)
        if src == dest:
            raise ValueError("Original files may not be overwritten")
        args = argparse.Namespace(output=str(dest), width=width, height=height, max_kb=max_kb, mode=mode)
        return core.prepare_image(core.safe_file(str(src)), args)
    return _result(perform)


@mcp.tool()
def extract_pdf_pages(
    input_path: str,
    output_path: str,
    pages: str,
    max_kb: int | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """Extract 1-based page ranges such as '2-4,7' into a new local PDF, in requested order, and recheck count. May remove PDF signatures, forms or bookmarks; no overwrite."""
    def perform() -> dict[str, Any]:
        _positive("max_kb", max_kb)
        _positive("max_pages", max_pages)
        src = _confined(input_path)
        dest = _confined(output_path, for_output=True)
        if src == dest:
            raise ValueError("Original files may not be overwritten")
        args = argparse.Namespace(output=str(dest), pages=pages, max_kb=max_kb, max_pages=max_pages)
        return core.prepare_pdf(core.safe_file(str(src)), args)
    return _result(perform)


@mcp.tool()
def verify_submission(
    input_path: str,
    expected_format: Format = "any",
    max_kb: int | None = None,
    width: int | None = None,
    height: int | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """Independently re-open a final local file and validate at least one explicit technical requirement. A 'pass' does not guarantee institutional acceptance."""
    return _result(lambda: _inspect(input_path, expected_format, max_kb, width, height, max_pages, require_rules=True))




@mcp.tool()
def parse_submission_rules(requirements_text: str) -> dict[str, Any]:
    """Parse Korean/English file submission requirements conservatively. Unknown conditions require review; never edits files."""
    return _result(lambda: extract_submission_rules(requirements_text))


@mcp.tool()
def prepare_from_requirements(
    input_path: str,
    output_path: str,
    requirements_text: str,
    pages_to_extract: str | None = None,
    mode: Mode = "contain",
    crop_approved: bool = False,
) -> dict[str, Any]:
    """Prepare a local JPG or explicitly selected PDF pages from unambiguous text rules. Never overwrite; verify output; do not infer page selection."""
    def perform() -> dict[str, Any]:
        parsed = extract_submission_rules(requirements_text)
        if parsed["status"] != "parsed":
            return {"status": "needs_review", "message": "제출 조건이 모호하거나 자동 검증할 수 없습니다.", "parsed": parsed}
        rules = parsed["rules"]
        fmt = rules["expected_format"]
        if fmt not in {"jpg", "pdf"}:
            return {"status": "needs_review", "message": "단일 JPG 또는 PDF 형식 조건이 필요합니다.", "parsed": parsed}
        if fmt == "pdf" and not pages_to_extract:
            return {"status": "needs_review", "message": "삭제할 페이지는 임의로 선택하지 않습니다. pages_to_extract를 지정하세요.", "parsed": parsed}
        if fmt == "jpg" and pages_to_extract:
            return {"status": "needs_review", "message": "사진에 PDF 페이지 추출 범위를 지정할 수 없습니다.", "parsed": parsed}
        if mode not in ("contain", "cover"):
            raise ValueError("mode must be contain or cover")
        if mode == "cover" and crop_approved is not True:
            raise ValueError("Center crop needs explicit user approval")
        source = _confined(input_path)
        dest = _confined(output_path, for_output=True)
        if source == dest:
            raise ValueError("Original files may not be overwritten")
        meta = core.info_for(core.safe_file(str(source)))
        if core.evaluation(meta)["status"] == "fail":
            return {"status": "error", "message": "원본 확장자와 실제 파일 형식이 맞지 않습니다."}
        if fmt == "jpg":
            if meta["format"] not in {"jpg", "png", "webp"}:
                return {"status": "needs_review", "message": "JPG, PNG, WebP 이미지만 JPG로 준비할 수 있습니다.", "parsed": parsed}
            args = argparse.Namespace(output=str(dest), width=rules["width"], height=rules["height"],
                                      max_kb=rules["max_kb"], mode=mode)
            prepared = core.prepare_image(core.safe_file(str(source)), args)
        else:
            args = argparse.Namespace(output=str(dest), pages=pages_to_extract,
                                      max_kb=rules["max_kb"], max_pages=rules["max_pages"])
            prepared = core.prepare_pdf(core.safe_file(str(source)), args)
        verified = _inspect(str(dest), expected_format=fmt, max_kb=rules["max_kb"],
                            width=rules["width"], height=rules["height"],
                            max_pages=rules["max_pages"], require_rules=True)
        if verified["status"] != "pass":
            dest.unlink(missing_ok=True)
            return {"status": "error", "message": "결과 파일 재검증 실패. 생성한 파일을 삭제했습니다.",
                    "verification": verified, "parsed": parsed}
        return {"status": "pass", "output": str(dest), "preparation": prepared,
                "verification": verified, "parsed": parsed,
                "limitations": "기술 조건만 검증합니다. 사진 구도·내용·기관 접수는 수동 확인이 필요합니다."}
    return _result(perform)

from notice_batch import analyze_notice, prepare_batch

@mcp.tool()
def analyze_submission_notice(notice_text: str) -> dict[str, Any]:
    """Parse a long Korean notice into explicitly named per-file requirements. Ambiguous/shared rules block automation. Never modifies files."""
    return _result(lambda: analyze_notice(notice_text))


@mcp.tool()
def prepare_submission_batch(
    notice_text: str,
    assignments: list[dict[str, Any]],
    execute: bool = False,
    confirm_execution: bool = False,
) -> dict[str, Any]:
    """Preflight all explicit item_id/file mappings. Dry run by default; actual writes need execute=true and confirm_execution=true. Never guess page ranges or overwrite files."""
    return _result(lambda: prepare_batch(notice_text, assignments, execute=execute,
                                         confirm_execution=confirm_execution, confine=_confined))


from file_candidates import suggest_files

@mcp.tool()
def suggest_submission_files(
    notice_text: str,
    directory_path: str,
) -> dict[str, Any]:
    """Suggest local filename/extension candidates for named submission items. READ ONLY, no automatic assignment; inspect and confirm each mapping manually."""
    return _result(lambda: suggest_files(notice_text, directory_path,
                                         confine_directory=_confined_directory))


if __name__ == "__main__":
    # Local stdio only. Do not expose arbitrary user files via an unauthenticated HTTP endpoint.
    mcp.run(transport="stdio")

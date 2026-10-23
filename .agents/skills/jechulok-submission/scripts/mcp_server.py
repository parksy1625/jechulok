#!/usr/bin/env python3
"""JeChulOK local MCP server (v0.2). Only stdio; never listens on a network port.

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

mcp = MCPServer(
    "JeChulOK Submission",
    instructions=(
        "Local-only submission-file tooling. Call check_file before modifying. "
        "Use explicit institution requirements, do not invent them. "
        "Never overwrite inputs. cover/crop requires user approval. "
        "Treat 'unverified' and 'info' as NOT compliant. "
        "Call verify_submission on every generated output. "
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


if __name__ == "__main__":
    # Local stdio only. Do not expose arbitrary user files via an unauthenticated HTTP endpoint.
    mcp.run(transport="stdio")

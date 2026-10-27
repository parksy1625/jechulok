#!/usr/bin/env python3
"""v3.3 bound preflight and read-only postflight verification.

Neither command converts, writes, uploads, or approves a user document.
The operator separately invokes the existing converter after approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any

from PIL import Image
from pypdf import PdfReader

from jechulok import MAX_FILE_BYTES, MAX_OUTPUT_PIXELS, evaluation, info_for, output_path, safe_file
from preview_prepare_v32 import _oriented_size, preview_file

SCHEMA = "jechulok-bound-preview-v33"
MAX_PLAN_BYTES = 64 * 1024


def _fingerprint(path: Path, salt: bytes) -> str:
    digest = hashlib.sha256(b"jechulok-source-v33\0" + salt)
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _path_binding(path: Path, salt: bytes) -> str:
    canonical = os.path.normcase(os.path.abspath(os.fspath(path)))
    return hashlib.sha256(b"jechulok-target-v33\0" + salt + os.fsencode(canonical)).hexdigest()


def _signature(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _seal(report: dict[str, Any], salt: bytes) -> str:
    # Accidental manifest changes are detected, not adversarial alterations.
    data = json.dumps(report, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(b"jechulok-plan-v33\0" + salt + data).hexdigest()


def bound_preview(*, input_path: str, rules_text: str, output: str | None = None,
                  pages: str | None = None, mode: str = "contain") -> dict[str, Any]:
    """Produce a path-free preview bound to source *bytes* and one target path."""
    report = preview_file(input_path=input_path, rules_text=rules_text,
                          output=output, pages=pages, mode=mode)
    if report["status"] != "ready_for_review":
        return report
    try:
        source = safe_file(input_path)
        kind = report["planned_output"]["format"]
        target = output_path(source, output, kind)
        before = _signature(source)
        if before[2] > MAX_FILE_BYTES or before[2] != report["input"]["size_bytes"]:
            raise ValueError("changed")
        salt = secrets.token_bytes(16)
        source_digest = _fingerprint(source, salt)
        if _signature(source) != before or target.exists() or target.is_symlink():
            raise ValueError("changed")
    except (OSError, ValueError):
        report.update(status="blocked", action="manual_review",
                      reason_code="source_or_target_changed_during_preview",
                      planned_output=None, risks=[])
        return report
    report["schema"] = SCHEMA
    report["operation_mode"] = mode
    report["binding"] = {
        "algorithm": "sha256-salted-v1", "salt_hex": salt.hex(),
        "source_sha256": source_digest,
        "target_sha256": _path_binding(target, salt),
    }
    report["limitations"].append(
        "The local plan checksum is not a signature; do not use an untrusted plan as authorization.")
    report["plan_sha256"] = _seal(report, salt)
    return report


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for key, value in pairs:
        if key in record:
            raise ValueError("duplicate json key")
        record[key] = value
    return record


def _read_plan(path: str) -> dict[str, Any]:
    plan_path = safe_file(path)
    if plan_path.stat().st_size > MAX_PLAN_BYTES:
        raise ValueError("plan too large")
    with plan_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle, object_pairs_hook=_reject_duplicates)
    if type(data) is not dict or data.get("schema") != SCHEMA:
        raise ValueError("not bound preview")
    if (data.get("status") != "ready_for_review" or data.get("files_written") != 0
            or data.get("preview_only") is not True or data.get("execution_permitted") is not False
            or data.get("human_approval_recorded") is not False):
        raise ValueError("invalid preview state")
    binding = data.get("binding")
    if type(binding) is not dict or set(binding) != {"algorithm", "salt_hex", "source_sha256", "target_sha256"}:
        raise ValueError("invalid binding")
    if binding["algorithm"] != "sha256-salted-v1":
        raise ValueError("unknown binding")
    if (any(type(binding[key]) is not str for key in ("salt_hex", "source_sha256", "target_sha256"))
            or len(binding["salt_hex"]) != 32 or len(binding["source_sha256"]) != 64
            or len(binding["target_sha256"]) != 64):
        raise ValueError("invalid digest")
    try:
        salt = bytes.fromhex(binding["salt_hex"])
        bytes.fromhex(binding["source_sha256"])
        bytes.fromhex(binding["target_sha256"])
    except ValueError as exc:
        raise ValueError("invalid hex") from exc
    given = data.pop("plan_sha256", None)
    if type(given) is not str or not secrets.compare_digest(given, _seal(data, salt)):
        raise ValueError("modified plan")
    data["plan_sha256"] = given
    if (type(data.get("input")) is not dict or type(data.get("requested")) is not dict
            or type(data.get("planned_output")) is not dict
            or data.get("operation_mode") not in {"contain", "cover"}):
        raise ValueError("missing plan fields")
    if (any(key not in data["input"] for key in ("format", "size_bytes", "width", "height", "pages"))
            or type(data["input"]["size_bytes"]) is not int
            or data["input"]["size_bytes"] < 0):
        raise ValueError("invalid source metadata")
    kind = data["planned_output"].get("format")
    if kind not in {"jpg", "pdf"} or data["requested"].get("expected_format") != kind:
        raise ValueError("invalid plan kind")
    return data


def _base_result() -> dict[str, Any]:
    return {
        "schema": "jechulok-postflight-v33", "status": "blocked", "reason_code": None,
        "checks": [], "verified": False, "technical_consistency_only": True,
        "files_written": 0, "network_used": False, "automatic_upload": False,
        "execution_permitted": False, "institutional_acceptance_verified": False,
        "limitations": [
            "This does not confirm document meaning, photo identity, PDF page content or institutional acceptance.",
            "Preview checksum detects accidental changes, not a maliciously forged manifest.",
            "The output may still need human visual, signature, accessibility and content review.",
        ],
    }


def _block(result: dict[str, Any], reason: str) -> dict[str, Any]:
    result.update(status="blocked", reason_code=reason, verified=False)
    return result


def _check(result: dict[str, Any], code: str, ok: bool) -> None:
    result["checks"].append({"code": code, "status": "pass" if ok else "fail"})


def _padding_samples_white(path: Path, *, source_size: tuple[int, int],
                           expected_size: tuple[int, int]) -> bool | None:
    """Check only safely interior points of predicted white padding; never judge content."""
    sw, sh = source_size
    tw, th = expected_size
    if tw * th > MAX_OUTPUT_PIXELS:
        return False
    if sw * th > sh * tw:
        fitted_w, fitted_h = tw, round(sh * tw / sw)
    else:
        fitted_w, fitted_h = round(sw * th / sh), th
    left = (tw - fitted_w) // 2
    top = (th - fitted_h) // 2
    right = tw - fitted_w - left
    bottom = th - fitted_h - top
    if max(left, right, top, bottom) == 0:
        return True
    candidates: list[tuple[int, int]] = []
    # Margin of 6+ pixels keeps samples away from JPEG ringing at the image edge.
    for edge, xlo, xhi, ylo, yhi in (
        (left, 0, left, 0, th), (right, tw - right, tw, 0, th),
        (top, 0, tw, 0, top), (bottom, 0, tw, th - bottom, th),
    ):
        if edge < 6:
            continue
        center_x, center_y = (xlo + xhi) // 2, (ylo + yhi) // 2
        for delta in (-1, 0, 1):
            x = max(xlo, min(xhi - 1, center_x + delta * (xhi - xlo) // 4))
            y = max(ylo, min(yhi - 1, center_y + delta * (yhi - ylo) // 4))
            candidates.append((x, y))
    if not candidates:
        return None
    try:
        with Image.open(path) as image:
            image.load()
            rgb = image.convert("RGB")
            return all(min(rgb.getpixel(point)) >= 235 for point in candidates)
    except Exception:
        return False


def _pdf_page_geometries(path: Path, pages: list[int] | None) -> list[tuple[float, ...]]:
    reader = PdfReader(str(path), strict=False)
    if reader.is_encrypted:
        raise ValueError("encrypted pdf")
    sequence = range(len(reader.pages)) if pages is None else pages
    result = []
    for index in sequence:
        page = reader.pages[index]
        box = page.mediabox
        crop = page.cropbox
        result.append(tuple(round(float(value), 3) for value in (
            *box, *crop, page.get("/Rotate", 0)
        )))
    return result


def verify_conversion(*, preview_path: str, input_path: str, output_path_str: str) -> dict[str, Any]:
    """Fail closed on metadata, rule, plan-binding or target mismatches."""
    report = _base_result()
    try:
        plan = _read_plan(preview_path)
    except (ValueError, OSError, UnicodeError, TypeError, RecursionError, json.JSONDecodeError):
        return _block(report, "invalid_or_modified_preview")
    try:
        source = safe_file(input_path)
        if os.path.samefile(source, safe_file(preview_path)):
            return _block(report, "files_not_distinct")
        binding = plan["binding"]
        salt = bytes.fromhex(binding["salt_hex"])
        proposed_output = Path(output_path_str).expanduser().absolute()
        if _path_binding(proposed_output, salt) != binding["target_sha256"]:
            return _block(report, "output_path_not_in_preview")
        before = _signature(source)
        if before[2] > MAX_FILE_BYTES:
            return _block(report, "source_changed_since_preview")
        source_digest = _fingerprint(source, salt)
        if _signature(source) != before or not secrets.compare_digest(source_digest, binding["source_sha256"]):
            return _block(report, "source_changed_since_preview")
        source_meta = info_for(source)
        original = plan["input"]
        if any(source_meta.get(k) != original.get(k) for k in ("format", "size_bytes", "width", "height", "pages")):
            return _block(report, "source_metadata_changed")
        result_file = safe_file(output_path_str)
        if os.path.samefile(source, result_file):
            return _block(report, "files_not_distinct")
        output_meta = info_for(result_file)
    except (OSError, ValueError, TypeError):
        return _block(report, "file_missing_or_unreadable")
    except Exception:
        return _block(report, "inspection_failed")
    if source_meta["issues"] or output_meta["issues"]:
        return _block(report, "file_integrity_unverified")
    kind = plan["planned_output"]["format"]
    if output_meta["format"] != kind or output_meta["extension"] != kind:
        return _block(report, "output_format_mismatch")
    requested = plan["requested"]
    max_kb, max_pages = requested.get("max_kb"), requested.get("max_pages")
    if any(x is not None and (type(x) is not int or x < 1) for x in (max_kb, max_pages)):
        return _block(report, "invalid_plan_constraints")
    _check(report, "output_format", True)
    if max_kb is not None:
        _check(report, "output_size_limit", output_meta["size_bytes"] <= max_kb * 1024)
    expected = plan["planned_output"]
    if kind == "jpg":
        tw, th = expected.get("width"), expected.get("height")
        if (type(tw) is not int or type(th) is not int or tw <= 0 or th <= 0
                or tw * th > MAX_OUTPUT_PIXELS or plan["operation_mode"] not in {"contain", "cover"}):
            return _block(report, "invalid_planned_dimensions")
        if (original["format"] not in {"jpg", "png", "webp"}
                or type(original["width"]) is not int or type(original["height"]) is not int):
            return _block(report, "invalid_source_format")
        _check(report, "output_width", output_meta["width"] == tw)
        _check(report, "output_height", output_meta["height"] == th)
        if (output_meta["width"], output_meta["height"]) == (tw, th):
            try:
                with Image.open(result_file) as converted:
                    orientation = converted.getexif().get(274, 1)
                _check(report, "output_exif_orientation_cleared", orientation in (1, None))
                sw, sh, _ = _oriented_size(source, original["width"], original["height"])
                if plan["operation_mode"] == "contain":
                    white = _padding_samples_white(result_file,
                                                   source_size=(sw, sh), expected_size=(tw, th))
                    if white is None:
                        report["checks"].append({"code": "white_padding_interior", "status": "unverified"})
                    else:
                        _check(report, "white_padding_interior", white)
            except Exception:
                return _block(report, "padding_inspection_failed")
    else:
        selected = expected.get("selected_pages")
        if (type(original.get("pages")) is not int or type(selected) is not list or not selected
                or any(type(i) is not int or i < 1 or i > original["pages"] for i in selected)
                or len(set(selected)) != len(selected)):
            return _block(report, "invalid_page_selection")
        _check(report, "output_page_count", output_meta["pages"] == len(selected))
        if max_pages is not None:
            _check(report, "output_page_limit", output_meta["pages"] <= max_pages)
        if output_meta["pages"] == len(selected):
            try:
                before_geo = _pdf_page_geometries(source, [i - 1 for i in selected])
                after_geo = _pdf_page_geometries(result_file, None)
            except Exception:
                return _block(report, "pdf_geometry_inspection_failed")
            _check(report, "selected_page_geometries_and_order", before_geo == after_geo)
    if any(item["status"] == "fail" for item in report["checks"]):
        return _block(report, "postflight_mismatch")
    if any(item["status"] == "unverified" for item in report["checks"]):
        report.update(status="needs_review", reason_code="padding_too_narrow_to_verify")
        return report
    report.update(status="pass", reason_code=None, verified=True)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bound preview and read-only technical postflight")
    command = parser.add_subparsers(dest="command", required=True)
    pre = command.add_parser("preview", help="Print a source- and destination-bound JSON preview")
    pre.add_argument("--input", required=True)
    pre.add_argument("--rules", required=True)
    pre.add_argument("--output", help="Proposed new output path, never created")
    pre.add_argument("--pages", help="Selected PDF pages")
    pre.add_argument("--mode", choices=["contain", "cover"], default="contain")
    post = command.add_parser("verify", help="Read an existing preview and converted output")
    post.add_argument("--preview-json", required=True)
    post.add_argument("--input", required=True)
    post.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = (bound_preview(input_path=args.input, rules_text=args.rules, output=args.output,
                            pages=args.pages, mode=args.mode)
              if args.command == "preview" else
              verify_conversion(preview_path=args.preview_json, input_path=args.input,
                                output_path_str=args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"ready_for_review", "pass"} else 3


if __name__ == "__main__":
    sys.exit(main())

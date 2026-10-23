#!/usr/bin/env python3
"""JeChulOK: a local, offline-first file-submission CLI for agent skills.

Dependencies: Pillow and pypdf. Nothing is uploaded. Never overwrite user files.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from submission_rules import parse_requirements

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
    from pypdf import PdfReader, PdfWriter
except ImportError as exc:
    print(json.dumps({"status": "error", "message": "Install dependencies: python -m pip install -r requirements.txt", "detail": str(exc)}, ensure_ascii=False), file=sys.stdout)
    sys.exit(1)

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_OUTPUT_PIXELS = 24_000_000
MAX_PAGES = 300
Image.MAX_IMAGE_PIXELS = MAX_OUTPUT_PIXELS


def detect_format(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if b"%PDF-" in data[:1024]:
        return "pdf"
    if data[4:8] == b"ftyp":
        brands = data[8:24].lower()
        if b"avif" in brands or b"avis" in brands:
            return "avif"
        if any(brand in brands for brand in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1")):
            return "heic"
    return "unknown"


def extension_kind(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return {"jpeg": "jpg", "jfif": "jpg", "heif": "heic"}.get(suffix, suffix if suffix in {"jpg", "png", "gif", "webp", "pdf", "heic", "avif"} else "unknown")


def safe_file(path_str: str) -> Path:
    path = Path(path_str).expanduser().absolute()
    if path.is_symlink() or not path.is_file():
        raise ValueError("Input must be an existing regular file, not a symbolic link")
    return path


def info_for(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError("Input exceeds the 50 MiB inspection limit")
    with path.open("rb") as file:
        kind = detect_format(file.read(1024))
    result: dict[str, Any] = {"name": path.name, "format": kind, "extension": extension_kind(path), "size_bytes": size, "width": None, "height": None, "pages": None, "issues": []}
    if kind in {"jpg", "png", "webp", "gif"}:
        try:
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                result["width"], result["height"] = im.size
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            result["issues"].append("Cannot verify image dimensions or integrity: " + str(exc))
    elif kind == "pdf":
        if size > MAX_PDF_BYTES:
            result["issues"].append("PDF over 20 MiB: page count is unverified")
        else:
            try:
                reader = PdfReader(str(path), strict=False)
                if reader.is_encrypted:
                    result["issues"].append("Encrypted PDF: page count is unverified")
                else:
                    result["pages"] = len(reader.pages)
            except Exception as exc:
                result["issues"].append("Cannot read PDF pages: " + str(exc)[:240])
    elif kind in {"heic", "avif"}:
        result["issues"].append("HEIC/AVIF decoding is not supported by this v0.1 CLI")
    return result


def evaluation(meta: dict[str, Any], *, expected_format: str = "any", max_kb: int | None = None, width: int | None = None, height: int | None = None, max_pages: int | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(rule: str, state: str, expected: Any, actual: Any) -> None:
        checks.append({"rule": rule, "status": state, "expected": expected, "actual": actual})

    actual_format = meta["format"]
    if actual_format == "unknown":
        add("file_signature", "fail", "recognized file header", "unknown")
    else:
        add("file_signature", "pass", "recognized file header", actual_format)
    if meta["extension"] != "unknown" and actual_format != "unknown" and meta["extension"] != actual_format:
        add("extension_matches_content", "fail", meta["extension"], actual_format)
    if expected_format != "any":
        add("format", "pass" if actual_format == expected_format else "fail", expected_format, actual_format)
    if max_kb is not None:
        add("max_kb", "pass" if meta["size_bytes"] <= max_kb * 1024 else "fail", max_kb, meta["size_bytes"])
    for key, expected in (("width", width), ("height", height)):
        if expected is not None:
            actual = meta[key]
            state = "unverified" if actual is None and actual_format in {"jpg", "png", "webp", "gif", "heic", "avif"} else ("pass" if actual == expected else "fail")
            add(key, state, expected, actual)
    if max_pages is not None:
        actual = meta["pages"]
        status = "fail" if actual_format != "pdf" else "unverified" if actual is None else "pass" if actual <= max_pages else "fail"
        add("max_pages", status, max_pages, actual)
    states = [c["status"] for c in checks]
    specified = expected_format != "any" or max_kb is not None or width is not None or height is not None or max_pages is not None
    status = "fail" if "fail" in states else "unverified" if "unverified" in states else "pass" if specified else "info"
    return {"status": status, "file": meta, "checks": checks, "limitations": ["This verifies only explicit technical conditions; it does not verify document content, portrait composition, institution-specific rules, or acceptance by a submission system."]}


def file_report(path: Path, args: argparse.Namespace) -> dict[str, Any]:
    return evaluation(info_for(path), expected_format=args.format, max_kb=args.max_kb, width=args.width, height=args.height, max_pages=args.max_pages)


def pages_from(text: str, count: int) -> list[int]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Specify --pages, e.g. 1-3,5")
    pages: list[int] = []
    seen: set[int] = set()
    for token in text.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", token)
        if not match:
            raise ValueError("Invalid page range. Use 1-3,5")
        start = int(match[1])
        stop = int(match[2]) if match[2] else start
        if start < 1 or stop < start or stop > count:
            raise ValueError(f"Page range must be within 1..{count}")
        if stop - start >= MAX_PAGES:
            raise ValueError("A single operation supports at most 300 pages")
        for page in range(start, stop + 1):
            index = page - 1
            if index not in seen:
                seen.add(index)
                pages.append(index)
            if len(pages) > MAX_PAGES:
                raise ValueError("A single operation supports at most 300 pages")
    return pages


def output_path(input_path: Path, user_output: str | None, kind: str) -> Path:
    default = f"{input_path.stem}-jechulok.{kind}"
    path = Path(user_output).expanduser().absolute() if user_output else input_path.with_name(default)
    if path == input_path or path.exists() or path.is_symlink():
        raise ValueError("Output must be a new file, distinct from the original; overwriting is prohibited")
    if not path.parent.is_dir():
        raise ValueError("Output parent directory must exist")
    if kind == "jpg" and path.suffix.lower() not in {".jpg", ".jpeg"}:
        raise ValueError("JPG output path must end in .jpg or .jpeg")
    if kind == "pdf" and path.suffix.lower() != ".pdf":
        raise ValueError("PDF output path must end in .pdf")
    return path


def persist_validated(data: bytes, output: Path, constraints: dict[str, Any], *, expected_pages: int | None = None) -> dict[str, Any]:
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Generated output exceeds the 50 MiB inspection limit")
    created = False
    try:
        with output.open("xb") as fh:
            created = True
            fh.write(data)
        report = evaluation(info_for(output), **constraints)
        if expected_pages is not None and report["file"]["pages"] != expected_pages:
            raise ValueError("Output PDF page count did not match the selected pages")
        if report["status"] != "pass":
            raise ValueError("Output verification failed: " + report["status"] + "; " + json.dumps(report["checks"], ensure_ascii=False))
        return report
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise


def prepare_image(path: Path, args: argparse.Namespace) -> dict[str, Any]:
    metadata = info_for(path)
    if metadata["format"] not in {"jpg", "png", "webp"}:
        raise ValueError("Image conversion in v0.1 supports JPG, PNG and WebP sources")
    if metadata["width"] is None or metadata["height"] is None:
        raise ValueError("Source image could not be verified")
    dest = output_path(path, args.output, "jpg")
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGBA")
        width = args.width or im.width
        height = args.height or im.height
        if args.width is not None and args.height is None:
            height = round(im.height * width / im.width)
        if args.height is not None and args.width is None:
            width = round(im.width * height / im.height)
        if width <= 0 or height <= 0 or width * height > MAX_OUTPUT_PIXELS:
            raise ValueError("Output image must contain at most 24 million pixels")
        if args.mode == "cover":
            fitted = ImageOps.fit(im, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        else:
            fitted = ImageOps.contain(im, (width, height), method=Image.Resampling.LANCZOS)
        background = Image.new("RGB", (width, height), "white")
        background.paste(fitted, ((width - fitted.width)//2, (height - fitted.height)//2), fitted)
        buffer = io.BytesIO()
        best: bytes | None = None
        low, high = 8, 95
        threshold = args.max_kb * 1024 if args.max_kb is not None else None
        if threshold is None:
            background.save(buffer, format="JPEG", quality=92, optimize=True, progressive=True)
            best = buffer.getvalue()
        else:
            while low <= high:
                mid = (low + high)//2
                buffer.seek(0); buffer.truncate(0)
                background.save(buffer, format="JPEG", quality=mid, optimize=True, progressive=True)
                payload = buffer.getvalue()
                if len(payload) <= threshold:
                    best = payload
                    low = mid + 1
                else:
                    high = mid - 1
            if best is None:
                raise ValueError("Cannot satisfy the requested size even at low JPEG quality; reduce the pixel dimensions")
    rules = {"expected_format": "jpg", "max_kb": args.max_kb, "width": width, "height": height, "max_pages": None}
    report = persist_validated(best, dest, rules)
    return {"status": "pass", "operation": "prepare-image", "input": str(path), "output": str(dest), "mode": args.mode, "report": report, "warning": "White padding preserves the image; cover mode crops the center. Transparency and metadata are removed. Face positioning is not checked."}


def prepare_pdf(path: Path, args: argparse.Namespace) -> dict[str, Any]:
    meta = info_for(path)
    if meta["format"] != "pdf" or meta["pages"] is None:
        raise ValueError("PDF is encrypted, damaged, too large or has unreadable pages; cannot extract")
    if path.stat().st_size > MAX_PDF_BYTES:
        raise ValueError("PDF extraction is limited to 20 MiB files")
    indices = pages_from(args.pages, meta["pages"])
    dest = output_path(path, args.output, "pdf")
    reader = PdfReader(str(path), strict=False)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF is unsupported")
    writer = PdfWriter()
    for i in indices:
        writer.add_page(reader.pages[i])
    blob = io.BytesIO()
    writer.write(blob)
    constraints = {"expected_format": "pdf", "max_kb": args.max_kb, "width": None, "height": None, "max_pages": args.max_pages}
    report = persist_validated(blob.getvalue(), dest, constraints, expected_pages=len(indices))
    return {"status": "pass", "operation": "prepare-pdf", "input": str(path), "output": str(dest), "selected_pages": [i + 1 for i in indices], "report": report, "warning": "Extracted PDF may lose digital signatures, attachments, form behavior or bookmarks. Check the output before submission. This is not image recompression."}


def positive(value: str) -> int:
    val = int(value)
    if val < 1:
        raise argparse.ArgumentTypeError("Must be a positive integer")
    return val


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JeChulOK local submission-file checker and preparer (no network, no overwrite)")
    actions = parser.add_subparsers(dest="command", required=True)
    notice = actions.add_parser("parse-notice", help="Split explicit named file conditions in a long Korean notice (no edits)")
    notice.add_argument("--text", required=True)
    rule = actions.add_parser("parse-rules", help="Parse Korean submission conditions; does not modify files")
    rule.add_argument("--text", required=True)
    check = actions.add_parser("check", help="Inspect file and evaluate explicit constraints")
    check.add_argument("--input", required=True)
    check.add_argument("--format", choices=["any", "jpg", "png", "webp", "gif", "pdf"], default="any")
    check.add_argument("--max-kb", type=positive)
    check.add_argument("--width", type=positive)
    check.add_argument("--height", type=positive)
    check.add_argument("--max-pages", type=positive)
    image = actions.add_parser("prepare-image", help="Create a new JPG and verify format/dimensions/size")
    image.add_argument("--input", required=True)
    image.add_argument("--output", help="A new .jpg path; defaults to <stem>-jechulok.jpg")
    image.add_argument("--width", type=positive)
    image.add_argument("--height", type=positive)
    image.add_argument("--max-kb", type=positive)
    image.add_argument("--mode", choices=["contain", "cover"], default="contain", help="contain: white padding (default); cover: crop center only with explicit approval")
    pdf = actions.add_parser("prepare-pdf", help="Extract pages to a new PDF and verify page count")
    pdf.add_argument("--input", required=True)
    pdf.add_argument("--output", help="A new .pdf path; defaults to <stem>-jechulok.pdf")
    pdf.add_argument("--pages", required=True, help="Page ranges 1-3,5 (1-based, deduplicated, preserves requested order)")
    pdf.add_argument("--max-kb", type=positive)
    pdf.add_argument("--max-pages", type=positive)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "parse-rules":
            result = parse_requirements(args.text)
        elif args.command == "parse-notice":
            from notice_batch import analyze_notice
            result = analyze_notice(args.text)
        else:
            file = safe_file(args.input)
            if args.command == "check":
                result = file_report(file, args)
            elif args.command == "prepare-image":
                result = prepare_image(file, args)
            else:
                result = prepare_pdf(file, args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        state = result["status"]
        return 2 if state == "fail" else 3 if state in {"unverified", "needs_review", "no_rules", "no_items"} else 0
    except (ValueError, OSError, Image.DecompressionBombError, UnidentifiedImageError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1
    except Exception as exc:
        print(json.dumps({"status": "error", "message": f"Processing failure: {type(exc).__name__}: {str(exc)[:250]}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

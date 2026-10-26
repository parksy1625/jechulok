#!/usr/bin/env python3
"""v3.1 opt-in synthetic rehearsal of the real local JPG and PDF pipeline.

The only documents created/read are invented files inside an automatically
removed temporary directory. No client config, allowed directory or network
endpoint is consulted; no output files or paths are returned to callers.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import tempfile
from typing import Any

from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter

from jechulok import evaluation, info_for, prepare_image, prepare_pdf, safe_file
from submission_rules import parse_requirements

STAGES = ("requirements", "image_prepare", "image_recheck",
          "pdf_prepare", "pdf_recheck", "cleanup")


def _image_bytes() -> bytes:
    """Invent a nonsensitive illustration in memory, not a person's photo."""
    im = Image.new("RGB", (640, 480), "#d7e9fc")
    draw = ImageDraw.Draw(im)
    draw.rectangle((75, 55, 555, 425), fill="#178ba0")
    draw.ellipse((180, 95, 460, 375), fill="#f4d06f")
    stream = io.BytesIO()
    im.save(stream, format="PNG")
    return stream.getvalue()


def _pdf_bytes() -> bytes:
    """Three empty, differently-sized pages let us verify 2-3 selection."""
    writer = PdfWriter()
    for width, height in ((210, 310), (300, 400), (400, 500)):
        writer.add_blank_page(width=width, height=height)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def _new_file(path: Path, payload: bytes) -> None:
    # Exclusive creation: even temporary rehearsal files cannot be overwritten.
    with path.open("xb") as fh:
        fh.write(payload)


def _ok(condition: bool) -> None:
    if not condition:
        raise ValueError("Synthetic rehearsal assertion failed")


def _base_report() -> dict[str, Any]:
    return {
        "schema": "jechulok-offline-demo-v31", "status": "not_run",
        "stages": [{"id": stage, "status": "not_run"} for stage in STAGES],
        "synthetic_only": True, "personal_documents_read": False,
        "client_config_read": False, "client_config_modified": False,
        "network_used": False, "telemetry_sent": False,
        "external_submission_attempted": False,
        "institution_acceptance_verified": False,
        "outputs_persisted": False,
        "limitation": "Synthetic file structure and explicit technical rules only; not a real submission or human-document test.",
    }


def run_rehearsal() -> dict[str, Any]:
    """Exercise production functions and return only fixed, path-free facts.

    Unexpected errors become a fixed failure code. The temporary directory is
    torn down before the report leaves this function, including on failures.
    """
    report = _base_report()
    stage = "requirements"
    sandbox: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="jechulok-synthetic-v31-") as temp:
            sandbox = Path(temp)

            image_rules = parse_requirements("JPG 가로 300픽셀 세로 400픽셀, 500KB 이하")
            pdf_rules = parse_requirements("PDF 최대 2페이지")
            _ok(image_rules["status"] == "parsed")
            _ok(pdf_rules["status"] == "parsed")
            _ok(image_rules["rules"]["expected_format"] == "jpg")
            _ok(image_rules["rules"]["width"] == 300)
            _ok(image_rules["rules"]["height"] == 400)
            _ok(image_rules["rules"]["max_kb"] == 500)
            _ok(pdf_rules["rules"]["expected_format"] == "pdf")
            _ok(pdf_rules["rules"]["max_pages"] == 2)
            report["stages"][0]["status"] = "pass"

            png = sandbox / "invented-illustration.png"
            pdf = sandbox / "invented-pages.pdf"
            _new_file(png, _image_bytes())
            _new_file(pdf, _pdf_bytes())
            originals = (hashlib.sha256(png.read_bytes()).digest(),
                         hashlib.sha256(pdf.read_bytes()).digest())

            stage = "image_prepare"
            jpg_result = prepare_image(safe_file(str(png)), argparse.Namespace(
                output=str(sandbox / "prepared.jpg"), width=300, height=400,
                max_kb=500, mode="contain"))
            _ok(jpg_result["status"] == "pass")
            report["stages"][1]["status"] = "pass"

            stage = "image_recheck"
            jpg_meta = info_for(sandbox / "prepared.jpg")
            jpg_verdict = evaluation(jpg_meta, expected_format="jpg",
                                     width=300, height=400, max_kb=500)
            _ok(jpg_verdict["status"] == "pass")
            _ok(jpg_meta["extension"] == "jpg" and not jpg_meta["issues"])
            report["stages"][2]["status"] = "pass"

            stage = "pdf_prepare"
            pdf_result = prepare_pdf(safe_file(str(pdf)), argparse.Namespace(
                output=str(sandbox / "selected.pdf"), pages="2-3",
                max_kb=500, max_pages=2))
            _ok(pdf_result["status"] == "pass")
            _ok(pdf_result["selected_pages"] == [2, 3])
            report["stages"][3]["status"] = "pass"

            stage = "pdf_recheck"
            pdf_meta = info_for(sandbox / "selected.pdf")
            pdf_verdict = evaluation(pdf_meta, expected_format="pdf", max_pages=2,
                                     max_kb=500)
            _ok(pdf_verdict["status"] == "pass" and pdf_meta["pages"] == 2)
            selected = PdfReader(str(sandbox / "selected.pdf"))
            _ok([int(page.mediabox.width) for page in selected.pages] == [300, 400])
            _ok(hashlib.sha256(png.read_bytes()).digest() == originals[0])
            _ok(hashlib.sha256(pdf.read_bytes()).digest() == originals[1])
            report["stages"][4]["status"] = "pass"

        stage = "cleanup"
        _ok(sandbox is not None and not sandbox.exists())
        report["stages"][5]["status"] = "pass"
        report["status"] = "pass"
    except Exception:
        # No exception strings: they may contain local paths or library details.
        for item in report["stages"]:
            if item["id"] == stage:
                item["status"] = "fail"
                break
        report["status"] = "fail"
        report["failure_stage"] = stage
        # TemporaryDirectory always exits before this function returns.
        report["stages"][-1]["status"] = (
            "pass" if sandbox is not None and not sandbox.exists() else "unverified")
    return report


def render_text(report: dict[str, Any], *, language: str = "ko") -> str:
    if language not in {"ko", "en"}:
        raise ValueError("Unsupported language")
    ko = language == "ko"
    lines = ["제출OK 오프라인 가상 서류 연습" if ko else "JeChulOK Offline Synthetic Rehearsal",
             ("상태: " if ko else "Status: ") + report["status"]]
    for index, item in enumerate(report["stages"], 1):
        lines.append(f"{index}. {item['id']}: {item['status']}")
    lines.append("실제 서류 열람·업로드·영구 출력 없음" if ko else
                 "No personal documents, uploads or persistent outputs")
    lines.append("기관 접수 성공을 보증하지 않습니다" if ko else
                 "Does not prove institutional acceptance")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in offline synthetic JPG/PDF end-to-end rehearsal")
    parser.add_argument("--run", action="store_true", help="Explicitly create and process disposable synthetic files")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--language", choices=["ko", "en"], default="ko")
    args = parser.parse_args(argv)
    report = run_rehearsal() if args.run else _base_report()
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report, language=args.language), end="")
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())

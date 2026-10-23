#!/usr/bin/env python3
"""Synthetic, offline JPEG benchmark for JeChulOK v1.2.

Never reads user documents or network resources; outputs synthetic fixtures to
a temporary directory that is removed after the benchmark. Times vary by OS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from PIL import Image

import jechulok as core


def benchmark() -> dict[str, object]:
    with TemporaryDirectory(prefix="jechulok-synthetic-benchmark-") as temporary:
        folder = Path(temporary)
        source = folder / "synthetic.png"
        Image.effect_noise((1200, 900), 100).convert("RGB").save(source)
        cases: list[dict[str, object]] = []
        for label, limit_kb in (("generous_limit", 5000), ("tight_limit", 200)):
            output = folder / (label + ".jpg")
            args = argparse.Namespace(
                output=str(output), width=1200, height=900,
                max_kb=limit_kb, mode="contain",
            )
            result = core.prepare_image(source, args)
            if result["status"] != "pass":
                raise RuntimeError("Synthetic preparation did not pass")
            cases.append({
                "case": label, "limit_kb": limit_kb,
                "encoding_attempts": result["encoding_attempts"],
                "duration_ms": result["duration_ms"],
                "output_bytes": output.stat().st_size,
                "technical_status": result["report"]["status"],
            })
    return {
        "status": "pass",
        "fixtures": "synthetic_noise_only",
        "files_retained": False,
        "personal_documents_processed": False,
        "cases": cases,
        "note": "Timings are single-run observations, not a scientifically controlled speedup claim.",
    }


def main() -> int:
    result = benchmark()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

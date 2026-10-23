"""v1.2 fast JPEG path, verified fallback, timing and safe batch retry tests."""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import jechulok as core
import mcp_server as server

NOTICE = "- 증명사진: JPG 1200×900px 5000KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"


class PerformanceV12Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.env = patch.dict(os.environ, {"JECHULOK_ALLOWED_DIRS": str(self.root)})
        self.env.start()
        self.source = self.root / "photo.png"
        # Constant dimensions with non-uniform image content; expensive enough
        # to exercise the slow-quality-search path without large fixtures.
        Image.effect_noise((1200, 900), 100).convert("RGB").save(self.source)
        self.pdf = self.root / "resume.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=200, height=300)
        with self.pdf.open("wb") as f:
            writer.write(f)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_generous_limit_encodes_only_once(self):
        output = self.root / "wide.jpg"
        args = argparse.Namespace(output=str(output), width=1200, height=900,
                                  max_kb=5000, mode="contain")
        result = core.prepare_image(self.source, args)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["encoding_attempts"], 1)
        self.assertGreaterEqual(result["duration_ms"], 0)
        self.assertEqual(result["report"]["status"], "pass")
        self.assertLessEqual(output.stat().st_size, 5000 * 1024)

    def test_small_limit_retains_fallback_and_exact_verification(self):
        output = self.root / "tight.jpg"
        args = argparse.Namespace(output=str(output), width=1200, height=900,
                                  max_kb=200, mode="contain")
        result = core.prepare_image(self.source, args)
        self.assertEqual(result["status"], "pass", result)
        self.assertGreater(result["encoding_attempts"], 1)
        self.assertLessEqual(output.stat().st_size, 200 * 1024)
        self.assertEqual(result["report"]["status"], "pass")

    def test_impossible_budget_does_not_leave_output(self):
        output = self.root / "impossible.jpg"
        args = argparse.Namespace(output=str(output), width=1200, height=900,
                                  max_kb=1, mode="contain")
        with self.assertRaises(ValueError):
            core.prepare_image(self.source, args)
        self.assertFalse(output.exists())

    def test_batch_success_records_snapshot_timing(self):
        assignments = [
            {"item_id": "item_01", "input_path": str(self.source),
             "output_path": str(self.root / "ready.jpg")},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.root / "ready.pdf"), "pages_to_extract": "1-3"},
        ]
        dry = server.prepare_submission_batch(NOTICE, assignments)
        self.assertEqual(dry["status"], "planned")
        self.assertEqual(dry["progress"]["phase"], "awaiting_approval")
        self.assertEqual(dry["progress"]["completed_items"], 0)
        self.assertFalse(dry["progress"]["live_streaming"])
        self.assertGreaterEqual(dry["duration_ms"], 0)

        result = server.prepare_submission_batch(
            NOTICE, assignments, execute=True, confirm_execution=True
        )
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["progress"]["phase"], "completed")
        self.assertEqual(result["progress"]["percent"], 100)
        self.assertEqual(result["progress"]["completed_items"], 2)
        self.assertGreaterEqual(result["duration_ms"], 0)
        self.assertTrue(all(entry["duration_ms"] >= 0 for entry in result["results"]))
        self.assertEqual(result["results"][0]["preparation"]["encoding_attempts"], 1)
        self.assertEqual(result["summary"]["technically_verified"], 2)

    def test_batch_failure_retry_requires_fresh_approval(self):
        assignments = [
            {"item_id": "item_01", "input_path": str(self.source),
             "output_path": str(self.root / "ready.jpg")},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.root / "ready.pdf"), "pages_to_extract": "1-3"},
        ]
        with patch.object(core, "prepare_pdf", side_effect=ValueError("synthetic PDF error")):
            result = server.prepare_submission_batch(
                NOTICE, assignments, execute=True, confirm_execution=True
            )
        self.assertEqual(result["status"], "error", result)
        self.assertEqual(result["progress"]["phase"], "failed")
        self.assertEqual(result["progress"]["completed_items"], 0)
        self.assertFalse(result["retry_guidance"]["automatic_retry"])
        self.assertFalse(result["retry_guidance"]["reuse_prior_approval"])
        self.assertFalse((self.root / "ready.jpg").exists())
        self.assertFalse((self.root / "ready.pdf").exists())
        self.assertTrue(self.source.exists())
        self.assertTrue(self.pdf.exists())

    def test_blocked_progress_does_not_count_partial_preflight(self):
        assignments = [
            {"item_id": "item_01", "input_path": str(self.source),
             "output_path": str(self.root / "ready.jpg")},
            {"item_id": "item_02", "input_path": str(self.pdf),
             "output_path": str(self.root / "ready.pdf")},
        ]
        result = server.prepare_submission_batch(NOTICE, assignments)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["progress"]["phase"], "blocked")
        self.assertEqual(result["progress"]["percent"], 0)
        self.assertFalse(result["retry_guidance"]["automatic_retry"])


if __name__ == "__main__":
    unittest.main()

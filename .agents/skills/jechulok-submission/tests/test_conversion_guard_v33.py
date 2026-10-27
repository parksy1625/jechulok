"""Read-only v3.3 preview-to-output checks on invented files only."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from jechulok import build_parser, prepare_image, prepare_pdf, safe_file
from conversion_guard_v33 import bound_preview, main, verify_conversion


class ConversionGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        self.src = self.work / "private-imaginary.png"
        self.dst = self.work / "prepared.jpg"
        self.plan = self.work / "plan.json"
        # Deliberately varied pixels make a crop/padding mismatch detectable.
        im = Image.new("RGB", (640, 480), "#3a84a1")
        im.save(self.src)
        self.rules = "JPG 가로 300픽셀 세로 400픽셀 500KB 이하"

        self.pdf = self.work / "private-imaginary.pdf"
        self.pdf_dst = self.work / "prepared.pdf"
        writer = PdfWriter()
        for width in (210, 320, 430):
            writer.add_blank_page(width=width, height=500)
        with self.pdf.open("wb") as handle:
            writer.write(handle)

    def tearDown(self):
        self.temp.cleanup()

    def bound(self, *, source=None, output=None, rules=None, mode="contain", pages=None):
        return bound_preview(input_path=str(source or self.src),
                             output=str(output or self.dst),
                             rules_text=rules or self.rules, mode=mode, pages=pages)

    def save_plan(self, plan):
        self.plan.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    def verify(self, source=None, output=None):
        return verify_conversion(preview_path=str(self.plan),
                                 input_path=str(source or self.src),
                                 output_path_str=str(output or self.dst))

    def prepared_jpg(self, *, mode="contain", max_kb=500, width=300, height=400):
        args = build_parser().parse_args(["prepare-image", "--input", str(self.src),
                                          "--output", str(self.dst), "--width", str(width),
                                          "--height", str(height), "--max-kb", str(max_kb),
                                          "--mode", mode])
        return prepare_image(safe_file(str(self.src)), args)

    def prepared_pdf(self, *, pages="3,1"):
        args = build_parser().parse_args(["prepare-pdf", "--input", str(self.pdf),
                                          "--output", str(self.pdf_dst), "--pages", pages,
                                          "--max-pages", "2"])
        return prepare_pdf(safe_file(str(self.pdf)), args)

    def test_preview_has_salted_source_and_target_bindings(self):
        before = set(self.work.iterdir())
        plan = self.bound()
        self.assertEqual(plan["status"], "ready_for_review", plan)
        self.assertEqual(plan["schema"], "jechulok-bound-preview-v33")
        self.assertEqual(plan["binding"]["algorithm"], "sha256-salted-v1")
        self.assertEqual(len(plan["binding"]["salt_hex"]), 32)
        self.assertEqual(len(plan["binding"]["source_sha256"]), 64)
        self.assertEqual(set(self.work.iterdir()), before)
        self.assertFalse(plan["execution_permitted"])
        self.assertNotIn(str(self.work), json.dumps(plan))
        self.assertNotIn(self.src.name, json.dumps(plan))

    def test_salts_do_not_create_tracking_identifier(self):
        a, b = self.bound(), self.bound()
        self.assertNotEqual(a["binding"]["salt_hex"], b["binding"]["salt_hex"])
        self.assertNotEqual(a["binding"]["source_sha256"], b["binding"]["source_sha256"])

    def test_photo_passes_after_separately_approved_production_conversion(self):
        self.save_plan(self.bound())
        self.prepared_jpg()
        result = self.verify()
        self.assertEqual(result["status"], "pass", result)
        self.assertTrue(result["verified"])
        self.assertTrue(all(x["status"] == "pass" for x in result["checks"]))
        self.assertEqual(result["files_written"], 0)

    def test_output_dimensions_disagree(self):
        self.save_plan(self.bound())
        self.prepared_jpg(width=400)
        r = self.verify()
        self.assertEqual(r["status"], "blocked", r)
        self.assertIn("output_width", [x["code"] for x in r["checks"] if x["status"] == "fail"])

    def test_changed_source_is_detected_before_output_read(self):
        self.save_plan(self.bound())
        self.src.write_bytes(self.src.read_bytes() + b"different bytes")
        with patch("conversion_guard_v33.info_for", side_effect=AssertionError("output not allowed")):
            r = self.verify()
        self.assertEqual(r["reason_code"], "source_changed_since_preview")

    def test_wrong_target_is_detected(self):
        self.save_plan(self.bound())
        self.prepared_jpg()
        copy = self.work / "wrong-target.jpg"
        copy.write_bytes(self.dst.read_bytes())
        self.assertEqual(self.verify(output=copy)["reason_code"], "output_path_not_in_preview")

    def test_output_not_yet_created(self):
        self.save_plan(self.bound())
        self.assertEqual(self.verify()["reason_code"], "file_missing_or_unreadable")

    def test_plan_tamper_detected(self):
        plan = self.bound()
        plan["planned_output"]["width"] = 333
        self.save_plan(plan)
        self.assertEqual(self.verify()["reason_code"], "invalid_or_modified_preview")

    def test_duplicate_json_keys_rejected(self):
        self.plan.write_text('{"schema":"a","schema":"b"}', encoding="utf-8")
        self.assertEqual(self.verify()["reason_code"], "invalid_or_modified_preview")

    def test_nonexistent_plan_rejected(self):
        self.assertEqual(self.verify()["reason_code"], "invalid_or_modified_preview")

    def test_oversized_plan_rejected(self):
        self.plan.write_text("x" * (64 * 1024 + 1), encoding="utf-8")
        self.assertEqual(self.verify()["reason_code"], "invalid_or_modified_preview")

    def test_plan_file_symlink_rejected(self):
        other = self.work / "other.json"
        other.write_text("{}", encoding="utf-8")
        try:
            self.plan.symlink_to(other)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.assertEqual(self.verify()["reason_code"], "invalid_or_modified_preview")

    def test_bad_padding_detected(self):
        self.save_plan(self.bound())
        Image.new("RGB", (300, 400), "black").save(self.dst, "JPEG")
        result = self.verify()
        self.assertEqual(result["reason_code"], "postflight_mismatch", result)
        self.assertIn("white_padding_interior", [x["code"] for x in result["checks"]
                                                     if x["status"] == "fail"])

    def test_cover_passes_without_padding_inference(self):
        self.save_plan(self.bound(mode="cover"))
        self.prepared_jpg(mode="cover")
        result = self.verify()
        self.assertEqual(result["status"], "pass", result)
        self.assertFalse(any(x["code"] == "white_padding_interior" for x in result["checks"]))

    def test_display_rotation_metadata_mismatch_is_rejected(self):
        self.save_plan(self.bound(mode="cover"))
        photo = Image.new("RGB", (300, 400), "navy")
        exif = photo.getexif()
        exif[274] = 6
        photo.save(self.dst, "JPEG", exif=exif)
        result = self.verify()
        self.assertEqual(result["reason_code"], "postflight_mismatch", result)
        self.assertIn("output_exif_orientation_cleared", [x["code"] for x in result["checks"]
                                                         if x["status"] == "fail"])

    def test_tiny_padding_requires_review_not_false_pass(self):
        self.save_plan(self.bound(rules="JPG 가로 640픽셀 세로 485픽셀"))
        Image.new("RGB", (640, 485), "black").save(self.dst, "JPEG")
        result = self.verify()
        self.assertEqual(result["status"], "needs_review", result)
        self.assertFalse(result["verified"])

    def test_too_large_jpg_is_blocked(self):
        self.save_plan(self.bound(rules="JPG 가로 300픽셀 세로 400픽셀 1KB 이하"))
        Image.new("RGB", (300, 400), "#224466").save(self.dst, "JPEG", quality=95)
        result = self.verify()
        self.assertEqual(result["status"], "blocked", result)
        self.assertIn("output_size_limit", [x["code"] for x in result["checks"]
                                               if x["status"] == "fail"])

    def test_pdf_selected_page_geometry_and_order_pass(self):
        self.save_plan(self.bound(source=self.pdf, output=self.pdf_dst,
                                  rules="PDF 최대 2페이지", pages="3,1"))
        self.prepared_pdf(pages="3,1")
        result = self.verify(source=self.pdf, output=self.pdf_dst)
        self.assertEqual(result["status"], "pass", result)

    def test_pdf_page_order_mismatch_fails_even_when_count_matches(self):
        self.save_plan(self.bound(source=self.pdf, output=self.pdf_dst,
                                  rules="PDF 최대 2페이지", pages="3,1"))
        self.prepared_pdf(pages="1,3")
        result = self.verify(source=self.pdf, output=self.pdf_dst)
        self.assertEqual(result["reason_code"], "postflight_mismatch", result)
        self.assertIn("selected_page_geometries_and_order", [x["code"] for x in result["checks"]
                                                         if x["status"] == "fail"])

    def test_pdf_page_count_mismatch_fails(self):
        self.save_plan(self.bound(source=self.pdf, output=self.pdf_dst,
                                  rules="PDF 최대 2페이지", pages="3,1"))
        self.prepared_pdf(pages="2")
        result = self.verify(source=self.pdf, output=self.pdf_dst)
        self.assertEqual(result["status"], "blocked", result)

    def test_invalid_rules_do_not_read_source(self):
        with patch("conversion_guard_v33.safe_file", side_effect=AssertionError("read attempted")):
            result = self.bound(rules="색깔을 좋게 만들어줘")
        self.assertEqual(result["status"], "needs_review")

    def test_unsaved_preview_has_no_implicit_conversion(self):
        initial = {file.name: file.read_bytes() for file in self.work.iterdir()}
        result = self.bound()
        self.assertEqual(result["files_written"], 0)
        self.assertEqual({file.name: file.read_bytes() for file in self.work.iterdir()}, initial)

    def test_cli_preview_and_postflight_stdout_are_path_free(self):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main(["preview", "--input", str(self.src), "--output", str(self.dst),
                         "--rules", self.rules])
        self.assertEqual(code, 0)
        self.assertNotIn(str(self.work), stdout.getvalue())
        self.plan.write_text(stdout.getvalue(), encoding="utf-8")
        self.prepared_jpg()
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main(["verify", "--preview-json", str(self.plan),
                         "--input", str(self.src), "--output", str(self.dst)])
        self.assertEqual(code, 0, stdout.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())["status"], "pass")
        self.assertNotIn(str(self.work), stdout.getvalue())


if __name__ == "__main__":
    unittest.main()

"""v3.2 safe, truthful previews without creating or approving outputs."""
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

import preview_prepare_v32 as preview
from preview_audit_v32 import run_audit


class PreviewV32Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.png = self.folder / "invented.png"
        self.jpg = self.folder / "invented.jpg"
        self.pdf = self.folder / "blank.pdf"
        Image.new("RGB", (640, 480), "#00abc2").save(self.png)
        Image.new("RGB", (300, 400), "#00abc2").save(self.jpg)
        writer = PdfWriter()
        for width in (200, 300, 400):
            writer.add_blank_page(width=width, height=500)
        with self.pdf.open("wb") as handle:
            writer.write(handle)
        self.photo_rules = "JPG 가로 300픽셀 세로 400픽셀 500KB 이하"
        self.pdf_rules = "PDF 최대 2페이지"

    def tearDown(self):
        self.tmp.cleanup()

    def image(self, **kwargs):
        return preview.preview_file(input_path=str(self.png), rules_text=self.photo_rules, **kwargs)

    def test_contain_predicts_padding_fraction_and_dimensions(self):
        result = self.image()
        self.assertEqual(result["status"], "ready_for_review", result)
        self.assertEqual(result["action"], "prepare_image")
        self.assertEqual(result["planned_output"]["width"], 300)
        self.assertEqual(result["planned_output"]["height"], 400)
        padding = next(r for r in result["risks"] if r["code"] == "white_padding")
        self.assertAlmostEqual(padding["estimated_area_pct"], 43.8)

    def test_cover_requires_explicit_crop_approval(self):
        result = self.image(mode="cover")
        crop = next(r for r in result["risks"] if r["code"] == "center_crop")
        self.assertTrue(crop["requires_separate_approval"])
        self.assertTrue(any(r["code"] == "cover_mode_requires_approval" for r in result["risks"]))
        self.assertFalse(result["execution_permitted"])

    def test_unpredictable_jpeg_bytes_never_converted_into_fake_estimate(self):
        result = self.image()
        self.assertIsNone(result["planned_output"]["estimated_size_bytes"])
        self.assertFalse(result["planned_output"]["size_limit_guaranteed"])
        self.assertFalse(result["exact_output_size_predictable"])

    def test_size_cap_risk_is_visible(self):
        self.assertIn("jpeg_size_may_not_fit", [r["code"] for r in self.image()["risks"]])

    def test_width_only_preserves_ratio_without_letterboxing(self):
        r = preview.preview_file(input_path=str(self.png),
                                 rules_text="JPG 가로 300픽셀")
        self.assertEqual(r["planned_output"]["height"], 225)
        self.assertNotIn("white_padding", [x["code"] for x in r["risks"]])

    def test_exif_orientation_swaps_source_dimensions(self):
        rotated = self.folder / "rotated.jpg"
        im = Image.new("RGB", (640, 480), "red")
        exif = im.getexif()
        exif[274] = 6
        im.save(rotated, exif=exif)
        r = preview.preview_file(input_path=str(rotated),
                                 rules_text="JPG 가로 320픽셀")
        self.assertEqual(r["planned_output"]["height"], 427)
        self.assertIn("exif_orientation_applied", [x["code"] for x in r["risks"]])

    def test_already_compliant_jpg_does_not_reencode_without_reason(self):
        r = preview.preview_file(input_path=str(self.jpg), rules_text=self.photo_rules)
        self.assertEqual(r["status"], "already_compliant", r)
        self.assertEqual(r["action"], "check_only")
        self.assertEqual(r["risks"], [])

    def test_proposed_output_requests_separate_new_file(self):
        r = preview.preview_file(input_path=str(self.jpg), rules_text=self.photo_rules,
                                 output=str(self.folder / "brand-new.jpg"))
        self.assertEqual(r["action"], "prepare_image")

    def test_existing_output_fails_closed(self):
        r = self.image(output=str(self.jpg))
        self.assertEqual(r["status"], "blocked")
        self.assertEqual(r["reason_code"], "output_exists_or_invalid")

    def test_output_equal_to_input_fails_closed(self):
        r = self.image(output=str(self.png))
        self.assertEqual(r["status"], "blocked")

    def test_bad_extension_output_fails_closed(self):
        r = self.image(output=str(self.folder / "new.pdf"))
        self.assertEqual(r["reason_code"], "output_exists_or_invalid")

    def test_symlink_input_is_not_followed(self):
        alias = self.folder / "alias.png"
        try:
            alias.symlink_to(self.png)
        except (NotImplementedError, OSError):
            self.skipTest("Platform cannot create symlink")
        r = preview.preview_file(input_path=str(alias), rules_text=self.photo_rules)
        self.assertEqual(r["status"], "blocked")
        self.assertEqual(r["reason_code"], "input_missing_or_unreadable")

    def test_ambiguous_rules_stop_before_file_access(self):
        with patch.object(preview, "info_for", side_effect=AssertionError("not allowed")):
            r = preview.preview_file(input_path=str(self.png), rules_text="사진 흰 배경")
        self.assertEqual(r["status"], "needs_review")
        self.assertIsNone(r["input"])

    def test_missing_format_stops_before_file_access(self):
        with patch.object(preview, "info_for", side_effect=AssertionError("not allowed")):
            r = preview.preview_file(input_path=str(self.png), rules_text="500KB 이하")
        self.assertEqual(r["reason_code"], "unsupported_or_missing_target_format")

    def test_invalid_notice_text_is_not_echoed(self):
        text = "<my private identity>"
        r = preview.preview_file(input_path=str(self.png), rules_text=text)
        self.assertNotIn(text, json.dumps(r))

    def test_rule_issues_are_codes_not_sensitive_quotes(self):
        r = preview.preview_file(input_path=str(self.png),
                                 rules_text="JPG 최대 200KB, 최대 300KB")
        self.assertEqual(r["status"], "needs_review")
        self.assertEqual(r["reason_code"], "ambiguous_or_missing_requirements")
        self.assertTrue(r["rule_issue_codes"])

    def test_pdf_needs_pages_if_limit_exceeded(self):
        r = preview.preview_file(input_path=str(self.pdf), rules_text=self.pdf_rules)
        self.assertEqual(r["action"], "choose_pages")
        self.assertIsNone(r["planned_output"])

    def test_pdf_selection_returns_explicit_order(self):
        r = preview.preview_file(input_path=str(self.pdf), rules_text=self.pdf_rules,
                                 pages="3,2")
        self.assertEqual(r["status"], "ready_for_review", r)
        self.assertEqual(r["planned_output"]["selected_pages"], [3, 2])
        self.assertEqual(r["planned_output"]["page_count"], 2)

    def test_pdf_too_many_pages_blocked(self):
        r = preview.preview_file(input_path=str(self.pdf), rules_text=self.pdf_rules,
                                 pages="1-3")
        self.assertEqual(r["reason_code"], "selected_pages_exceed_limit")

    def test_pdf_invalid_range_blocked(self):
        r = preview.preview_file(input_path=str(self.pdf), rules_text=self.pdf_rules,
                                 pages="42")
        self.assertEqual(r["reason_code"], "invalid_pdf_page_selection")

    def test_pdf_preserves_signature_warning(self):
        r = preview.preview_file(input_path=str(self.pdf), rules_text=self.pdf_rules,
                                 pages="2-3")
        self.assertIn("pdf_signatures_forms_bookmarks_may_change", [x["code"] for x in r["risks"]])

    def test_pdf_and_cover_incompatible(self):
        r = preview.preview_file(input_path=str(self.pdf), rules_text=self.pdf_rules,
                                 pages="2-3", mode="cover")
        self.assertEqual(r["reason_code"], "incompatible_options")

    def test_image_and_pdf_pages_incompatible(self):
        self.assertEqual(self.image(pages="1-2")["reason_code"], "incompatible_options")

    def test_pdf_without_selecting_pages_when_already_small(self):
        r = preview.preview_file(input_path=str(self.pdf), rules_text="PDF 최대 3페이지")
        self.assertEqual(r["status"], "already_compliant")

    def test_pdf_extension_mismatch_is_not_called_compliant(self):
        renamed = self.folder / "pdf-with-jpg-extension.jpg"
        renamed.write_bytes(self.pdf.read_bytes())
        r = preview.preview_file(input_path=str(renamed), rules_text="PDF 최대 3페이지")
        self.assertEqual(r["reason_code"], "pdf_extension_mismatch")

    def test_pdf_cannot_claim_recompression(self):
        r = preview.preview_file(input_path=str(self.pdf), rules_text="PDF 1KB 이하")
        self.assertNotEqual(r["action"], "compress_pdf")
        if self.pdf.stat().st_size <= 1024:
            self.assertEqual(r["status"], "already_compliant")
        else:
            self.assertEqual(r["reason_code"], "pdf_size_cannot_be_shrunk_by_preview")

    def test_missing_source_and_error_do_not_leak_path(self):
        missing = self.folder / "secret-name.pdf"
        r = preview.preview_file(input_path=str(missing), rules_text=self.pdf_rules)
        self.assertEqual(r["reason_code"], "input_missing_or_unreadable")
        self.assertNotIn(str(self.folder), json.dumps(r))

    def test_unexpected_input_error_is_not_echoed(self):
        with patch.object(preview, "info_for", side_effect=RuntimeError("sensitive path")):
            r = self.image()
        self.assertEqual(r["reason_code"], "input_inspection_failed")
        self.assertNotIn("sensitive path", json.dumps(r))

    def test_no_writes_and_no_sensitive_file_names(self):
        original = {p.name: p.read_bytes() for p in (self.png, self.jpg, self.pdf)}
        before = {p.name for p in self.folder.iterdir()}
        output = self.image()
        self.assertEqual({p.name for p in self.folder.iterdir()}, before)
        self.assertEqual({p.name: p.read_bytes() for p in (self.png, self.jpg, self.pdf)}, original)
        serialized = json.dumps(output)
        self.assertNotIn(str(self.folder), serialized)
        self.assertNotIn(self.png.name, serialized)
        self.assertEqual(output["files_written"], 0)

    def test_cli_json_and_text(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(preview.main(["--input", str(self.png), "--rules", self.photo_rules,
                                           "--format", "json"]), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "ready_for_review")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(preview.main(["--input", str(self.png), "--rules", self.photo_rules]), 0)
        self.assertIn("읽기 전용", out.getvalue())
        self.assertIn("흰 여백", out.getvalue())

    def test_six_synthetic_audits(self):
        r = run_audit()
        self.assertEqual(r["scenario_count"], r["passed_count"])
        self.assertEqual(r["scenario_count"], 6)
        self.assertEqual(r["status"], "pass")


if __name__ == "__main__":
    unittest.main()

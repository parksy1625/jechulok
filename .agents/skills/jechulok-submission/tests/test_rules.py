"""Conservative parsing regressions: ambiguity must block automated work."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from submission_rules import parse_requirements


class ParseRuleTests(unittest.TestCase):
    def test_photo_exact(self):
        r=parse_requirements("지원서 사진 JPG, 300×400px, 500KB 이하")
        self.assertEqual(r["status"],"parsed")
        self.assertTrue(r["auto_prepare_image"])
        self.assertEqual({k:r["rules"][k] for k in ("expected_format","width","height","max_kb")},{"expected_format":"jpg","width":300,"height":400,"max_kb":500})

    def test_axis_mb(self):
        r=parse_requirements("JPEG 가로 300px 세로 400px 최대 1.5MB")
        self.assertEqual(r["status"],"parsed")
        self.assertEqual(r["rules"]["max_kb"],1536)
        self.assertEqual((r["rules"]["width"],r["rules"]["height"]),(300,400))

    def test_pdf(self):
        r=parse_requirements("PDF 10MB 이하, 최대 5페이지")
        self.assertEqual(r["status"],"parsed")
        self.assertEqual(r["rules"]["max_kb"],10240)
        self.assertEqual(r["rules"]["max_pages"],5)

    def test_format_ambiguity(self):
        r=parse_requirements("JPG 또는 PNG 500KB 이하")
        self.assertEqual(r["status"],"needs_review")
        self.assertIsNone(r["rules"]["expected_format"])

    def test_physical_size(self):
        r=parse_requirements("JPG 3x4cm")
        self.assertEqual(r["status"],"needs_review")
        self.assertIsNone(r["rules"]["width"])

    def test_missing_unit(self):
        r=parse_requirements("JPG 300x400 500KB 이하")
        self.assertEqual(r["status"],"needs_review")
        self.assertIsNone(r["rules"]["width"])

    def test_minimum_not_maximum(self):
        r=parse_requirements("JPG 500KB 이상")
        self.assertEqual(r["status"],"needs_review")
        self.assertIsNone(r["rules"]["max_kb"])

    def test_strict_less_than(self):
        r=parse_requirements("JPG 500KB 미만")
        self.assertEqual(r["status"],"needs_review")
        self.assertIsNone(r["rules"]["max_kb"])

    def test_plain_size_not_max(self):
        r=parse_requirements("PDF 5MB")
        self.assertEqual(r["status"],"needs_review")

    def test_conflicting_pixels(self):
        r=parse_requirements("JPG 300×400px, 600×800px 500KB 이하")
        self.assertEqual(r["status"],"needs_review")
        self.assertIsNone(r["rules"]["width"])

    def test_background_not_verified(self):
        r=parse_requirements("JPG 300×400px, 500KB 이하, 흰색 배경")
        self.assertEqual(r["status"],"needs_review")
        self.assertTrue(r["unsupported_conditions"])

    def test_excessive_image_pixels(self):
        r=parse_requirements("JPG 9000×9000px, 10MB 이하")
        self.assertEqual(r["status"],"needs_review")

    def test_narrative_only(self):
        self.assertEqual(parse_requirements("서류를 제출하세요")["status"],"no_rules")

    def test_bad_input(self):
        for text in (""," ","X"*5001):
            with self.assertRaises(ValueError):
                parse_requirements(text)

    def test_cli_exit_codes(self):
        cli=str(ROOT/"scripts"/"jechulok.py")
        ok=subprocess.run([sys.executable,cli,"parse-rules","--text","JPG 300x400px 500KB 이하"],text=True,capture_output=True)
        self.assertEqual(ok.returncode,0,ok.stdout+ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["rules"]["max_kb"],500)
        bad=subprocess.run([sys.executable,cli,"parse-rules","--text","JPG 또는 PNG 500KB 이하"],text=True,capture_output=True)
        self.assertEqual(bad.returncode,3)

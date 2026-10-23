import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import jechulok as app


class JeChulOKTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.png = self.path / "sample.png"
        Image.new("RGBA", (600, 600), (220, 40, 75, 120)).save(self.png)
        self.pdf = self.path / "sample.pdf"
        w = PdfWriter()
        for _ in range(8):
            w.add_blank_page(width=310, height=420)
        with self.pdf.open("wb") as f:
            w.write(f)

    def tearDown(self):
        self.temp.cleanup()

    def test_detect_signatures(self):
        self.assertEqual(app.detect_format(b"\xff\xd8\xffx"), "jpg")
        self.assertEqual(app.detect_format(self.png.read_bytes()[:1024]), "png")
        self.assertEqual(app.detect_format(b"garbage"), "unknown")
        self.assertEqual(app.detect_format(self.pdf.read_bytes()[:1024]), "pdf")

    def test_info_and_constraints(self):
        result = app.evaluation(app.info_for(self.png), expected_format="png", width=600, height=600, max_kb=100)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(app.evaluation(app.info_for(self.png), width=300)["status"], "fail")
        self.assertEqual(app.evaluation(app.info_for(self.png))["status"], "info")
        self.assertEqual(app.info_for(self.pdf)["pages"], 8)
        self.assertEqual(app.evaluation(app.info_for(self.pdf), expected_format="pdf", max_pages=4)["status"], "fail")

    def test_extension_mismatch(self):
        renamed = self.path / "misleading.jpg"
        renamed.write_bytes(self.png.read_bytes())
        failed = app.evaluation(app.info_for(renamed), expected_format="jpg")
        self.assertEqual(failed["status"], "fail")
        self.assertIn("extension_matches_content", [c["rule"] for c in failed["checks"]])

    def test_image_contain_and_validate(self):
        args = argparse.Namespace(output=None, width=300, height=400, max_kb=500, mode="contain")
        result = app.prepare_image(self.png, args)
        self.assertEqual(result["status"], "pass")
        output = Path(result["output"])
        self.assertTrue(output.exists())
        self.assertEqual(app.info_for(output)["format"], "jpg")
        self.assertEqual(app.info_for(output)["width"], 300)
        self.assertEqual(app.info_for(output)["height"], 400)
        self.assertLessEqual(output.stat().st_size, 500*1024)
        with Image.open(output) as im:
            self.assertEqual(im.getpixel((5, 10)), (255, 255, 255))  # white padding, no crop
        with self.assertRaises(ValueError):
            app.prepare_image(self.png, args)  # output exists: no overwrite

    def test_image_cover_explicit(self):
        args = argparse.Namespace(output=str(self.path / "covered.jpg"), width=300, height=400, max_kb=500, mode="cover")
        result = app.prepare_image(self.png, args)
        with Image.open(result["output"]) as im:
            self.assertEqual(im.size, (300, 400))
            self.assertNotEqual(im.getpixel((5, 10)), (255, 255, 255))

    def test_unachievable_max_bytes_does_not_save(self):
        args = argparse.Namespace(output=str(self.path / "unpossible.jpg"), width=2000, height=2000, max_kb=1, mode="contain")
        with self.assertRaises(ValueError):
            app.prepare_image(self.png, args)
        self.assertFalse(Path(args.output).exists())

    def test_pdf_extract_and_verify(self):
        args = argparse.Namespace(output=None, pages="2-4,7", max_kb=None, max_pages=4)
        result = app.prepare_pdf(self.pdf, args)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["selected_pages"], [2, 3, 4, 7])
        self.assertEqual(len(PdfReader(result["output"]).pages), 4)
        self.assertEqual(result["report"]["file"]["pages"], 4)
        with self.assertRaises(ValueError):
            app.prepare_pdf(self.pdf, args)

    def test_page_ranges(self):
        self.assertEqual(app.pages_from("4,2-3,2", 8), [3, 1, 2])
        for item in ("", "0", "3-2", "1-9", "a", "2--3"):
            with self.subTest(item=item), self.assertRaises(ValueError):
                app.pages_from(item, 8)

    def test_unverified_pdf(self):
        encrypted_path = self.path / "encrypted.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.encrypt("secret")
        with encrypted_path.open("wb") as f:
            writer.write(f)
        info = app.info_for(encrypted_path)
        self.assertIsNone(info["pages"])
        self.assertEqual(app.evaluation(info, expected_format="pdf", max_pages=5)["status"], "unverified")

    def test_unknown_file_fails(self):
        invalid = self.path / "fake.pdf"
        invalid.write_bytes(b"random file content")
        self.assertEqual(app.evaluation(app.info_for(invalid))["status"], "fail")

    def test_cli_json_and_exit_codes(self):
        program = ROOT / "scripts" / "jechulok.py"
        cmd = [sys.executable, str(program), "check", "--input", str(self.png), "--format", "jpg", "--width", "300"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "fail")
        good = subprocess.run([sys.executable, str(program), "check", "--input", str(self.pdf), "--format", "pdf", "--max-pages", "8"], capture_output=True, text=True)
        self.assertEqual(good.returncode, 0)
        self.assertEqual(json.loads(good.stdout)["status"], "pass")


if __name__ == "__main__":
    unittest.main()

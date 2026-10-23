"""CLI v0.4 long notice parsing tests."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NoticeCLITests(unittest.TestCase):
    def test_parse_notice_cli(self):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "jechulok.py"),
                               "parse-notice", "--text",
                               "- 증명사진: JPG 300×400px 500KB 이하\n- 이력서: PDF 5MB 이하, 최대 3페이지"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["status"], "parsed")
        self.assertEqual(result["total_items"], 2)

    def test_ambiguous_notice_exit_nonzero(self):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "jechulok.py"),
                               "parse-notice", "--text", "JPG 또는 PNG, 500KB 이하"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(json.loads(proc.stdout)["status"], "needs_review")

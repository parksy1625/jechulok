"""MCP v0.3 tool discovery and real local preparation integration."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader,PdfWriter
from mcp import Client,StdioServerParameters

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import mcp_server as server


class V03Tools(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name).resolve()
        self.photo=self.folder/"original.png"
        Image.new("RGB",(600,450),"#3878b0").save(self.photo)
        self.pdf=self.folder/"original.pdf"
        writer=PdfWriter()
        for i in range(8):writer.add_blank_page(width=200,height=300)
        with self.pdf.open("wb") as fp:writer.write(fp)
        self.env=patch.dict(os.environ,{"JECHULOK_ALLOWED_DIRS":str(self.folder)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    async def test_six_tools_and_parser(self):
        async with Client(server.mcp) as client:
            listing=await client.list_tools()
            self.assertEqual({x.name for x in listing.tools},{"check_file","prepare_image","extract_pdf_pages","verify_submission","parse_submission_rules","prepare_from_requirements","analyze_submission_notice","prepare_submission_batch","suggest_submission_files", "suggest_submission_output_paths", "review_submission_plan", "verify_submission_package", "guide_submission_workflow", "create_submission_html_report", "start_submission_job", "get_submission_job", "cancel_submission_job", "list_interrupted_submission_jobs", "resolve_interrupted_submission_job"})
            r=await client.call_tool("parse_submission_rules",{"requirements_text":"JPG 300×400px 500KB 이하"})
            self.assertEqual(r.structured_content["status"],"parsed")

    async def test_prepare_photo_with_reverification(self):
        path=self.folder/"ready.jpg"
        async with Client(server.mcp) as client:
            r=await client.call_tool("prepare_from_requirements",{"input_path":str(self.photo),"output_path":str(path),"requirements_text":"JPG 가로 300px 세로 400px 최대 500KB"})
            self.assertEqual(r.structured_content["status"],"pass",r.structured_content)
            self.assertEqual(r.structured_content["verification"]["status"],"pass")
            self.assertLessEqual(path.stat().st_size,500*1024)
            with Image.open(path) as img:self.assertEqual(img.size,(300,400))
            self.assertTrue(self.photo.exists())

    async def test_ambiguous_no_write(self):
        for rules in ["JPG 또는 PNG 500KB 이하","JPG 3x4cm","JPG 300x400px 흰색 배경"]:
            path=self.folder/"blocked.jpg"
            async with Client(server.mcp) as client:
                r=await client.call_tool("prepare_from_requirements",{"input_path":str(self.photo),"output_path":str(path),"requirements_text":rules})
                self.assertEqual(r.structured_content["status"],"needs_review")
                self.assertFalse(path.exists())

    async def test_pdf_pages_require_explicit_selection(self):
        path=self.folder/"ready.pdf"
        async with Client(server.mcp) as client:
            arguments={"input_path":str(self.pdf),"output_path":str(path),"requirements_text":"PDF 10MB 이하, 최대 4페이지"}
            hold=await client.call_tool("prepare_from_requirements",arguments)
            self.assertEqual(hold.structured_content["status"],"needs_review")
            self.assertFalse(path.exists())
            done=await client.call_tool("prepare_from_requirements",{**arguments,"pages_to_extract":"2-4,7"})
            self.assertEqual(done.structured_content["status"],"pass",done.structured_content)
            self.assertEqual(len(PdfReader(str(path)).pages),4)
            self.assertTrue(self.pdf.exists())

    async def test_crop_requires_approval(self):
        path=self.folder/"crop.jpg"
        args={"input_path":str(self.photo),"output_path":str(path),"requirements_text":"JPG 300×400px 500KB 이하","mode":"cover"}
        async with Client(server.mcp) as client:
            refused=await client.call_tool("prepare_from_requirements",args)
            self.assertEqual(refused.structured_content["status"],"error")
            self.assertFalse(path.exists())
            approved=await client.call_tool("prepare_from_requirements",{**args,"crop_approved":True})
            self.assertEqual(approved.structured_content["status"],"pass")

    async def test_allowed_folders_enforced(self):
        with tempfile.TemporaryDirectory() as outside:
            path=Path(outside)/"out.jpg"
            async with Client(server.mcp) as client:
                r=await client.call_tool("prepare_from_requirements",{"input_path":str(self.photo),"output_path":str(path),"requirements_text":"JPG 300×400px 500KB 이하"})
                self.assertEqual(r.structured_content["status"],"error")
                self.assertFalse(path.exists())

    async def test_real_stdio_transport(self):
        options=StdioServerParameters(command=sys.executable,args=[str(ROOT/"scripts"/"mcp_server.py")],env={"JECHULOK_ALLOWED_DIRS":str(self.folder)})
        async with Client(options) as client:
            tools=await client.list_tools()
            self.assertEqual(len(tools.tools),19)
            r=await client.call_tool("parse_submission_rules",{"requirements_text":"PDF 5MB 이하, 최대 3페이지"})
            self.assertFalse(r.is_error)
            self.assertEqual(r.structured_content["rules"]["max_pages"],3)

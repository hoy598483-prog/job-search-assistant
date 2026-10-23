import base64
import io
import unittest
import zipfile
import sys
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work" / "companion_vendor"))

from companion.resume_text import extract_resume, analyze_pdf


def encoded(data):
    return base64.b64encode(data).decode("ascii")


class ResumeTests(unittest.TestCase):
    def test_original_pdf_images_sent_and_cleaned(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=600, height=800)
        data = io.BytesIO()
        writer.write(data)
        image_paths = []
        def stream(messages, samples, local_images):
            self.assertEqual(samples, [])
            self.assertIn('原始简历页面图片', messages[0]['content'])
            self.assertTrue(local_images)
            for path in local_images:
                self.assertTrue(path.exists())
                self.assertEqual(path.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
                image_paths.append(path)
            yield {'type':'done', 'reply':'待本人核对的背景草案'}
        with patch('companion.streaming.chat_stream', side_effect=stream):
            result = analyze_pdf(encoded(data.getvalue()))
        self.assertEqual(result['mode'], 'original_pdf_pages')
        self.assertTrue(all(not path.exists() for path in image_paths))

    def test_pdf_text_local_extraction(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject('/Type'):NameObject('/Font'), NameObject('/Subtype'):NameObject('/Type1'), NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        content = DecodedStreamObject()
        content.set_data(b'BT /F1 12 Tf 50 750 Td (Python project experience) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(content)
        data = io.BytesIO()
        writer.write(data)
        self.assertIn('Python project experience', extract_resume('resume.pdf', encoded(data.getvalue()))['text'])

    def test_text_exactly_preserves_user_input(self):
        self.assertEqual(extract_resume("简历.txt", encoded("我会Python\n本人经历".encode()))["text"], "我会Python\n本人经历")

    def test_docx_local_text_extraction(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>本人项目</w:t></w:r></w:p></w:body></w:document>')
        self.assertEqual(extract_resume("简历.docx", encoded(data.getvalue()))["text"], "本人项目")

    def test_bad_files_rejected(self):
        for name, content in [("x.exe", encoded(b"hello")), ("x.txt", "bad"), ("x.txt", encoded(b"")), ("x.docx", encoded(b"not zip"))]:
            with self.subTest(name=name, content=content), self.assertRaises(ValueError):
                extract_resume(name, content)

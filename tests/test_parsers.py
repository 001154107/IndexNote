"""Tests for document parsers."""

from pathlib import Path
import pytest

from indexnote.utils.file_utils import get_parser_type, ParserType, is_supported_file


class TestFileUtils:
    """Tests for file type detection and routing."""

    def test_pdf_detected_as_docling(self):
        assert get_parser_type("test.pdf") == ParserType.DOCLING

    def test_docx_detected_as_docling(self):
        assert get_parser_type("report.docx") == ParserType.DOCLING

    def test_html_detected_as_docling(self):
        assert get_parser_type("page.html") == ParserType.DOCLING

    def test_markdown_detected_as_docling(self):
        assert get_parser_type("notes.md") == ParserType.DOCLING

    def test_txt_detected_as_plain_text(self):
        assert get_parser_type("readme.txt") == ParserType.PLAIN_TEXT

    def test_json_detected_as_plain_text(self):
        assert get_parser_type("data.json") == ParserType.PLAIN_TEXT

    def test_python_detected_as_plain_text(self):
        assert get_parser_type("script.py") == ParserType.PLAIN_TEXT

    def test_mp3_detected_as_audio(self):
        assert get_parser_type("recording.mp3") == ParserType.AUDIO

    def test_mp4_detected_as_video(self):
        assert get_parser_type("lecture.mp4") == ParserType.VIDEO

    def test_png_detected_as_image(self):
        assert get_parser_type("diagram.png") == ParserType.IMAGE

    def test_mht_detected(self):
        assert get_parser_type("page.mht") == ParserType.MHT

    def test_unsupported_extension(self):
        assert get_parser_type("file.xyz") == ParserType.UNSUPPORTED

    def test_gitkeep_ignored(self):
        assert get_parser_type(".gitkeep") == ParserType.UNSUPPORTED

    def test_is_supported_file(self):
        assert is_supported_file("test.pdf") is True
        assert is_supported_file("test.xyz") is False


class TestPlainTextParser:
    """Tests for PlainTextParser."""

    def test_parse_txt_file(self, tmp_path):
        from indexnote.parsers.docling_parser import PlainTextParser

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World! This is a test.", encoding="utf-8")

        parser = PlainTextParser()
        docs = parser.parse(test_file)

        assert len(docs) == 1
        assert "Hello, World!" in docs[0].text
        assert docs[0].metadata["file_name"] == "test.txt"
        assert docs[0].metadata["file_type"] == ".txt"

"""
Docling-based document parser.

Handles: PDF, DOCX, PPTX, XLSX, HTML, Markdown, AsciiDoc.
Uses DoclingReader (JSON export) + DoclingNodeParser for rich structural parsing.
"""

from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core.schema import Document

logger = logging.getLogger(__name__)


class DoclingParser:
    """
    Parse documents using IBM Docling via the LlamaIndex integration.

    Supports PDF (with OCR), DOCX, PPTX, XLSX, HTML, Markdown, AsciiDoc.
    """

    def __init__(self):
        from llama_index.readers.docling import DoclingReader

        self._reader = DoclingReader(export_type=DoclingReader.ExportType.MARKDOWN)
        logger.debug("DoclingParser initialized (Markdown export mode)")

    def parse(self, file_path: str | Path) -> list[Document]:
        """
        Parse a document file into LlamaIndex Document objects.

        Args:
            file_path: Path to the document file.

        Returns:
            List of Document objects with source metadata.
        """
        file_path = Path(file_path).resolve()
        logger.info("Parsing document: %s", file_path.name)

        try:
            docs = self._reader.load_data(file_path=str(file_path))

            # Enrich metadata with source file info
            for doc in docs:
                doc.metadata["source_file"] = str(file_path)
                doc.metadata["file_name"] = file_path.name
                doc.metadata["file_type"] = file_path.suffix.lower()
                # Preserve any existing metadata from Docling (page numbers, etc.)

            logger.info("Parsed %d document(s) from: %s", len(docs), file_path.name)
            return docs

        except Exception as e:
            logger.error("Failed to parse %s: %s", file_path.name, e)
            raise


class PlainTextParser:
    """
    Simple parser for plain text files (.txt, .csv, .json, .xml, .yaml, code).

    These don't need Docling — just read the file content directly.
    """

    def parse(self, file_path: str | Path) -> list[Document]:
        """
        Read a plain text file into a LlamaIndex Document.

        Args:
            file_path: Path to the text file.

        Returns:
            List containing a single Document.
        """
        file_path = Path(file_path).resolve()
        logger.info("Reading plain text: %s", file_path.name)

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")

            doc = Document(
                text=content,
                metadata={
                    "source_file": str(file_path),
                    "file_name": file_path.name,
                    "file_type": file_path.suffix.lower(),
                },
            )
            return [doc]

        except Exception as e:
            logger.error("Failed to read %s: %s", file_path.name, e)
            raise

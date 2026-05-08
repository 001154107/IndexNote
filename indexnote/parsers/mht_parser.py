"""
MHT/MHTML parser — extract HTML from archived web pages.

Handles: .mht, .mhtml files.
Extracts the HTML body from the MIME-encoded MHT archive,
then passes it to Docling for structured parsing.
"""

from __future__ import annotations

import email
import logging
import tempfile
from pathlib import Path

from llama_index.core.schema import Document

logger = logging.getLogger(__name__)


class MHTParser:
    """
    Parse MHT/MHTML archived web pages.

    MHT files are MIME-encoded archives containing HTML + embedded resources.
    This parser extracts the HTML content and processes it via Docling.
    """

    def parse(self, file_path: str | Path) -> list[Document]:
        """
        Parse an MHT file by extracting HTML and processing with Docling.

        Args:
            file_path: Path to the .mht/.mhtml file.

        Returns:
            List of Document objects.
        """
        file_path = Path(file_path).resolve()
        logger.info("Parsing MHT file: %s", file_path.name)

        try:
            # Read the MHT file as a MIME message
            raw_content = file_path.read_bytes()
            msg = email.message_from_bytes(raw_content)

            # Extract HTML content from MIME parts
            html_content = self._extract_html(msg)

            if not html_content:
                logger.warning("No HTML content found in MHT: %s", file_path.name)
                return [
                    Document(
                        text=f"[MHT file: {file_path.name} — no HTML content found]",
                        metadata={
                            "source_file": str(file_path),
                            "file_name": file_path.name,
                            "file_type": ".mht",
                        },
                    )
                ]

            # Write HTML to temp file and parse with Docling
            with tempfile.NamedTemporaryFile(
                suffix=".html", delete=False, mode="w", encoding="utf-8",
                prefix="indexnote_mht_"
            ) as tmp:
                tmp.write(html_content)
                tmp_path = Path(tmp.name)

            try:
                from indexnote.parsers.docling_parser import DoclingParser

                parser = DoclingParser()
                docs = parser.parse(tmp_path)

                # Update metadata to reference original MHT file
                for doc in docs:
                    doc.metadata["source_file"] = str(file_path)
                    doc.metadata["file_name"] = file_path.name
                    doc.metadata["file_type"] = file_path.suffix.lower()
                    doc.metadata["original_format"] = "mht"

                return docs
            finally:
                tmp_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error("Failed to parse MHT %s: %s", file_path.name, e)
            raise

    def _extract_html(self, msg: email.message.Message) -> str | None:
        """
        Extract HTML content from a MIME message.

        Walks through MIME parts looking for text/html content.
        """
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
        else:
            content_type = msg.get_content_type()
            if content_type == "text/html":
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")

        return None

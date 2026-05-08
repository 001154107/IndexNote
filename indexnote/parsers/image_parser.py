"""
Image parser — AI-powered image and diagram description.

Handles: PNG, JPG, JPEG, GIF, BMP, TIFF, SVG, WebP.
Uses vision LLM for rich descriptions of photos, diagrams, charts, handwritten notes.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from llama_index.core.schema import Document

from indexnote.config import create_vision_llm

logger = logging.getLogger(__name__)

# Map extensions to MIME types for vision LLM
_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class ImageParser:
    """
    Describe images using a vision-capable LLM.

    Generates rich text descriptions suitable for indexing and retrieval.
    """

    def __init__(self):
        self._vision_llm = None

    def _get_vision_llm(self):
        """Lazy-load vision LLM."""
        if self._vision_llm is None:
            self._vision_llm = create_vision_llm()
        return self._vision_llm

    def parse(self, file_path: str | Path) -> list[Document]:
        """
        Generate an AI description of an image.

        Args:
            file_path: Path to the image file.

        Returns:
            List containing a single Document with the image description.
        """
        file_path = Path(file_path).resolve()
        logger.info("Describing image: %s", file_path.name)

        ext = file_path.suffix.lower()
        mime_type = _MIME_MAP.get(ext, "image/png")

        try:
            image_data = file_path.read_bytes()
            b64_image = base64.b64encode(image_data).decode("utf-8")

            llm = self._get_vision_llm()

            from llama_index.core.llms import ChatMessage, ImageBlock, TextBlock

            response = llm.chat(
                messages=[
                    ChatMessage(
                        role="user",
                        blocks=[
                            ImageBlock(image=b64_image, image_mimetype=mime_type),
                            TextBlock(
                                text=(
                                    "Analyze this image in detail. Provide:\n"
                                    "1. A general description of what the image shows\n"
                                    "2. Any visible text (OCR)\n"
                                    "3. If it's a diagram/chart/graph: describe the structure, "
                                    "relationships, labels, and data\n"
                                    "4. If it's a photo: describe the scene, objects, people\n"
                                    "5. Any other notable details\n\n"
                                    "Be thorough but concise."
                                )
                            ),
                        ],
                    )
                ]
            )

            description = response.message.content

            doc = Document(
                text=description,
                metadata={
                    "source_file": str(file_path),
                    "file_name": file_path.name,
                    "file_type": ext,
                    "content_type": "image_description",
                    "mime_type": mime_type,
                },
            )

            logger.info("Described image: %s (%d chars)", file_path.name, len(description))
            return [doc]

        except Exception as e:
            logger.error("Failed to describe image %s: %s", file_path.name, e)
            # Fallback: create a minimal document
            doc = Document(
                text=f"[Image file: {file_path.name} — description unavailable]",
                metadata={
                    "source_file": str(file_path),
                    "file_name": file_path.name,
                    "file_type": ext,
                    "content_type": "image_description",
                    "error": str(e),
                },
            )
            return [doc]

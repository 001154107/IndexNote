"""
File utilities — MIME type detection and parser routing.

Maps file extensions to the appropriate parser type for ingestion.
"""

from __future__ import annotations

import mimetypes
from enum import Enum
from pathlib import Path


class ParserType(Enum):
    """Supported parser categories."""

    DOCLING = "docling"          # PDF, DOCX, PPTX, XLSX, HTML, MD, AsciiDoc
    PLAIN_TEXT = "plain_text"    # TXT, CSV, JSON, XML, YAML, LOG, code files
    AUDIO = "audio"             # MP3, WAV, M4A, OGG, FLAC
    VIDEO = "video"             # MP4, MKV, AVI, MOV, WebM
    IMAGE = "image"             # PNG, JPG, GIF, BMP, TIFF
    MHT = "mht"                 # MHT/MHTML archived web pages
    UNSUPPORTED = "unsupported"


# ---------------------------------------------------------------------------
# Extension → ParserType mapping
# ---------------------------------------------------------------------------

_DOCLING_EXTENSIONS: set[str] = {
    ".pdf", ".docx", ".pptx", ".xlsx",
    ".html", ".htm",
    ".md", ".markdown",
    ".asciidoc", ".adoc",
}

_PLAIN_TEXT_EXTENSIONS: set[str] = {
    ".txt", ".csv", ".tsv",
    ".json", ".jsonl",
    ".xml",
    ".yaml", ".yml",
    ".log",
    ".rst",
    ".ini", ".cfg", ".conf", ".toml",
    # Common code files (indexed as plain text)
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".hpp",
    ".go", ".rs", ".rb", ".php", ".sh", ".bat", ".ps1",
    ".sql", ".r", ".m", ".swift", ".kt",
    ".css", ".scss", ".less",
}

_AUDIO_EXTENSIONS: set[str] = {
    ".mp3", ".wav", ".m4a", ".ogg", ".flac",
    ".aac", ".wma", ".opus",
}

_VIDEO_EXTENSIONS: set[str] = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm",
    ".wmv", ".flv", ".m4v",
}

_IMAGE_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp",
    ".tiff", ".tif", ".svg", ".webp", ".ico",
}

_MHT_EXTENSIONS: set[str] = {
    ".mht", ".mhtml",
}

# Files/dirs to always ignore
IGNORED_PATTERNS: set[str] = {
    ".gitkeep", ".DS_Store", "Thumbs.db", "desktop.ini",
}


def get_parser_type(file_path: str | Path) -> ParserType:
    """
    Determine the appropriate parser type for a given file.

    Args:
        file_path: Path to the file.

    Returns:
        ParserType enum indicating which parser to use.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if path.name in IGNORED_PATTERNS:
        return ParserType.UNSUPPORTED

    if ext in _DOCLING_EXTENSIONS:
        return ParserType.DOCLING
    elif ext in _MHT_EXTENSIONS:
        return ParserType.MHT
    elif ext in _PLAIN_TEXT_EXTENSIONS:
        return ParserType.PLAIN_TEXT
    elif ext in _AUDIO_EXTENSIONS:
        return ParserType.AUDIO
    elif ext in _VIDEO_EXTENSIONS:
        return ParserType.VIDEO
    elif ext in _IMAGE_EXTENSIONS:
        return ParserType.IMAGE
    else:
        return ParserType.UNSUPPORTED


def get_supported_extensions() -> set[str]:
    """Return all supported file extensions."""
    return (
        _DOCLING_EXTENSIONS
        | _PLAIN_TEXT_EXTENSIONS
        | _AUDIO_EXTENSIONS
        | _VIDEO_EXTENSIONS
        | _IMAGE_EXTENSIONS
        | _MHT_EXTENSIONS
    )


def is_supported_file(file_path: str | Path) -> bool:
    """Check if a file is supported for ingestion."""
    return get_parser_type(file_path) != ParserType.UNSUPPORTED

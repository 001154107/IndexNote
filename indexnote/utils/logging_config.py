"""
Logging configuration for IndexNote.

Provides structured, colourful logging via Rich.
"""

from __future__ import annotations

import logging
import sys

from rich.logging import RichHandler


def setup_logging(level: str = "INFO") -> None:
    """
    Configure root logger with Rich handler.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR).
    """
    # Ensure log file exists and is writable
    log_file = "indexnote.log"
    
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8")
        ],
        force=True,
    )

    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("kuzu").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)

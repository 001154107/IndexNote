"""
Web Scraper Module

Downloads URLs, determines their content type (HTML vs PDF),
and saves them to the web_downloads directory.
"""

from __future__ import annotations

import logging
import mimetypes
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests

from indexnote.config import get_settings

logger = logging.getLogger(__name__)


class WebScraper:
    """Handles downloading and saving web content."""

    def __init__(self, download_dir: Path | str | None = None):
        """Initialize the web scraper."""
        if download_dir is None:
            settings = get_settings()
            self._download_dir = settings.source_notes_dir / "web_downloads"
        else:
            self._download_dir = Path(download_dir)
            
        self._download_dir.mkdir(parents=True, exist_ok=True)
        
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "IndexNote/1.0 (Local NotebookLM Clone; +https://github.com/indexnote/indexnote)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.8",
        })

    def download_url(self, url: str) -> Path | None:
        """
        Download content from a URL and save it with an appropriate extension.

        Args:
            url: The URL to download.

        Returns:
            The Path to the saved file, or None if download failed.
        """
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.warning("Invalid URL: %s", url)
                return None

            logger.info("Downloading URL: %s", url)
            response = self._session.get(url, timeout=15, stream=True)
            response.raise_for_status()

            # Determine content type and appropriate extension
            content_type = response.headers.get("Content-Type", "").lower()
            
            ext = ".html" # Default to html
            if "application/pdf" in content_type:
                ext = ".pdf"
            elif "text/plain" in content_type:
                ext = ".txt"
            elif "text/markdown" in content_type:
                ext = ".md"
            elif "application/json" in content_type:
                ext = ".json"
            else:
                # Try to guess from url if content-type is ambiguous
                url_path = parsed.path.lower()
                if url_path.endswith(".pdf"):
                    ext = ".pdf"
                elif url_path.endswith(".txt"):
                    ext = ".txt"
                elif url_path.endswith(".md"):
                    ext = ".md"

            # Create a safe filename from the URL path + random UUID to prevent collisions
            base_name = parsed.path.strip("/").split("/")[-1]
            if not base_name or len(base_name) > 50:
                base_name = parsed.netloc.replace(".", "_")
            
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)
            filename = f"{safe_name}_{uuid.uuid4().hex[:8]}{ext}"
            
            file_path = self._download_dir / filename
            
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            logger.info("Successfully downloaded to: %s", file_path)
            return file_path

        except requests.RequestException as e:
            logger.error("Failed to download URL %s: %s", url, e)
            return None

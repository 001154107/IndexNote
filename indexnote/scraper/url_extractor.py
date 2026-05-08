"""
URL Extractor Module

Extracts valid HTTP/HTTPS URLs from text chunks.
"""

from __future__ import annotations

import re
from typing import Set

class URLExtractor:
    """Extracts URLs from text."""

    # Robust regex for HTTP/HTTPS URLs
    _URL_PATTERN = re.compile(
        r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )

    @classmethod
    def extract_urls(cls, text: str) -> Set[str]:
        """
        Extract all unique HTTP/HTTPS URLs from the provided text.

        Args:
            text: The text to scan.

        Returns:
            A set of unique URLs found in the text.
        """
        if not text:
            return set()

        # Find all raw matches
        matches = cls._URL_PATTERN.findall(text)
        
        valid_urls = set()
        for match in matches:
            # Clean trailing punctuation that might be caught in the regex
            # (e.g. if a URL is at the end of a sentence like "http://example.com.")
            clean_url = match.rstrip(".,;:'\"!?)]}")
            valid_urls.add(clean_url)

        return valid_urls

"""Tests for retrieval and citation engine."""

import pytest

from indexnote.retrieval.citation_engine import CitationEngine, Citation


class TestCitationEngine:
    """Tests for citation extraction and formatting."""

    def test_format_citations_display(self):
        engine = CitationEngine()
        citations = [
            Citation(
                index=1,
                file_path="/notes/paper.pdf",
                file_name="paper.pdf",
                content_type=".pdf",
                score=0.89,
                chunk_preview="Neural networks are...",
            ),
            Citation(
                index=2,
                file_path="/notes/lecture.md",
                file_name="lecture.md",
                content_type=".md",
                score=0.75,
                chunk_preview="Machine learning involves...",
            ),
        ]

        display = engine.format_citations_display(citations)
        assert "Sources:" in display
        assert "[1]" in display
        assert "[2]" in display
        assert "paper.pdf" in display
        assert "0.89" in display

    def test_empty_citations(self):
        engine = CitationEngine()
        display = engine.format_citations_display([])
        assert display == ""

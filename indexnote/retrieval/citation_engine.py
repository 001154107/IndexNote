"""
Citation Engine — formats source citations from retrieved nodes.

Extracts source file metadata from retrieved nodes and formats
them as numbered citations for LLM response synthesis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from llama_index.core.schema import NodeWithScore

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """A single source citation."""

    index: int
    file_path: str
    file_name: str
    content_type: str
    score: float
    chunk_preview: str  # First ~100 chars of the chunk


class CitationEngine:
    """
    Extracts and formats source citations from retrieved nodes.

    Provides citations in both human-readable format (for display)
    and structured format (for LLM prompt context).
    """

    def __init__(self, source_notes_dir: str | Path | None = None):
        """
        Initialize the citation engine.

        Args:
            source_notes_dir: Base directory for making relative paths.
        """
        self._base_dir = Path(source_notes_dir) if source_notes_dir else None

    def extract_citations(self, nodes: list[NodeWithScore]) -> list[Citation]:
        """
        Extract citation metadata from retrieved nodes.

        Args:
            nodes: List of retrieved NodeWithScore objects.

        Returns:
            List of Citation objects, deduplicated by source file.
        """
        citations = []
        seen_files: dict[str, int] = {}  # file_path → citation index

        for node in nodes:
            metadata = node.node.metadata or {}
            source_file = metadata.get("source_file", "unknown")
            file_name = metadata.get("file_name", Path(source_file).name if source_file != "unknown" else "unknown")
            content_type = metadata.get("content_type", metadata.get("file_type", "text"))
            score = node.score or 0.0
            text = node.node.get_content()
            chunk_preview = text[:150].replace("\n", " ").strip() + ("..." if len(text) > 150 else "")

            # Deduplicate by source file (keep first/highest scored)
            if source_file in seen_files:
                continue

            idx = len(citations) + 1
            seen_files[source_file] = idx

            citations.append(
                Citation(
                    index=idx,
                    file_path=source_file,
                    file_name=file_name,
                    content_type=content_type,
                    score=round(score, 3),
                    chunk_preview=chunk_preview,
                )
            )

        return citations

    def format_citations_display(self, citations: list[Citation]) -> str:
        """
        Format citations for display to the user.

        Returns a human-readable string like:
            Sources:
              [1] notes/paper.pdf (score: 0.89)
              [2] notes/lecture.md (score: 0.85)
        """
        if not citations:
            return ""

        lines = ["", "Sources:"]
        for c in citations:
            # Make path relative if possible
            display_path = c.file_path
            if self._base_dir:
                try:
                    display_path = str(Path(c.file_path).relative_to(self._base_dir.parent))
                except ValueError:
                    pass

            lines.append(f"  [{c.index}] {display_path} (score: {c.score})")

        return "\n".join(lines)

    def format_context_for_llm(
        self, nodes: list[NodeWithScore], citations: list[Citation]
    ) -> str:
        """
        Format retrieved context with citation markers for the LLM prompt.

        Returns context text where each chunk is annotated with its source number.
        """
        if not nodes:
            return "No relevant context found."

        # Build a map of source_file → citation index
        file_to_idx: dict[str, int] = {}
        for c in citations:
            file_to_idx[c.file_path] = c.index

        parts = []
        for node in nodes:
            metadata = node.node.metadata or {}
            source_file = metadata.get("source_file", "unknown")
            citation_idx = file_to_idx.get(source_file, "?")
            text = node.node.get_content()

            parts.append(f"[Source {citation_idx}]:\n{text}\n")

        return "\n---\n".join(parts)

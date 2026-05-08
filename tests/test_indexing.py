"""Tests for indexing pipeline."""

import pytest

from indexnote.config import get_settings


class TestConfig:
    """Tests for configuration loading."""

    def test_default_settings(self):
        settings = get_settings()
        assert settings.llm_provider in ("ollama", "gemini")
        assert settings.chunk_size > 0
        assert settings.chunk_overlap >= 0
        assert settings.kg_max_paths_per_chunk > 0

    def test_paths_are_path_objects(self):
        from pathlib import Path
        settings = get_settings()
        assert isinstance(settings.source_notes_dir, Path)
        assert isinstance(settings.data_dir, Path)

    def test_derived_paths(self):
        settings = get_settings()
        assert "chroma_db" in str(settings.chroma_db_path)
        assert "kuzu_db" in str(settings.kuzu_db_path)
        assert "file_index.db" in str(settings.file_index_db_path)

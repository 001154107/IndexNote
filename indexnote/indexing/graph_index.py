"""
Graph Index — PropertyGraphIndex backed by Kuzu.

Extracts entity-relation-entity triples from documents and stores
them in the Kuzu graph database for relationship-aware retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core import PropertyGraphIndex
from llama_index.core.schema import Document

from indexnote.config import Settings, get_settings, create_llm, create_embed_model

logger = logging.getLogger(__name__)


class GraphIndex:
    """
    Manages a LlamaIndex PropertyGraphIndex with Kuzu graph store.

    Handles creation, loading, and incremental document insertion.
    """

    def __init__(self, graph_store, settings: Settings | None = None):
        """
        Initialize the graph index manager.

        Args:
            graph_store: KuzuGraphStore instance.
            settings: Configuration settings.
        """
        self._graph_store = graph_store
        self._settings = settings or get_settings()
        self._llm = create_llm(self._settings)
        self._embed_model = create_embed_model(self._settings)
        self._index: PropertyGraphIndex | None = None

    def _get_kg_extractors(self):
        """Create knowledge graph extractors."""
        from llama_index.core.indices.property_graph import (
            SimpleLLMPathExtractor,
            ImplicitPathExtractor,
        )

        return [
            SimpleLLMPathExtractor(
                llm=self._llm,
                max_paths_per_chunk=self._settings.kg_max_paths_per_chunk,
                num_workers=1,
            ),
            ImplicitPathExtractor(),
        ]

    def build_from_documents(self, documents: list[Document]) -> PropertyGraphIndex:
        """
        Build a new PropertyGraphIndex from documents.

        Args:
            documents: List of LlamaIndex Document objects.

        Returns:
            The created PropertyGraphIndex.
        """
        logger.info("Building graph index from %d documents...", len(documents))

        self._index = PropertyGraphIndex.from_documents(
            documents,
            graph_store=self._graph_store,
            kg_extractors=self._get_kg_extractors(),
            llm=self._llm,
            embed_model=self._embed_model,
            show_progress=True,
        )

        logger.info("Graph index built successfully")
        return self._index

    def insert_documents(self, documents: list[Document]) -> None:
        """
        Insert additional documents into an existing graph index.

        Args:
            documents: New documents to add.
        """
        if self._index is None:
            self.build_from_documents(documents)
            return

        logger.info("Inserting %d documents into graph index...", len(documents))
        for doc in documents:
            self._index.insert(doc)
        logger.info("Documents inserted into graph index")

    def get_index(self) -> PropertyGraphIndex | None:
        """Return the current PropertyGraphIndex, if built."""
        return self._index

    def load_existing(self) -> PropertyGraphIndex:
        """
        Load an existing PropertyGraphIndex from the graph store.

        Used when restarting and the Kuzu DB already has data.
        """
        logger.info("Loading existing graph index from store...")
        self._index = PropertyGraphIndex.from_existing(
            property_graph_store=self._graph_store,
            llm=self._llm,
            embed_model=self._embed_model,
        )
        logger.info("Graph index loaded from existing store")
        return self._index

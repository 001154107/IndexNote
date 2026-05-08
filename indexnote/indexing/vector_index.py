"""
Vector Index — VectorStoreIndex backed by ChromaDB.

Stores document embeddings for semantic similarity retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.schema import Document

from indexnote.config import Settings, get_settings, create_llm, create_embed_model

logger = logging.getLogger(__name__)


class VectorIndex:
    """
    Manages a LlamaIndex VectorStoreIndex with ChromaDB backend.

    Handles creation, loading, and incremental document insertion.
    """

    def __init__(self, vector_store, settings: Settings | None = None):
        """
        Initialize the vector index manager.

        Args:
            vector_store: ChromaVectorStore instance.
            settings: Configuration settings.
        """
        self._vector_store = vector_store
        self._settings = settings or get_settings()
        self._embed_model = create_embed_model(self._settings)
        self._index: VectorStoreIndex | None = None

    def build_from_documents(self, documents: list[Document]) -> VectorStoreIndex:
        """
        Build a new VectorStoreIndex from documents.

        Args:
            documents: List of LlamaIndex Document objects.

        Returns:
            The created VectorStoreIndex.
        """
        logger.info("Building vector index from %d documents...", len(documents))

        storage_context = StorageContext.from_defaults(vector_store=self._vector_store)

        self._index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            embed_model=self._embed_model,
            show_progress=True,
        )

        logger.info("Vector index built successfully")
        return self._index

    def insert_documents(self, documents: list[Document]) -> None:
        """
        Insert additional documents into an existing vector index.

        Args:
            documents: New documents to add.
        """
        if self._index is None:
            self.build_from_documents(documents)
            return

        logger.info("Inserting %d documents into vector index...", len(documents))
        for doc in documents:
            self._index.insert(doc)
        logger.info("Documents inserted into vector index")

    def get_index(self) -> VectorStoreIndex | None:
        """Return the current VectorStoreIndex, if built."""
        return self._index

    def load_existing(self) -> VectorStoreIndex:
        """
        Load an existing VectorStoreIndex from the ChromaDB store.

        Used when restarting and ChromaDB already has data.
        """
        logger.info("Loading existing vector index from store...")
        self._index = VectorStoreIndex.from_vector_store(
            vector_store=self._vector_store,
            embed_model=self._embed_model,
        )
        logger.info("Vector index loaded from existing store")
        return self._index

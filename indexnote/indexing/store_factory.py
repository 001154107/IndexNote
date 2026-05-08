"""
Store Factory — Initialize Kuzu (graph) and ChromaDB (vector) stores.

Provides ready-to-use LlamaIndex-compatible store instances.
"""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb
import kuzu
from llama_index.core import StorageContext
from llama_index.graph_stores.kuzu import KuzuGraphStore
from llama_index.vector_stores.chroma import ChromaVectorStore

from indexnote.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Default ChromaDB collection name
_CHROMA_COLLECTION = "indexnote_vectors"


def create_kuzu_store(settings: Settings | None = None) -> tuple[kuzu.Database, KuzuGraphStore]:
    """
    Initialize Kuzu embedded graph database and LlamaIndex graph store.

    Returns:
        Tuple of (kuzu.Database, KuzuGraphStore)
    """
    if settings is None:
        settings = get_settings()

    db_path = settings.kuzu_db_path
    # Ensure parent directory exists, but let Kuzu manage its own db directory
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # If the db dir exists but is empty (no Kuzu files), remove it so Kuzu can init
    if db_path.exists() and db_path.is_dir():
        contents = list(db_path.iterdir())
        if not contents:
            db_path.rmdir()

    logger.info("Initializing Kuzu graph database at: %s", db_path)
    db = kuzu.Database(str(db_path))
    graph_store = KuzuGraphStore(db)

    return db, graph_store


def create_chroma_store(settings: Settings | None = None) -> tuple[chromadb.ClientAPI, ChromaVectorStore]:
    """
    Initialize ChromaDB persistent client and LlamaIndex vector store.

    Returns:
        Tuple of (chromadb.ClientAPI, ChromaVectorStore)
    """
    if settings is None:
        settings = get_settings()

    db_path = settings.chroma_db_path
    db_path.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing ChromaDB at: %s", db_path)
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_or_create_collection(_CHROMA_COLLECTION)
    vector_store = ChromaVectorStore(chroma_collection=collection)

    return client, vector_store


def create_storage_context(
    vector_store: ChromaVectorStore | None = None,
    graph_store: KuzuGraphStore | None = None,
    settings: Settings | None = None,
) -> StorageContext:
    """
    Create a LlamaIndex StorageContext combining vector and graph stores.

    If stores are not provided, they will be created from settings.
    """
    if settings is None:
        settings = get_settings()

    if vector_store is None:
        _, vector_store = create_chroma_store(settings)

    if graph_store is None:
        _, graph_store = create_kuzu_store(settings)

    return StorageContext.from_defaults(
        vector_store=vector_store,
        graph_store=graph_store,
    )

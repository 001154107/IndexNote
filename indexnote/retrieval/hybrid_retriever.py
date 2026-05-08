"""
Hybrid Retriever — combines Vector and Graph retrieval strategies.

Merges results from ChromaDB vector similarity and Kuzu graph traversal
for comprehensive context retrieval.
"""

from __future__ import annotations

import logging
from typing import Optional

from llama_index.core.schema import NodeWithScore, QueryBundle

from indexnote.config import Settings, get_settings, create_llm, create_embed_model
from indexnote.indexing.hybrid_index import HybridIndexManager

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Combines vector and graph retrieval for hybrid RAG.

    Uses PropertyGraphIndex sub-retrievers (VectorContextRetriever + LLMSynonymRetriever)
    plus a standard VectorStoreIndex retriever.
    """

    def __init__(
        self,
        index_manager: HybridIndexManager,
        similarity_top_k: int = 5,
        settings: Settings | None = None,
    ):
        """
        Initialize the hybrid retriever.

        Args:
            index_manager: The HybridIndexManager holding both indexes.
            similarity_top_k: Number of top results for vector retrieval.
            settings: Configuration settings.
        """
        self._index_manager = index_manager
        self._similarity_top_k = similarity_top_k
        self._settings = settings or get_settings()
        self._llm = create_llm(self._settings)
        self._embed_model = create_embed_model(self._settings)

    def retrieve(self, query: str) -> list[NodeWithScore]:
        """
        Retrieve relevant nodes from both vector and graph stores.

        Args:
            query: User query string.

        Returns:
            List of NodeWithScore objects, deduplicated and sorted by score.
        """
        all_nodes: list[NodeWithScore] = []

        # 1. Vector retrieval (from ChromaDB)
        vector_index = self._index_manager.vector_index.get_index()
        if vector_index is not None:
            try:
                vector_retriever = vector_index.as_retriever(
                    similarity_top_k=self._similarity_top_k,
                )
                vector_nodes = vector_retriever.retrieve(query)
                logger.debug("Vector retrieval returned %d nodes", len(vector_nodes))
                all_nodes.extend(vector_nodes)
            except Exception as e:
                logger.warning("Vector retrieval failed: %s", e)

        # 2. Graph retrieval (from Kuzu PropertyGraphIndex)
        graph_index = self._index_manager.graph_index.get_index()
        if graph_index is not None:
            try:
                from llama_index.core.indices.property_graph import (
                    VectorContextRetriever,
                    LLMSynonymRetriever,
                )

                sub_retrievers = [
                    VectorContextRetriever(
                        graph_index.property_graph_store,
                        embed_model=self._embed_model,
                        similarity_top_k=self._similarity_top_k,
                    ),
                    LLMSynonymRetriever(
                        graph_index.property_graph_store,
                        llm=self._llm,
                    ),
                ]
                graph_retriever = graph_index.as_retriever(
                    sub_retrievers=sub_retrievers,
                )
                graph_nodes = graph_retriever.retrieve(query)
                logger.debug("Graph retrieval returned %d nodes", len(graph_nodes))
                all_nodes.extend(graph_nodes)
            except Exception as e:
                logger.warning("Graph retrieval failed: %s", e)

        # 3. Deduplicate by node ID, keeping the highest-scored version
        seen: dict[str, NodeWithScore] = {}
        for node in all_nodes:
            node_id = node.node.node_id
            if node_id not in seen or (node.score or 0) > (seen[node_id].score or 0):
                seen[node_id] = node

        # 4. Sort by score descending
        results = sorted(seen.values(), key=lambda n: n.score or 0, reverse=True)
        logger.info("Hybrid retrieval: %d unique nodes from query", len(results))

        return results

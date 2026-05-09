"""
Query Engine — main entry point for querying IndexNote.

Combines hybrid retrieval, citation extraction, and LLM response synthesis
to answer user queries with source citations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from indexnote.config import Settings, get_settings, create_llm
from indexnote.indexing.hybrid_index import HybridIndexManager
from indexnote.retrieval.hybrid_retriever import HybridRetriever
from indexnote.retrieval.citation_engine import CitationEngine, Citation

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are IndexNote, a helpful research assistant. 
Answer the user's question based ONLY on the provided source context below.
If the context doesn't contain enough information, say so honestly.
Reference sources by their [Source N] markers when citing specific information.
Be concise, accurate, and well-structured in your response."""


@dataclass
class QueryResponse:
    """Structured response from the query engine."""

    answer: str
    citations: list[Citation]
    citations_display: str
    num_sources: int


class QueryEngine:
    """
    Main query engine combining hybrid retrieval with cited responses.

    Pipeline:
    1. Hybrid retrieve (vector + graph)
    2. Extract source citations
    3. Build LLM prompt with context + citations
    4. Synthesize response
    5. Return answer + formatted citations
    """

    def __init__(
        self,
        index_manager: HybridIndexManager,
        settings: Settings | None = None,
    ):
        """
        Initialize the query engine.

        Args:
            index_manager: HybridIndexManager with populated indexes.
            settings: Configuration settings.
        """
        self._settings = settings or get_settings()
        self._index_manager = index_manager
        self._retriever = HybridRetriever(
            index_manager=index_manager,
            settings=self._settings,
        )
        self._citation_engine = CitationEngine(
            source_notes_dir=self._settings.source_notes_dir,
        )
        self._llm = create_llm(self._settings)

        self._chat_history = []
        self._history_window = 5 # Number of previous turns to keep in context window

    def get_context(self, user_query: str) -> tuple[str, list[Citation]]:
        """Retrieve relevant context and formatted citations for a query."""
        nodes = self._retriever.retrieve(user_query)
        if not nodes:
            return "", []
        
        citations = self._citation_engine.extract_citations(nodes)
        context_str = self._citation_engine.format_context_for_llm(nodes, citations)
        return context_str, citations

    def query(self, user_query: str) -> QueryResponse:
        """
        Answer a user query with source citations, maintaining conversation history.

        Args:
            user_query: The user's question.

        Returns:
            QueryResponse with answer, citations, and display string.
        """
        logger.info("Processing query: %s", user_query[:80])

        # 1 & 2. Retrieve relevant context and citations
        context_str, citations = self.get_context(user_query)

        if not context_str:
            return QueryResponse(
                answer="I couldn't find any relevant information in your indexed notes. "
                       "Make sure you have files in the source_notes/ directory and they've been indexed.",
                citations=[],
                citations_display="",
                num_sources=0,
            )
        citations_display = self._citation_engine.format_citations_display(citations)
        context = self._citation_engine.format_context_for_llm(nodes, citations)

        # 3. Build prompt and get LLM response
        from llama_index.core.llms import ChatMessage

        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
        ]
        
        # Inject short-term chat history
        for turn in self._chat_history[-self._history_window:]:
            messages.append(ChatMessage(role="user", content=turn["user"]))
            messages.append(ChatMessage(role="assistant", content=turn["assistant"]))

        # Current question + Context
        messages.append(
            ChatMessage(
                role="user",
                content=(
                    f"Context from indexed documents:\n\n{context}\n\n"
                    f"---\n\nUser question: {user_query}"
                ),
            )
        )

        response = self._llm.chat(messages)
        answer = response.message.content

        # 4. Save to short-term memory
        self._chat_history.append({"user": user_query, "assistant": answer})
        
        # 5. Append to long-term memory (Chat_History.md)
        self._log_to_chat_history(user_query, answer)

        logger.info("Query answered with %d sources", len(citations))

        return QueryResponse(
            answer=answer,
            citations=citations,
            citations_display=citations_display,
            num_sources=len(citations),
        )

    def _log_to_chat_history(self, query: str, answer: str) -> None:
        """Append the QA pair to source_notes/Chat_History.md so it gets indexed."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history_file = self._settings.source_notes_dir / "Chat_History.md"
        
        # Format the entry cleanly without terminal output
        entry = (
            f"\n## Conversation Turn - {timestamp}\n\n"
            f"**User Question:**\n{query}\n\n"
            f"**IndexNote Response:**\n{answer}\n\n"
            f"---\n"
        )
        
        try:
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.error("Failed to append to Chat_History.md: %s", e)

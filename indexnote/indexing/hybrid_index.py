"""
Hybrid Index Manager — coordinates Graph and Vector indexes.

Provides a unified interface for indexing documents into both stores
and managing document lifecycle (insert, delete, reindex).
"""

from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core.schema import Document

from indexnote.config import Settings, get_settings
from indexnote.indexing.graph_index import GraphIndex
from indexnote.indexing.vector_index import VectorIndex
from indexnote.indexing.store_factory import create_kuzu_store, create_chroma_store
from indexnote.parsers.docling_parser import DoclingParser, PlainTextParser
from indexnote.parsers.audio_parser import AudioParser
from indexnote.parsers.video_parser import VideoParser
from indexnote.parsers.image_parser import ImageParser
from indexnote.parsers.mht_parser import MHTParser
from indexnote.utils.file_utils import ParserType, get_parser_type

logger = logging.getLogger(__name__)


class HybridIndexManager:
    """
    Unified manager for both Graph (Kuzu) and Vector (ChromaDB) indexes.

    Coordinates document parsing, indexing into both stores,
    and document lifecycle management.
    """

    def __init__(self, settings: Settings | None = None):
        """
        Initialize the hybrid index manager.

        Creates connections to both Kuzu and ChromaDB stores.
        """
        self._settings = settings or get_settings()

        # Initialize stores
        self._kuzu_db, self._kuzu_store = create_kuzu_store(self._settings)
        self._chroma_client, self._chroma_store = create_chroma_store(self._settings)

        # Initialize index managers
        self._graph_index = GraphIndex(self._kuzu_store, self._settings)
        self._vector_index = VectorIndex(self._chroma_store, self._settings)

        # Lazy-init parsers
        self._parsers: dict[ParserType, object] = {}

        logger.info("HybridIndexManager initialized")

    def _get_parser(self, parser_type: ParserType):
        """Get or create a parser instance for the given type."""
        if parser_type not in self._parsers:
            if parser_type == ParserType.DOCLING:
                self._parsers[parser_type] = DoclingParser()
            elif parser_type == ParserType.PLAIN_TEXT:
                self._parsers[parser_type] = PlainTextParser()
            elif parser_type == ParserType.AUDIO:
                self._parsers[parser_type] = AudioParser()
            elif parser_type == ParserType.VIDEO:
                self._parsers[parser_type] = VideoParser()
            elif parser_type == ParserType.IMAGE:
                self._parsers[parser_type] = ImageParser()
            elif parser_type == ParserType.MHT:
                self._parsers[parser_type] = MHTParser()
            else:
                raise ValueError(f"No parser for type: {parser_type}")
        return self._parsers[parser_type]

    def parse_file(self, file_path: str | Path) -> list[Document]:
        """
        Parse a file using the appropriate parser.

        Args:
            file_path: Path to the file to parse.

        Returns:
            List of Document objects.

        Raises:
            ValueError: If file type is unsupported.
        """
        file_path = Path(file_path).resolve()
        parser_type = get_parser_type(file_path)

        if parser_type == ParserType.UNSUPPORTED:
            raise ValueError(f"Unsupported file type: {file_path.suffix} ({file_path.name})")

        parser = self._get_parser(parser_type)
        return parser.parse(file_path)

    def index_file(self, file_path: str | Path) -> int:
        """
        Parse and index a single file into both Graph and Vector stores.

        Args:
            file_path: Path to the file to index.

        Returns:
            Number of document chunks indexed.
        """
        file_path = Path(file_path).resolve()
        logger.info("Indexing file: %s", file_path.name)

        # 1. Parse the file
        documents = self.parse_file(file_path)

        if not documents:
            logger.warning("No content extracted from: %s", file_path.name)
            return 0

        # Extract URLs for discovery
        try:
            from indexnote.scraper.url_extractor import URLExtractor
            found_urls = set()
            for doc in documents:
                found_urls.update(URLExtractor.extract_urls(doc.text))
            
            if found_urls:
                self._append_suggested_urls(found_urls)
        except Exception as e:
            logger.error("Failed to extract URLs during indexing: %s", e)

        # 2. Index into both stores
        self._graph_index.insert_documents(documents)
        self._vector_index.insert_documents(documents)

        logger.info("Indexed %d chunk(s) from: %s", len(documents), file_path.name)
        return len(documents)

    def _append_suggested_urls(self, urls: set[str]) -> None:
        """Append newly discovered URLs to SUGGESTED_URLS.md."""
        suggested_path = self._settings.source_notes_dir / "SUGGESTED_URLS.md"
        
        existing_text = ""
        if suggested_path.exists():
            existing_text = suggested_path.read_text(encoding="utf-8", errors="replace")
            
        new_urls = []
        for url in urls:
            if url not in existing_text:
                new_urls.append(url)
                
        if new_urls:
            with open(suggested_path, "a", encoding="utf-8") as f:
                if not existing_text.endswith("\n") and existing_text:
                    f.write("\n")
                for url in sorted(new_urls):
                    f.write(f"- [ ] {url}\n")
            logger.info("Discovered and appended %d new URLs to SUGGESTED_URLS.md", len(new_urls))

    def index_files(self, file_paths: list[str | Path]) -> dict[str, int]:
        """
        Parse and index multiple files.

        Args:
            file_paths: List of file paths to index.

        Returns:
            Dict mapping file name → number of chunks indexed.
        """
        results = {}
        for fp in file_paths:
            try:
                count = self.index_file(fp)
                results[Path(fp).name] = count
            except Exception as e:
                logger.error("Failed to index %s: %s", Path(fp).name, e)
                results[Path(fp).name] = -1
        return results

    def load_existing_indexes(self) -> None:
        """Load existing indexes from persistent stores."""
        try:
            self._graph_index.load_existing()
            logger.info("Loaded existing graph index")
        except Exception as e:
            logger.debug("No existing graph index to load: %s", e)

        try:
            self._vector_index.load_existing()
            logger.info("Loaded existing vector index")
        except Exception as e:
            logger.debug("No existing vector index to load: %s", e)

    @property
    def graph_index(self) -> GraphIndex:
        """Access the graph index manager."""
        return self._graph_index

    @property
    def vector_index(self) -> VectorIndex:
        """Access the vector index manager."""
        return self._vector_index

    @property
    def graph_store(self):
        """Access the underlying Kuzu graph store."""
        return self._kuzu_store

    @property
    def vector_store(self):
        """Access the underlying ChromaDB vector store."""
        return self._chroma_store

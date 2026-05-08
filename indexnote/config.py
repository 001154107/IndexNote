"""
IndexNote Configuration — loads settings from .env and provides LLM/embedding factories.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from project root (two levels up from this file)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass
class Settings:
    """Central configuration for IndexNote, populated from environment variables."""

    # --- LLM Provider --------------------------------------------------------
    llm_provider: Literal["ollama", "gemini"] = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "ollama").lower()
    )

    # --- Ollama --------------------------------------------------------------
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.1")
    )
    ollama_embed_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    )
    ollama_vision_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_VISION_MODEL", "llava")
    )

    # --- Gemini --------------------------------------------------------------
    google_api_key: str = field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY", "")
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    )
    gemini_embed_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_EMBED_MODEL", "models/text-embedding-004")
    )

    # --- Paths ---------------------------------------------------------------
    source_notes_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / os.getenv("SOURCE_NOTES_DIR", "./source_notes")
    )
    data_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / os.getenv("DATA_DIR", "./data")
    )

    # --- Indexing ------------------------------------------------------------
    chunk_size: int = field(
        default_factory=lambda: int(os.getenv("CHUNK_SIZE", "1024"))
    )
    chunk_overlap: int = field(
        default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "128"))
    )
    kg_max_paths_per_chunk: int = field(
        default_factory=lambda: int(os.getenv("KG_MAX_PATHS_PER_CHUNK", "10"))
    )

    # --- File Watcher --------------------------------------------------------
    auto_reindex: bool = field(
        default_factory=lambda: os.getenv("AUTO_REINDEX", "false").lower() == "true"
    )
    watcher_debounce_seconds: float = field(
        default_factory=lambda: float(os.getenv("WATCHER_DEBOUNCE_SECONDS", "2.0"))
    )

    # --- Audio/Video ---------------------------------------------------------
    whisper_model_size: str = field(
        default_factory=lambda: os.getenv("WHISPER_MODEL_SIZE", "base")
    )

    # --- Logging -------------------------------------------------------------
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )

    # --- Derived paths -------------------------------------------------------
    @property
    def chroma_db_path(self) -> Path:
        return self.data_dir / "chroma_db"

    @property
    def kuzu_db_path(self) -> Path:
        return self.data_dir / "kuzu_db"

    @property
    def file_index_db_path(self) -> Path:
        return self.data_dir / "file_index.db"


def get_settings() -> Settings:
    """Create a Settings instance from current environment."""
    return Settings()


# ---------------------------------------------------------------------------
# LLM & Embedding Factories
# ---------------------------------------------------------------------------

def create_llm(settings: Settings | None = None):
    """Create the appropriate LLM instance based on provider config."""
    if settings is None:
        settings = get_settings()

    if settings.llm_provider == "ollama":
        from llama_index.llms.ollama import Ollama

        return Ollama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            request_timeout=120.0,
        )
    elif settings.llm_provider == "gemini":
        from llama_index.llms.google_genai import GoogleGenAI

        return GoogleGenAI(
            model=settings.gemini_model,
            api_key=settings.google_api_key,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def create_embed_model(settings: Settings | None = None):
    """Create the appropriate embedding model based on provider config."""
    if settings is None:
        settings = get_settings()

    if settings.llm_provider == "ollama":
        from llama_index.embeddings.ollama import OllamaEmbedding

        return OllamaEmbedding(
            model_name=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
        )
    elif settings.llm_provider == "gemini":
        from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

        return GoogleGenAIEmbedding(
            model_name=settings.gemini_embed_model,
            api_key=settings.google_api_key,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def create_vision_llm(settings: Settings | None = None):
    """Create a vision-capable LLM for image/video description."""
    if settings is None:
        settings = get_settings()

    if settings.llm_provider == "ollama":
        from llama_index.llms.ollama import Ollama

        return Ollama(
            model=settings.ollama_vision_model,
            base_url=settings.ollama_base_url,
            request_timeout=180.0,
        )
    elif settings.llm_provider == "gemini":
        # Gemini models natively support vision
        return create_llm(settings)
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")

#!/usr/bin/env python3
"""
setup_env.py — Initialize IndexNote environment.

Creates directory structure, initializes databases, and verifies LLM connectivity.

Usage:
    python scripts/setup_env.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from indexnote.config import Settings, get_settings, create_llm, create_embed_model

console = Console()


def setup_directories(settings: Settings) -> None:
    """Create all required directories."""
    dirs = [
        settings.source_notes_dir,
        settings.data_dir,
        settings.chroma_db_path,
        settings.kuzu_db_path,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        console.print(f"  ✅ {d}")


def init_stores(settings: Settings) -> None:
    """Initialize Kuzu and ChromaDB stores."""
    from indexnote.indexing.store_factory import create_kuzu_store, create_chroma_store

    console.print("\n[bold]Initializing stores...[/bold]")

    _, graph_store = create_kuzu_store(settings)
    console.print("  ✅ Kuzu graph store initialized")

    _, vector_store = create_chroma_store(settings)
    console.print("  ✅ ChromaDB vector store initialized")


def verify_llm(settings: Settings) -> bool:
    """Test LLM connectivity."""
    console.print(f"\n[bold]Testing LLM connection ({settings.llm_provider})...[/bold]")

    try:
        if settings.llm_provider == "ollama":
            import httpx

            resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]

            # Check if required models are available
            has_llm = any(settings.ollama_model in name for name in model_names)
            has_embed = any(settings.ollama_embed_model in name for name in model_names)

            if has_llm:
                console.print(f"  ✅ LLM model: {settings.ollama_model}")
            else:
                console.print(
                    f"  ⚠️  LLM model '{settings.ollama_model}' not found. "
                    f"Run: ollama pull {settings.ollama_model}",
                    style="yellow",
                )

            if has_embed:
                console.print(f"  ✅ Embedding model: {settings.ollama_embed_model}")
            else:
                console.print(
                    f"  ⚠️  Embedding model '{settings.ollama_embed_model}' not found. "
                    f"Run: ollama pull {settings.ollama_embed_model}",
                    style="yellow",
                )

            return has_llm and has_embed

        elif settings.llm_provider == "gemini":
            if not settings.google_api_key:
                console.print(
                    "  ❌ GOOGLE_API_KEY not set in .env",
                    style="red",
                )
                return False

            # Quick test: try to create the LLM
            llm = create_llm(settings)
            console.print(f"  ✅ Gemini model: {settings.gemini_model}")
            console.print(f"  ✅ API key configured")
            return True

    except Exception as e:
        console.print(f"  ❌ Connection failed: {e}", style="red")
        if settings.llm_provider == "ollama":
            console.print(
                "     Make sure Ollama is running: https://ollama.com/download",
                style="dim",
            )
        return False


def print_summary(settings: Settings, llm_ok: bool) -> None:
    """Print a configuration summary."""
    table = Table(title="IndexNote Configuration", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("LLM Provider", settings.llm_provider)
    table.add_row(
        "LLM Model",
        settings.ollama_model if settings.llm_provider == "ollama" else settings.gemini_model,
    )
    table.add_row(
        "Embed Model",
        settings.ollama_embed_model if settings.llm_provider == "ollama" else settings.gemini_embed_model,
    )
    table.add_row("Source Notes", str(settings.source_notes_dir))
    table.add_row("Data Directory", str(settings.data_dir))
    table.add_row("Chunk Size", str(settings.chunk_size))
    table.add_row("KG Paths/Chunk", str(settings.kg_max_paths_per_chunk))
    table.add_row("Auto Reindex", str(settings.auto_reindex))
    table.add_row("LLM Status", "✅ Ready" if llm_ok else "❌ Not Ready")

    console.print()
    console.print(table)


def main() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]🗂️  IndexNote Setup[/bold cyan]\n"
            "Initializing environment and verifying connections...",
            border_style="cyan",
        )
    )

    settings = get_settings()

    # 1. Create directories
    console.print("\n[bold]Creating directories...[/bold]")
    setup_directories(settings)

    # 2. Initialize stores
    init_stores(settings)

    # 3. Verify LLM
    llm_ok = verify_llm(settings)

    # 4. Summary
    print_summary(settings, llm_ok)

    if llm_ok:
        console.print(
            "\n[bold green]✅ Setup complete! Run `python main.py` to start IndexNote.[/bold green]"
        )
    else:
        console.print(
            "\n[bold yellow]⚠️  Setup complete but LLM not ready. Fix the issues above, then run again.[/bold yellow]"
        )


if __name__ == "__main__":
    main()

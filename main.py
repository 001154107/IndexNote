#!/usr/bin/env python3
"""
IndexNote — Main Entry Point

A local-first, privacy-first NotebookLM clone with hybrid VectorRAG + GraphRAG.

Usage:
    python main.py

Features:
    - Scans source_notes/ for new/changed files and indexes them
    - Watches for file changes in the background
    - Interactive query REPL with source citations
    - Slash commands for index management
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Fix Windows console encoding for Unicode/emoji output
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import nest_asyncio
nest_asyncio.apply()
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from indexnote import __version__, __app_name__
from indexnote.config import get_settings
from indexnote.utils.logging_config import setup_logging
from indexnote.utils.file_utils import is_supported_file
from indexnote.indexing.hybrid_index import HybridIndexManager
from indexnote.watcher.file_tracker import FileTracker
from indexnote.watcher.file_watcher import FileWatcher
from indexnote.retrieval.query_engine import QueryEngine

console = Console(force_terminal=True)


def print_banner():
    """Print the startup banner."""
    console.print(
        Panel.fit(
            f"[bold cyan]🗂️  {__app_name__} v{__version__}[/bold cyan]\n"
            "[dim]Local-first NotebookLM clone • Hybrid VectorRAG + GraphRAG[/dim]",
            border_style="cyan",
        )
    )


def scan_and_index(
    index_manager: HybridIndexManager,
    file_tracker: FileTracker,
    watcher: FileWatcher,
) -> int:
    """
    Scan source_notes/ and index any new or changed files.

    Returns:
        Number of files indexed.
    """
    files = watcher.scan_existing()

    if not files:
        console.print("[dim]No files found in source_notes/[/dim]")
        return 0

    new_files = []
    changed_files = []
    up_to_date = 0

    tracked = {Path(r.file_path).resolve(): r.status for r in file_tracker.get_all_tracked()}
    incomplete_files = []

    for fp in files:
        fp_res = fp.resolve()
        status = tracked.get(fp_res)
        if file_tracker.is_new(fp):
            new_files.append(fp)
        elif file_tracker.has_changed(fp):
            changed_files.append(fp)
        elif status == "vector_indexed":
            incomplete_files.append(fp)
        else:
            up_to_date += 1

    if not new_files and not changed_files and not incomplete_files:
        console.print(
            f"[green]✅ All {up_to_date} file(s) up to date[/green]"
        )
        return 0

    # Report what we found
    if new_files:
        console.print(f"[cyan]📄 New files: {len(new_files)}[/cyan]")
    if changed_files:
        console.print(f"[yellow]📝 Changed files: {len(changed_files)}[/yellow]")
    if incomplete_files:
        console.print(f"[magenta]⏳ Resuming incomplete files: {len(incomplete_files)}[/magenta]")
    if up_to_date:
        console.print(f"[dim]✅ Up to date: {up_to_date}[/dim]")

    # Index new + changed + incomplete files
    to_index = new_files + changed_files + incomplete_files
    indexed_count = 0

    for i, fp in enumerate(to_index, 1):
        console.print(
            f"  [{i}/{len(to_index)}] Indexing [bold]{fp.name}[/bold]...",
            end=" ",
        )
        try:
            # We must bind fp to the callback closure
            def make_callback(path=fp):
                return lambda: file_tracker.mark_status(path, "indexed")
                
            count = index_manager.index_file(fp, on_graph_complete=make_callback())
            file_tracker.mark_indexed(fp, status="vector_indexed")
            console.print(f"[green]✅ {count} chunk(s) (Graph queued)[/green]")
            indexed_count += 1
        except Exception as e:
            file_tracker.mark_error(fp, str(e))
            console.print(f"[red]❌ {e}[/red]")

    return indexed_count


import logging
logger = logging.getLogger(__name__)

def handle_file_change(
    file_path: Path,
    index_manager: HybridIndexManager,
    file_tracker: FileTracker,
    settings,
) -> None:
    """Handle a file change event from the watcher without interrupting the REPL."""
    if not is_supported_file(file_path):
        return

    if settings.auto_reindex:
        logger.info("Auto-reindexing: %s", file_path.name)
        try:
            def make_callback(path=file_path):
                return lambda: file_tracker.mark_status(path, "indexed")
                
            index_manager.index_file(file_path, on_graph_complete=make_callback())
            file_tracker.mark_indexed(file_path, status="vector_indexed")
            logger.info("Reindexed (Graph queued): %s", file_path.name)
        except Exception as e:
            file_tracker.mark_error(file_path, str(e))
            logger.error("Failed to reindex %s: %s", file_path.name, e)
    else:
        logger.info("File changed (not auto-indexed): %s", file_path.name)


def cmd_status(file_tracker: FileTracker) -> None:
    """Show status of all indexed files."""
    records = file_tracker.get_all_tracked()

    if not records:
        console.print("[dim]No files indexed yet.[/dim]")
        return

    table = Table(title="Indexed Files", show_header=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="cyan")
    table.add_column("Status", width=10)
    table.add_column("Size", justify="right", width=10)
    table.add_column("Indexed At", width=20)

    for i, rec in enumerate(records, 1):
        if rec.status == "indexed":
            status_style = "green"
        elif rec.status == "vector_indexed":
            status_style = "yellow"
        else:
            status_style = "red"
            
        size_str = _format_size(rec.file_size)
        table.add_row(
            str(i),
            Path(rec.file_path).name,
            f"[{status_style}]{rec.status}[/{status_style}]",
            size_str,
            rec.last_indexed_at[:19],
        )

    console.print(table)


def cmd_reindex(
    query: str,
    index_manager: HybridIndexManager,
    file_tracker: FileTracker,
    watcher: FileWatcher,
) -> None:
    """Reindex files matching a search pattern."""
    pattern = query.strip()
    if not pattern:
        console.print("[yellow]Usage: /reindex <filename pattern>[/yellow]")
        return

    files = watcher.scan_existing()
    matches = [f for f in files if pattern.lower() in f.name.lower()]

    if not matches:
        console.print(f"[yellow]No files matching '{pattern}'[/yellow]")
        return

    console.print(f"Reindexing {len(matches)} file(s)...")
    for fp in matches:
        try:
            def make_callback(path=fp):
                return lambda: file_tracker.mark_status(path, "indexed")
                
            count = index_manager.index_file(fp, on_graph_complete=make_callback())
            file_tracker.mark_indexed(fp, status="vector_indexed")
            console.print(f"  [green]✅ {fp.name}: {count} chunk(s) (Graph queued)[/green]")
        except Exception as e:
            file_tracker.mark_error(fp, str(e))
            console.print(f"  [red]❌ {fp.name}: {e}[/red]")


def cmd_graph(index_manager: HybridIndexManager) -> None:
    """Show graph statistics."""
    graph_index = index_manager.graph_index.get_index()
    if graph_index is None:
        console.print("[dim]Graph index not built yet.[/dim]")
        return

    try:
        store = graph_index.property_graph_store
        console.print("[bold]Knowledge Graph Statistics:[/bold]")
        console.print(f"  Graph store type: {type(store).__name__}")
        console.print("  [dim]Use queries to explore graph relationships[/dim]")
    except Exception as e:
        console.print(f"[yellow]Could not read graph stats: {e}[/yellow]")


def cmd_help() -> None:
    """Show help for available commands."""
    table = Table(title="Commands", show_header=True, box=None)
    table.add_column("Command", style="cyan", width=25)
    table.add_column("Description")

    table.add_row("/status", "Show all indexed files and their status")
    table.add_row("/reindex <pattern>", "Reindex files matching pattern")
    table.add_row("/graph", "Show knowledge graph statistics")
    table.add_row("/output <type> <topic>", "Generate MAS output (report, table, script)")
    table.add_row("/help", "Show this help message")
    table.add_row("/quit or /exit", "Exit IndexNote")
    table.add_row("<any text>", "Query your indexed notes")

    console.print(table)


def cmd_output(query: str, query_engine: QueryEngine, settings: Settings) -> None:
    """Generate a MAS output document."""
    parts = query.split(maxsplit=1)
    if len(parts) < 2:
        console.print("[yellow]Usage: /output <report|table|script> <topic>[/yellow]")
        return
        
    output_type, topic = parts[0].lower(), parts[1]
    if output_type not in ("report", "table", "script"):
        console.print("[yellow]Error: type must be 'report', 'table', or 'script'[/yellow]")
        return
        
    console.print(f"[bold cyan]🚀 Starting MAS Pipeline for '{output_type}'...[/bold cyan]")
    try:
        from indexnote.outputs.mas_pipeline import MASPipeline
        pipeline = MASPipeline(query_engine, settings)
        
        console.print("[dim]  1. Researcher Agent gathering context...[/dim]")
        # We don't have rich spinners without context managers, so just print
        console.print("[dim]  2. Writer Agent drafting content...[/dim]")
        console.print("[dim]  3. Reviewer Agent fact-checking and finalizing...[/dim]")
        
        out_path = pipeline.generate_output(output_type, topic)
        console.print(f"[green]✅ Success! Output saved to: {out_path}[/green]")
    except Exception as e:
        console.print(f"[red]❌ Pipeline failed: {e}[/red]")


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def main() -> None:
    """Main entry point for IndexNote."""
    settings = get_settings()
    setup_logging(settings.log_level)

    print_banner()

    # Verify CUDA environment for audio parsing
    from indexnote.utils.cuda_check import run_cuda_check
    run_cuda_check()

    # Initialize components
    console.print("\n[bold]Initializing...[/bold]")

    try:
        index_manager = HybridIndexManager(settings)
        console.print("  ✅ Stores connected (Kuzu + ChromaDB)")
    except Exception as e:
        console.print(f"  [red]❌ Failed to initialize stores: {e}[/red]")
        console.print("  [dim]Run `python scripts/setup_env.py` first.[/dim]")
        sys.exit(1)

    file_tracker = FileTracker(settings)
    console.print("  ✅ File tracker ready")

    # Try to load existing indexes
    index_manager.load_existing_indexes()

    # Scan and index files
    console.print("\n[bold]Scanning source_notes/...[/bold]")
    scan_and_index(index_manager, file_tracker, FileWatcher(settings=settings))

    # Start file watcher
    query_engine = QueryEngine(index_manager, settings)

    def on_change(path: Path):
        handle_file_change(path, index_manager, file_tracker, settings)

    def on_delete(path: Path):
        console.print(f"\n[red]🗑️  File deleted: {path.name}[/red]")
        file_tracker.remove(path)
        console.print("[bold cyan]IndexNote>[/bold cyan] ", end="")

    watcher = FileWatcher(
        on_file_changed=on_change,
        on_file_deleted=on_delete,
        settings=settings,
    )
    watcher.start()
    console.print(f"\n👁️  Watching [cyan]{settings.source_notes_dir}[/cyan] for changes")

    # REPL
    console.print("\n[bold green]Ready! Type your question or /help for commands.[/bold green]\n")

    try:
        while True:
            try:
                user_input = Prompt.ask("[bold cyan]IndexNote[/bold cyan]")
            except (EOFError, KeyboardInterrupt):
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ("/quit", "/exit", "/q"):
                break
            elif user_input.lower() == "/help":
                cmd_help()
            elif user_input.lower() == "/status":
                cmd_status(file_tracker)
            elif user_input.lower().startswith("/reindex"):
                pattern = user_input[len("/reindex"):].strip()
                cmd_reindex(pattern, index_manager, file_tracker, watcher)
            elif user_input.lower().startswith("/output"):
                cmd_output(user_input[len("/output"):].strip(), query_engine, settings)
            elif user_input.lower() == "/graph":
                cmd_graph(index_manager)
            elif user_input.startswith("/"):
                console.print(f"[yellow]Unknown command: {user_input}. Type /help for commands.[/yellow]")
            else:
                # Query mode
                console.print("[dim]Searching...[/dim]")
                try:
                    response = query_engine.query(user_input)
                    console.print()
                    console.print(Panel(
                        response.answer,
                        title="Answer",
                        border_style="green",
                        padding=(1, 2),
                    ))
                    if response.citations_display:
                        console.print(response.citations_display)
                    console.print()
                except Exception as e:
                    console.print(f"\n[red]Query failed: {e}[/red]\n")

    finally:
        from indexnote.indexing.background_queue import BackgroundQueue
        BackgroundQueue().shutdown()
        watcher.stop()
        file_tracker.close()
        console.print("\n[dim]Goodbye! 👋[/dim]")


if __name__ == "__main__":
    main()

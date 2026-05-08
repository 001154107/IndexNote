#!/usr/bin/env python3
"""
ingest.py — Manual one-shot ingestion (no watcher).

Use this to manually index specific files or re-scan the entire source_notes directory.

Usage:
    python scripts/ingest.py                    # Scan and index all new/changed files
    python scripts/ingest.py path/to/file.pdf   # Index a specific file
    python scripts/ingest.py --force             # Force reindex everything
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Fix Windows console encoding for Unicode/emoji output
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from rich.console import Console

from indexnote.config import get_settings
from indexnote.utils.logging_config import setup_logging
from indexnote.indexing.hybrid_index import HybridIndexManager
from indexnote.watcher.file_tracker import FileTracker
from indexnote.watcher.file_watcher import FileWatcher

console = Console(force_terminal=True)


def main():
    parser = argparse.ArgumentParser(description="IndexNote manual ingestion")
    parser.add_argument("files", nargs="*", help="Specific files to index")
    parser.add_argument("--force", action="store_true", help="Force reindex all files")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level)

    console.print("[bold cyan]🗂️  IndexNote — Manual Ingestion[/bold cyan]\n")

    index_manager = HybridIndexManager(settings)
    file_tracker = FileTracker(settings)
    index_manager.load_existing_indexes()

    if args.files:
        # Index specific files
        for fp in args.files:
            path = Path(fp).resolve()
            if not path.exists():
                console.print(f"[red]File not found: {fp}[/red]")
                continue
            try:
                count = index_manager.index_file(path)
                file_tracker.mark_indexed(path)
                console.print(f"[green]✅ {path.name}: {count} chunk(s)[/green]")
            except Exception as e:
                file_tracker.mark_error(path, str(e))
                console.print(f"[red]❌ {path.name}: {e}[/red]")
    else:
        # Scan source_notes directory
        watcher = FileWatcher(settings=settings)
        files = watcher.scan_existing()

        if not files:
            console.print("[dim]No files found in source_notes/[/dim]")
            return

        to_index = []
        for fp in files:
            if args.force or file_tracker.is_new(fp) or file_tracker.has_changed(fp):
                to_index.append(fp)

        if not to_index:
            console.print(f"[green]All {len(files)} file(s) up to date. Use --force to reindex.[/green]")
            return

        console.print(f"Indexing {len(to_index)} file(s)...\n")
        for i, fp in enumerate(to_index, 1):
            console.print(f"  [{i}/{len(to_index)}] {fp.name}...", end=" ")
            try:
                count = index_manager.index_file(fp)
                file_tracker.mark_indexed(fp)
                console.print(f"[green]✅ {count} chunk(s)[/green]")
            except Exception as e:
                file_tracker.mark_error(fp, str(e))
                console.print(f"[red]❌ {e}[/red]")

    file_tracker.close()
    console.print("\n[bold green]Done![/bold green]")


if __name__ == "__main__":
    main()

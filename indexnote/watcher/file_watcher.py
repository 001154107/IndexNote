"""
File Watcher — monitors source_notes directory for file changes.

Uses watchdog to detect new, modified, and deleted files.
Integrates with the FileTracker to determine indexing actions.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
    FileMovedEvent,
)

from indexnote.config import Settings, get_settings
from indexnote.utils.file_utils import is_supported_file, IGNORED_PATTERNS

logger = logging.getLogger(__name__)


class _DebouncedHandler(FileSystemEventHandler):
    """
    File event handler with debouncing.

    Aggregates rapid file change events within a debounce window
    to avoid triggering multiple re-indexes for a single save.
    """

    def __init__(
        self,
        on_file_changed: Callable[[Path], None],
        on_file_deleted: Callable[[Path], None],
        debounce_seconds: float = 2.0,
    ):
        super().__init__()
        self._on_file_changed = on_file_changed
        self._on_file_deleted = on_file_deleted
        self._debounce_seconds = debounce_seconds

        self._pending: dict[str, float] = {}  # path → timestamp
        self._lock = threading.Lock()
        self._timer_thread: threading.Thread | None = None
        self._running = True

        # Start the debounce processor
        self._timer_thread = threading.Thread(
            target=self._process_pending, daemon=True
        )
        self._timer_thread.start()

    def _should_ignore(self, path: str) -> bool:
        """Check if a file event should be ignored."""
        p = Path(path)
        
        # Explicitly allow operational files for scraper logic
        if p.name in {"ONLINE_SOURCES.md", "SUGGESTED_URLS.md"}:
            return False
            
        if p.name in IGNORED_PATTERNS:
            return True
        if not is_supported_file(p):
            return True
        if p.is_dir():
            return True
        return False

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory and not self._should_ignore(event.src_path):
            self._schedule(event.src_path)

    def on_modified(self, event: FileModifiedEvent) -> None:
        if not event.is_directory and not self._should_ignore(event.src_path):
            self._schedule(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        if not event.is_directory:
            if not self._should_ignore(event.src_path):
                self._on_file_deleted(Path(event.src_path))
            if not self._should_ignore(event.dest_path):
                self._schedule(event.dest_path)

    def on_deleted(self, event: FileDeletedEvent) -> None:
        if not event.is_directory and not self._should_ignore(event.src_path):
            self._on_file_deleted(Path(event.src_path))

    def _schedule(self, path: str) -> None:
        """Schedule a file change event with debouncing."""
        with self._lock:
            self._pending[path] = time.time()

    def _process_pending(self) -> None:
        """Background thread that processes debounced events."""
        from indexnote.scraper.web_scraper import WebScraper
        from indexnote.scraper.url_extractor import URLExtractor
        
        scraper = WebScraper()
        
        while self._running:
            time.sleep(0.5)
            now = time.time()
            ready = []

            with self._lock:
                for path, timestamp in list(self._pending.items()):
                    if now - timestamp >= self._debounce_seconds:
                        ready.append(path)
                        del self._pending[path]

            for path in ready:
                try:
                    p = Path(path)
                    if p.exists():
                        # Intercept special scraper files
                        if p.name == "ONLINE_SOURCES.md":
                            self._handle_online_sources(p, scraper, URLExtractor)
                        elif p.name == "SUGGESTED_URLS.md":
                            self._handle_suggested_urls(p, scraper, URLExtractor)
                        else:
                            self._on_file_changed(p)
                except Exception as e:
                    logger.error("Error processing file change %s: %s", path, e)

    def _handle_online_sources(self, p: Path, scraper: 'WebScraper', extractor: type['URLExtractor']) -> None:
        """Extract URLs from ONLINE_SOURCES.md and download them."""
        text = p.read_text(encoding="utf-8", errors="replace")
        urls = extractor.extract_urls(text)
        
        # In a real scenario we'd deduplicate against already downloaded URLs.
        # For now, WebScraper will overwrite or we can just download all.
        for url in urls:
            # Check if we've already marked it in the file to avoid infinite loops
            # Actually, ONLINE_SOURCES.md is manual, so downloading every time it changes might be much.
            # A simple deduplication: check if file with this URL name already exists is hard due to uuid.
            # We'll just trigger download. The user is expected to manage this file.
            scraper.download_url(url)

    def _handle_suggested_urls(self, p: Path, scraper: 'WebScraper', extractor: type['URLExtractor']) -> None:
        """Find checked boxes in SUGGESTED_URLS.md, download them, and mark as downloaded."""
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        modified = False
        
        new_lines = []
        for line in lines:
            if line.strip().startswith("- [x]") and "(Downloaded)" not in line:
                urls = extractor.extract_urls(line)
                for url in urls:
                    if scraper.download_url(url):
                        line = f"{line} (Downloaded)"
                        modified = True
                        break # Only process first URL per line
            new_lines.append(line)
            
        if modified:
            p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def stop(self) -> None:
        """Stop the debounce processor."""
        self._running = False


class FileWatcher:
    """
    Watches the source_notes directory for file changes.

    Integrates with callbacks for new/changed/deleted files.
    """

    def __init__(
        self,
        watch_dir: str | Path | None = None,
        on_file_changed: Callable[[Path], None] | None = None,
        on_file_deleted: Callable[[Path], None] | None = None,
        settings: Settings | None = None,
    ):
        """
        Initialize the file watcher.

        Args:
            watch_dir: Directory to watch. Defaults to config source_notes_dir.
            on_file_changed: Callback for new/modified files.
            on_file_deleted: Callback for deleted files.
            settings: Configuration settings.
        """
        self._settings = settings or get_settings()
        self._watch_dir = Path(watch_dir or self._settings.source_notes_dir).resolve()
        self._watch_dir.mkdir(parents=True, exist_ok=True)

        self._on_file_changed = on_file_changed or self._default_change_handler
        self._on_file_deleted = on_file_deleted or self._default_delete_handler

        self._handler = _DebouncedHandler(
            on_file_changed=self._on_file_changed,
            on_file_deleted=self._on_file_deleted,
            debounce_seconds=self._settings.watcher_debounce_seconds,
        )
        self._observer = Observer()

    def start(self) -> None:
        """Start watching the directory."""
        logger.info("Watching directory: %s", self._watch_dir)
        self._observer.schedule(self._handler, str(self._watch_dir), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        """Stop the watcher."""
        self._handler.stop()
        self._observer.stop()
        self._observer.join(timeout=5)
        logger.info("File watcher stopped")

    def scan_existing(self) -> list[Path]:
        """
        Scan the watched directory for existing supported files.

        Returns:
            List of paths to supported files.
        """
        files = []
        for fp in self._watch_dir.rglob("*"):
            if fp.is_file() and is_supported_file(fp):
                files.append(fp)
        files.sort()
        return files

    @staticmethod
    def _default_change_handler(path: Path) -> None:
        logger.info("File changed: %s", path.name)

    @staticmethod
    def _default_delete_handler(path: Path) -> None:
        logger.info("File deleted: %s", path.name)

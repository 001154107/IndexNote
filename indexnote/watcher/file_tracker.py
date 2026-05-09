"""
File Tracker — SQLite-backed metadata cache for tracking indexed files.

Tracks file hashes, sizes, and index timestamps to detect changes
and avoid unnecessary re-indexing.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass

from indexnote.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class FileRecord:
    """Record of a tracked file."""

    file_path: str
    file_hash: str
    file_size: int
    last_indexed_at: str
    status: str  # "indexed", "pending", "error"


class FileTracker:
    """
    SQLite-backed file metadata tracker.

    Stores file hashes (SHA-256) and timestamps to detect changes
    and determine which files need (re)indexing.
    """

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._db_path = self._settings.file_index_db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._create_table()

    def _create_table(self) -> None:
        """Create the file tracking table if it doesn't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tracked_files (
                file_path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                last_indexed_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'indexed'
            )
        """)
        self._conn.commit()

    @staticmethod
    def compute_hash(file_path: str | Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def is_new(self, file_path: str | Path) -> bool:
        """Check if a file is not yet tracked."""
        file_path = str(Path(file_path).resolve())
        cursor = self._conn.execute(
            "SELECT 1 FROM tracked_files WHERE file_path = ?", (file_path,)
        )
        return cursor.fetchone() is None

    def has_changed(self, file_path: str | Path) -> bool:
        """Check if a tracked file has changed since last indexing."""
        file_path_str = str(Path(file_path).resolve())
        cursor = self._conn.execute(
            "SELECT file_hash FROM tracked_files WHERE file_path = ?",
            (file_path_str,),
        )
        row = cursor.fetchone()
        if row is None:
            return True  # New file = changed

        current_hash = self.compute_hash(file_path)
        return current_hash != row[0]

    def mark_indexed(self, file_path: str | Path, status: str = "indexed") -> None:
        """Mark a file as successfully indexed with its current hash."""
        file_path = Path(file_path).resolve()
        file_hash = self.compute_hash(file_path)
        file_size = file_path.stat().st_size
        now = datetime.now(timezone.utc).isoformat()

        self._conn.execute(
            """
            INSERT OR REPLACE INTO tracked_files
            (file_path, file_hash, file_size, last_indexed_at, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(file_path), file_hash, file_size, now, status),
        )
        self._conn.commit()

    def mark_status(self, file_path: str | Path, status: str) -> None:
        """Update just the status of an existing tracked file."""
        file_path = str(Path(file_path).resolve())
        self._conn.execute(
            "UPDATE tracked_files SET status = ? WHERE file_path = ?",
            (status, file_path),
        )
        self._conn.commit()

    def mark_error(self, file_path: str | Path, error: str = "") -> None:
        """Mark a file as having an indexing error."""
        file_path = Path(file_path).resolve()
        now = datetime.now(timezone.utc).isoformat()

        try:
            file_hash = self.compute_hash(file_path)
            file_size = file_path.stat().st_size
        except Exception:
            file_hash = "error"
            file_size = 0

        self._conn.execute(
            """
            INSERT OR REPLACE INTO tracked_files
            (file_path, file_hash, file_size, last_indexed_at, status)
            VALUES (?, ?, ?, ?, 'error')
            """,
            (str(file_path), file_hash, file_size, now),
        )
        self._conn.commit()

    def remove(self, file_path: str | Path) -> None:
        """Remove a file from tracking."""
        file_path = str(Path(file_path).resolve())
        self._conn.execute(
            "DELETE FROM tracked_files WHERE file_path = ?", (file_path,)
        )
        self._conn.commit()

    def get_all_tracked(self) -> list[FileRecord]:
        """Return all tracked file records."""
        cursor = self._conn.execute(
            "SELECT file_path, file_hash, file_size, last_indexed_at, status "
            "FROM tracked_files ORDER BY last_indexed_at DESC"
        )
        return [
            FileRecord(
                file_path=row[0],
                file_hash=row[1],
                file_size=row[2],
                last_indexed_at=row[3],
                status=row[4],
            )
            for row in cursor.fetchall()
        ]

    def get_indexed_count(self) -> int:
        """Return count of successfully indexed files."""
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM tracked_files WHERE status = 'indexed'"
        )
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

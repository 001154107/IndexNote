"""Smoke test — Docling parser + HybridIndexManager initialization."""
import sys
import os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from indexnote.config import get_settings
from indexnote.parsers.docling_parser import DoclingParser
from indexnote.indexing.hybrid_index import HybridIndexManager
from indexnote.watcher.file_tracker import FileTracker
from indexnote.watcher.file_watcher import FileWatcher

settings = get_settings()

print("=== Docling Parser Test ===")
parser = DoclingParser()
test_file = Path("source_notes/research_notes.md")
docs = parser.parse(test_file)
print(f"[OK] Docling parsed {test_file.name}: {len(docs)} document(s)")
for i, doc in enumerate(docs):
    preview = doc.text[:120].replace("\n", " ")
    print(f"  Doc {i}: {len(doc.text)} chars")
    print(f"  Preview: {preview}...")
    print(f"  Metadata: {doc.metadata}")

print()
print("=== HybridIndexManager Init Test ===")
mgr = HybridIndexManager(settings)
print("[OK] HybridIndexManager created")
print(f"  Graph store: {type(mgr.graph_store).__name__}")
print(f"  Vector store: {type(mgr.vector_store).__name__}")

print()
print("=== File Router Test ===")
from indexnote.utils.file_utils import get_parser_type

test_files = [
    "report.pdf", "notes.md", "data.json", "song.mp3",
    "video.mp4", "diagram.png", "page.mht", "archive.zip"
]
for f in test_files:
    pt = get_parser_type(f)
    print(f"  {f:20s} -> {pt.value}")

print()
print("=== File Watcher Scan Test ===")
watcher = FileWatcher(settings=settings)
files = watcher.scan_existing()
print(f"[OK] Found {len(files)} file(s) in source_notes/:")
for f in files:
    print(f"  - {f.name} ({f.stat().st_size} bytes)")

print()
print("ALL SMOKE TESTS PASSED!")

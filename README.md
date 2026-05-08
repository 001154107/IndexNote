# 🗂️ IndexNote

**A local-first, privacy-first NotebookLM clone** with hybrid VectorRAG + GraphRAG.

Drop any file into `source_notes/` — PDFs, images, audio, video, HTML, Markdown — and IndexNote will extract meaning, build a knowledge graph, and let you query everything with AI-powered source citations.

## ✨ Features

- **Multi-modal ingestion**: PDF, DOCX, PPTX, XLSX, HTML, MHT, Markdown, images (OCR + AI vision), audio (Whisper), video (keyframe + transcription)
- **Hybrid RAG**: Combines vector similarity (ChromaDB) with knowledge graph traversal (Kuzu) for richer retrieval
- **Source citations**: Every answer links back to the exact source file and chunk
- **File watching**: Auto-detects new/changed files in your notes folder
- **Fully local**: Runs entirely on your machine with Ollama — no data leaves your device
- **Cloud option**: Optional Gemini API support for higher-quality responses
- **100% FOSS**: MIT licensed, no proprietary dependencies

## 🏗️ Architecture

```
source_notes/ → Docling/Whisper/OpenCV → LlamaIndex → Kuzu (Graph) + ChromaDB (Vector) → Hybrid Query → Cited Answers
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Ollama** running locally ([install](https://ollama.com/download))
  ```bash
  ollama pull llama3.1
  ollama pull nomic-embed-text
  ```

### Setup

```bash
# Clone and enter project
cd IndexNote

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
copy .env.example .env       # Windows
# cp .env.example .env       # Linux/Mac

# Initialize databases
python scripts/setup_env.py
```

### Usage

```bash
# Run IndexNote
python main.py
```

Drop files into `source_notes/` and start querying:

```
IndexNote> What concepts are discussed in my notes?

Based on your documents, the key concepts include...

Sources:
  [1] source_notes/ml_paper.pdf (chunk 3, score: 0.89)
  [2] source_notes/lecture_notes.md (chunk 1, score: 0.85)

IndexNote> /status          # Show indexed files
IndexNote> /reindex paper   # Force reindex matching files
IndexNote> /graph           # Show graph statistics
IndexNote> /help            # Show all commands
IndexNote> /quit            # Exit
```

## 📁 Project Structure

```
IndexNote/
├── source_notes/           # Drop your files here (watched folder)
├── data/                   # Persistent stores (auto-created)
│   ├── chroma_db/          # Vector embeddings
│   ├── kuzu_db/            # Knowledge graph
│   └── file_index.db       # File metadata cache
├── indexnote/              # Main package
│   ├── config.py           # Settings & LLM factory
│   ├── parsers/            # Document type adapters
│   ├── indexing/           # Graph + Vector index managers
│   ├── retrieval/          # Hybrid query engine
│   ├── watcher/            # File system monitor
│   └── utils/              # Shared utilities
├── scripts/
│   └── setup_env.py        # Database initialization
├── main.py                 # Entry point
└── requirements.txt
```

## ⚙️ Configuration

Edit `.env` to configure:

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` (local) or `gemini` (cloud) |
| `OLLAMA_MODEL` | `llama3.1` | Ollama LLM model name |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `GOOGLE_API_KEY` | *(empty)* | Gemini API key (if using Gemini) |
| `CHUNK_SIZE` | `1024` | Token chunk size for indexing |
| `AUTO_REINDEX` | `false` | Auto-reindex on file changes |

See [.env.example](.env.example) for all options.

## 📄 Supported File Types

| Category | Extensions |
|---|---|
| **Documents** | `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`, `.mht` |
| **Text** | `.md`, `.txt`, `.csv`, `.json`, `.xml`, `.yaml` |
| **Images** | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff` |
| **Audio** | `.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac` |
| **Video** | `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm` |

## 📜 License

MIT — see [LICENSE](LICENSE).

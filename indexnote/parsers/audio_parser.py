"""
Audio transcription parser using faster-whisper.

Handles: MP3, WAV, M4A, OGG, FLAC, AAC, WMA, OPUS.
Transcribes audio to text locally using Whisper models.
"""

from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core.schema import Document

from indexnote.config import get_settings

logger = logging.getLogger(__name__)


class AudioParser:
    """
    Transcribe audio files using faster-whisper (CTranslate2-based Whisper).

    Requires: pip install faster-whisper
    """

    def __init__(self, model_size: str | None = None):
        """
        Initialize audio parser.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3).
                        Defaults to config setting.
        """
        self._model_size = model_size or get_settings().whisper_model_size
        self._model = None

    def _get_model(self):
        """Lazy-load the Whisper model."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel

                logger.info("Loading Whisper model: %s", self._model_size)
                self._model = WhisperModel(
                    self._model_size,
                    device="auto",
                    compute_type="auto",
                )
            except ImportError:
                raise ImportError(
                    "faster-whisper is required for audio parsing. "
                    "Install it with: pip install faster-whisper"
                )
        return self._model

    def parse(self, file_path: str | Path) -> list[Document]:
        """
        Transcribe an audio file into a LlamaIndex Document.

        Args:
            file_path: Path to the audio file.

        Returns:
            List containing a single Document with the transcription.
        """
        file_path = Path(file_path).resolve()
        logger.info("Transcribing audio: %s", file_path.name)

        model = self._get_model()

        try:
            segments, info = model.transcribe(
                str(file_path),
                beam_size=5,
                language=None,  # Auto-detect language
            )

            # Collect all segments into full transcript
            transcript_parts = []
            for segment in segments:
                timestamp = f"[{segment.start:.1f}s - {segment.end:.1f}s]"
                transcript_parts.append(f"{timestamp} {segment.text.strip()}")

            full_transcript = "\n".join(transcript_parts)

            if not full_transcript.strip():
                logger.warning("No speech detected in: %s", file_path.name)
                full_transcript = "[No speech detected in audio file]"

            doc = Document(
                text=full_transcript,
                metadata={
                    "source_file": str(file_path),
                    "file_name": file_path.name,
                    "file_type": file_path.suffix.lower(),
                    "content_type": "audio_transcription",
                    "language": info.language if info else "unknown",
                    "duration_seconds": round(info.duration, 1) if info else 0,
                },
            )

            logger.info(
                "Transcribed %s: %.1f seconds, language=%s",
                file_path.name,
                info.duration if info else 0,
                info.language if info else "unknown",
            )
            return [doc]

        except Exception as e:
            logger.error("Failed to transcribe %s: %s", file_path.name, e)
            raise

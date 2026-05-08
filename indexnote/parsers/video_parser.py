"""
Video parser — keyframe extraction + AI description + optional audio transcription.

Handles: MP4, MKV, AVI, MOV, WebM, WMV, FLV, M4V.
Uses OpenCV for keyframe extraction, vision LLM for frame description.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from llama_index.core.schema import Document

from indexnote.config import get_settings, create_vision_llm

logger = logging.getLogger(__name__)


class VideoParser:
    """
    Extract keyframes from video and generate AI descriptions.

    Requires: pip install opencv-python-headless scenedetect[opencv]
    Optionally also transcribes the audio track.
    """

    def __init__(self):
        self._vision_llm = None

    def _get_vision_llm(self):
        """Lazy-load vision LLM."""
        if self._vision_llm is None:
            self._vision_llm = create_vision_llm()
        return self._vision_llm

    def _extract_keyframes(self, video_path: Path, max_frames: int = 10) -> list[Path]:
        """
        Extract keyframes from a video using scene detection.

        Falls back to uniform sampling if scenedetect is unavailable.

        Returns:
            List of paths to extracted frame images (temporary files).
        """
        try:
            import cv2
        except ImportError:
            raise ImportError(
                "opencv-python-headless is required for video parsing. "
                "Install it with: pip install opencv-python-headless"
            )

        frame_paths = []
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        # Try scene detection first
        try:
            from scenedetect import SceneManager, open_video, ContentDetector

            video = open_video(str(video_path))
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=30.0))
            scene_manager.detect_scenes(frame_source=video)
            scene_list = scene_manager.get_scene_list()

            if scene_list:
                # Extract frame from middle of each scene
                for scene in scene_list[:max_frames]:
                    mid_frame = (scene[0].get_frames() + scene[1].get_frames()) // 2
                    cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
                    ret, frame = cap.read()
                    if ret:
                        tmp = tempfile.NamedTemporaryFile(
                            suffix=".jpg", delete=False, prefix="indexnote_frame_"
                        )
                        cv2.imwrite(tmp.name, frame)
                        frame_paths.append(Path(tmp.name))

                cap.release()
                logger.info("Extracted %d keyframes via scene detection", len(frame_paths))
                return frame_paths

        except ImportError:
            logger.debug("scenedetect not available, using uniform sampling")

        # Fallback: uniform frame sampling
        if total_frames > 0:
            interval = max(total_frames // max_frames, 1)
            for i in range(0, min(total_frames, max_frames * interval), interval):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if ret:
                    tmp = tempfile.NamedTemporaryFile(
                        suffix=".jpg", delete=False, prefix="indexnote_frame_"
                    )
                    cv2.imwrite(tmp.name, frame)
                    frame_paths.append(Path(tmp.name))

        cap.release()
        logger.info("Extracted %d keyframes via uniform sampling", len(frame_paths))
        return frame_paths

    def _describe_frame(self, frame_path: Path, frame_index: int) -> str:
        """Use vision LLM to describe a video frame."""
        import base64

        llm = self._get_vision_llm()
        image_data = frame_path.read_bytes()
        b64_image = base64.b64encode(image_data).decode("utf-8")

        try:
            from llama_index.core.llms import ChatMessage, ImageBlock, TextBlock

            response = llm.chat(
                messages=[
                    ChatMessage(
                        role="user",
                        blocks=[
                            ImageBlock(image=b64_image, image_mimetype="image/jpeg"),
                            TextBlock(
                                text=(
                                    "Describe this video frame in detail. Include any visible "
                                    "text, diagrams, people, objects, or scenes. Be concise "
                                    "but thorough."
                                )
                            ),
                        ],
                    )
                ]
            )
            return f"[Frame {frame_index + 1}] {response.message.content}"
        except Exception as e:
            logger.warning("Failed to describe frame %d: %s", frame_index, e)
            return f"[Frame {frame_index + 1}] [Description unavailable]"

    def parse(self, file_path: str | Path) -> list[Document]:
        """
        Parse a video file: extract keyframes, describe them, optionally transcribe audio.

        Args:
            file_path: Path to the video file.

        Returns:
            List of Document objects with frame descriptions and transcription.
        """
        file_path = Path(file_path).resolve()
        logger.info("Processing video: %s", file_path.name)

        docs = []
        temp_frames = []

        try:
            # 1. Extract keyframes
            temp_frames = self._extract_keyframes(file_path)

            # 2. Describe each keyframe
            if temp_frames:
                descriptions = []
                for i, frame in enumerate(temp_frames):
                    desc = self._describe_frame(frame, i)
                    descriptions.append(desc)

                frame_doc = Document(
                    text="\n\n".join(descriptions),
                    metadata={
                        "source_file": str(file_path),
                        "file_name": file_path.name,
                        "file_type": file_path.suffix.lower(),
                        "content_type": "video_frame_descriptions",
                        "num_frames": len(descriptions),
                    },
                )
                docs.append(frame_doc)

            # 3. Try to transcribe audio track
            try:
                from indexnote.parsers.audio_parser import AudioParser

                audio_parser = AudioParser()
                audio_docs = audio_parser.parse(file_path)
                for doc in audio_docs:
                    doc.metadata["content_type"] = "video_audio_transcription"
                docs.extend(audio_docs)
            except Exception as e:
                logger.debug("Audio transcription skipped for video: %s", e)

            logger.info("Processed video %s: %d document(s)", file_path.name, len(docs))
            return docs

        finally:
            # Clean up temporary frame files
            for frame in temp_frames:
                try:
                    frame.unlink(missing_ok=True)
                except Exception:
                    pass

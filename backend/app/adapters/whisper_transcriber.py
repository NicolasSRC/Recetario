"""Transcripción local con faster-whisper (RF-10, RF-11)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.config import ConfigError
from app.domain.content import Transcript, TranscriptSegment


class WhisperTranscriber:
    """Carga el modelo de forma perezosa: importar este módulo no cuesta nada."""

    def __init__(
        self,
        *,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model: Any | None = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ModuleNotFoundError as exc:
                raise ConfigError(
                    'falta faster-whisper. Instálalo con: pip install -e "backend[audio]"'
                ) from exc
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
        return self._model

    async def transcribe(self, audio_path: Path) -> Transcript:
        return await asyncio.to_thread(self._transcribe_sync, audio_path)

    def _transcribe_sync(self, audio_path: Path) -> Transcript:
        if not audio_path.exists():
            raise FileNotFoundError(f"no existe el audio: {audio_path}")

        model = self._ensure_model()
        raw_segments, info = model.transcribe(str(audio_path), vad_filter=True)

        segments = tuple(
            TranscriptSegment(
                start_s=float(segment.start),
                end_s=float(segment.end),
                text=segment.text.strip(),
            )
            for segment in raw_segments
        )
        text = " ".join(segment.text for segment in segments).strip()

        if not text:
            raise ValueError("la transcripción quedó vacía (¿el video no tiene voz?)")

        return Transcript(text=text, language=getattr(info, "language", None), segments=segments)

"""Interfaces de entrada del sistema (hexagonal: el dominio no conoce adaptadores)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.domain.content import Frame, ScreenTextResult, Transcript, VideoMetadata


class VideoExtractor(Protocol):
    """RF-05: cambiar yt-dlp por otro extractor sin tocar el resto."""

    async def get_metadata(self, url: str) -> VideoMetadata: ...

    async def download_audio(self, url: str, dest: Path) -> Path: ...

    async def download_video(self, url: str, dest: Path) -> Path: ...


class Transcriber(Protocol):
    async def transcribe(self, audio_path: Path) -> Transcript: ...


class FrameSampler(Protocol):
    """RF-12: muestrea fotogramas de un video ya descargado."""

    async def sample(
        self, video_path: Path, dest_dir: Path, interval_s: float
    ) -> tuple[Frame, ...]: ...


class ScreenTextReader(Protocol):
    """RNF-09: OCR clásico o modelo de visión, intercambiables por configuración."""

    async def read(self, frame: Frame) -> str: ...


class ScreenTextExtractor(Protocol):
    """Compone muestreo + lectura y devuelve texto con marca de tiempo."""

    async def read(self, video_path: Path, dest_dir: Path) -> ScreenTextResult: ...

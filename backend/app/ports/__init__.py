"""Interfaces de entrada del sistema (hexagonal: el dominio no conoce adaptadores)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.domain.content import Transcript, VideoMetadata


class VideoExtractor(Protocol):
    """RF-05: cambiar yt-dlp por otro extractor sin tocar el resto."""

    async def get_metadata(self, url: str) -> VideoMetadata: ...

    async def download_audio(self, url: str, dest: Path) -> Path: ...


class Transcriber(Protocol):
    async def transcribe(self, audio_path: Path) -> Transcript: ...

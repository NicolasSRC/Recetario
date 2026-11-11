"""Contenido de entrada: metadatos, transcripción y texto en pantalla.

Son estructuras puras (dataclasses) que viajan entre adaptadores y pipeline.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.domain.schemas import Evidence


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    start_s: float
    end_s: float
    text: str


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: str | None = None
    segments: tuple[TranscriptSegment, ...] = ()

    def with_timestamps(self) -> str:
        if not self.segments:
            return self.text
        lines = (f"[{seg.start_s:.1f}s-{seg.end_s:.1f}s] {seg.text}" for seg in self.segments)
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ScreenText:
    timestamp_s: float
    text: str


@dataclass(frozen=True, slots=True)
class Frame:
    """Un fotograma extraído del video, listo para OCR o visión (RF-12)."""

    path: Path
    timestamp_s: float


@dataclass(frozen=True, slots=True)
class ScreenTextResult:
    """Texto leído en los frames, con cuántos se analizaron y su costo."""

    items: tuple[ScreenText, ...] = ()
    frames_analyzed: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    url: str
    canonical_url: str | None = None
    author: str | None = None
    caption: str = ""
    duration_s: float | None = None
    hashtags: tuple[str, ...] = ()
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _escape(value: str) -> str:
    """Escapa el contenido para que no pueda cerrar las etiquetas del prompt."""
    return html.escape(value, quote=True)


@dataclass(frozen=True, slots=True)
class RecipeContext:
    """Todo lo que se sabe de un video antes de llamar al LLM."""

    metadata: VideoMetadata | None = None
    transcript: Transcript | None = None
    screen_text: tuple[ScreenText, ...] = ()

    @property
    def caption(self) -> str:
        return self.metadata.caption.strip() if self.metadata else ""

    @property
    def url(self) -> str | None:
        if not self.metadata:
            return None
        return self.metadata.canonical_url or self.metadata.url

    def sources_used(self) -> list[Evidence]:
        used: list[Evidence] = []
        if self.caption:
            used.append(Evidence.CAPTION)
        if self.transcript and self.transcript.text.strip():
            used.append(Evidence.AUDIO)
        if any(item.text.strip() for item in self.screen_text):
            used.append(Evidence.PANTALLA)
        return used

    def contains(self, needle: str) -> Evidence | None:
        """Busca un texto en las fuentes para inferir la evidencia de un campo."""
        target = _normalize(needle).strip()
        if len(target) < 3:
            return None
        if self.caption and target in _normalize(self.caption):
            return Evidence.CAPTION
        if self.transcript and target in _normalize(self.transcript.text):
            return Evidence.AUDIO
        if any(target in _normalize(item.text) for item in self.screen_text):
            return Evidence.PANTALLA
        return None

    def to_prompt(self) -> str:
        """Contexto unificado con la fuente de cada dato (RF-13).

        El contenido va escapado y etiquetado: el prompt de sistema indica que
        es dato, nunca instrucción (RA-06).
        """
        blocks: list[str] = []

        if self.metadata:
            meta = self.metadata
            attributes = [
                'plataforma="tiktok"',
                f'url="{_escape(meta.canonical_url or meta.url)}"',
            ]
            if meta.author:
                attributes.append(f'autor="{_escape(meta.author)}"')
            if meta.duration_s is not None:
                attributes.append(f'duracion_s="{meta.duration_s:.1f}"')
            blocks.append(f"<video {' '.join(attributes)} />")

        if self.caption:
            author = self.metadata.author if self.metadata and self.metadata.author else ""
            blocks.append(
                f'<fuente tipo="caption" autor="{_escape(author)}">\n'
                f"{_escape(self.caption)}\n"
                f"</fuente>"
            )

        if self.transcript and self.transcript.text.strip():
            language = self.transcript.language or "desconocido"
            blocks.append(
                f'<fuente tipo="audio" idioma="{_escape(language)}">\n'
                f"{_escape(self.transcript.with_timestamps())}\n"
                f"</fuente>"
            )

        screen_items = [item for item in self.screen_text if item.text.strip()]
        if screen_items:
            lines = "\n".join(
                f"[frame {item.timestamp_s:.1f}s] {item.text}" for item in screen_items
            )
            blocks.append(f'<fuente tipo="pantalla">\n{_escape(lines)}\n</fuente>')

        if not blocks:
            return "<sin_fuentes />"

        return "\n\n".join(blocks)


def strip_tags(value: str) -> str:
    """Utilidad para tests y logs: quita etiquetas del contexto."""
    return re.sub(r"<[^>]+>", "", value)

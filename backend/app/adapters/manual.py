"""Entrada manual: pegar caption, transcripción o texto en pantalla (RF-04).

Es imprescindible, no un extra: si la descarga falla, el pipeline sigue
funcionando con estos archivos. También es la base de las fixtures de las evals.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.domain.content import ScreenText, Transcript, TranscriptSegment, VideoMetadata

_SEGMENT_RE = re.compile(
    r"^\[(?P<start>\d+(?:[.,]\d+)?)s?(?:-(?P<end>\d+(?:[.,]\d+)?)s?)?\]\s*(?P<text>.+)$"
)
_FRAME_RE = re.compile(r"^\[(?P<ts>\d+(?:[.,]\d+)?)s?\]\s*(?P<text>.+)$")


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"no existe el archivo: {path}")
    return path.read_text(encoding="utf-8").strip()


def parse_transcript(text: str, *, language: str | None = None) -> Transcript:
    """Acepta texto plano o líneas con marcas `[0.0s-3.2s] ...`."""
    segments: list[TranscriptSegment] = []
    plain_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if match := _SEGMENT_RE.match(stripped):
            start = float(match.group("start").replace(",", "."))
            raw_end = match.group("end")
            end = float(raw_end.replace(",", ".")) if raw_end else start
            segment_text = match.group("text").strip()
            segments.append(TranscriptSegment(start_s=start, end_s=end, text=segment_text))
            plain_lines.append(segment_text)
        else:
            plain_lines.append(stripped)

    return Transcript(
        text=" ".join(plain_lines).strip(),
        language=language,
        segments=tuple(segments),
    )


def parse_screen_text(text: str) -> tuple[ScreenText, ...]:
    """Acepta líneas con marca de frame `[12.0s] 200 g de harina`."""
    items: list[ScreenText] = []
    for index, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        if match := _FRAME_RE.match(stripped):
            timestamp = float(match.group("ts").replace(",", "."))
            items.append(ScreenText(timestamp_s=timestamp, text=match.group("text").strip()))
        else:
            items.append(ScreenText(timestamp_s=float(index), text=stripped))
    return tuple(items)


def build_metadata(
    *,
    url: str,
    caption: str = "",
    author: str | None = None,
) -> VideoMetadata:
    return VideoMetadata(url=url, author=author, caption=caption)

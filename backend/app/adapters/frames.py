"""Muestreo de frames con ffmpeg y lectura de texto en pantalla (RF-12, F4).

El video se descarga aparte (yt-dlp) y aquí solo se muestrean fotogramas: nunca
se envía el video completo a un modelo (RNF-02).
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from app.config import ConfigError
from app.domain.content import Frame, ScreenText, ScreenTextResult
from app.ports import FrameSampler, ScreenTextReader


class FrameSamplingError(RuntimeError):
    """ffmpeg no pudo extraer fotogramas del video."""


class FFmpegFrameSampler:
    def __init__(
        self,
        *,
        executable: str = "ffmpeg",
        max_frames: int = 60,
        timeout_s: float = 120.0,
    ) -> None:
        self._executable = executable
        self._max_frames = max(1, max_frames)
        self._timeout_s = timeout_s

    async def sample(
        self, video_path: Path, dest_dir: Path, interval_s: float
    ) -> tuple[Frame, ...]:
        return await asyncio.to_thread(self._sample_sync, video_path, dest_dir, interval_s)

    def _sample_sync(
        self, video_path: Path, dest_dir: Path, interval_s: float
    ) -> tuple[Frame, ...]:
        if not video_path.exists():
            raise FileNotFoundError(f"no existe el video: {video_path}")
        if interval_s <= 0:
            raise ValueError("el intervalo de frames debe ser mayor que cero")

        executable = shutil.which(self._executable)
        if executable is None:
            raise ConfigError(
                "falta ffmpeg para muestrear frames. Instálalo y asegúrate de que "
                "esté en el PATH (en Windows: winget install Gyan.FFmpeg)."
            )

        dest_dir.mkdir(parents=True, exist_ok=True)
        pattern = dest_dir / "frame_%04d.jpg"
        command = [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vf",
            f"fps=1/{interval_s:g}",
            "-frames:v",
            str(self._max_frames),
            "-q:v",
            "3",
            str(pattern),
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise FrameSamplingError(
                f"ffmpeg tardó más de {self._timeout_s:.0f} s en muestrear {video_path.name}"
            ) from exc

        if completed.returncode != 0:
            detail = (completed.stderr or "").strip().splitlines()
            reason = detail[-1] if detail else f"código {completed.returncode}"
            raise FrameSamplingError(f"ffmpeg no pudo leer {video_path.name}: {reason}")

        files = sorted(dest_dir.glob("frame_*.jpg"))
        return tuple(
            Frame(path=path, timestamp_s=index * interval_s) for index, path in enumerate(files)
        )


def _clean(text: str) -> str:
    return " ".join(text.split())


class VideoScreenTextReader:
    """Muestrea frames y aplica el lector configurado (OCR o visión)."""

    def __init__(
        self,
        *,
        sampler: FrameSampler,
        reader: ScreenTextReader,
        interval_s: float = 2.0,
        max_frames: int = 24,
        cost_per_frame_usd: float = 0.0,
    ) -> None:
        self._sampler = sampler
        self._reader = reader
        self._interval_s = interval_s
        self._max_frames = max_frames
        self._cost_per_frame_usd = cost_per_frame_usd

    async def read(self, video_path: Path, dest_dir: Path) -> ScreenTextResult:
        frames = await self._sampler.sample(video_path, dest_dir, self._interval_s)
        frames = frames[: self._max_frames]

        items: list[ScreenText] = []
        analyzed = 0
        for frame in frames:
            analyzed += 1
            text = _clean(await self._reader.read(frame))
            if not text:
                continue
            # El texto en pantalla suele repetirse entre frames: se conserva
            # solo cuando cambia respecto al frame anterior.
            if items and items[-1].text.casefold() == text.casefold():
                continue
            items.append(ScreenText(timestamp_s=frame.timestamp_s, text=text))

        return ScreenTextResult(
            items=tuple(items),
            frames_analyzed=analyzed,
            cost_usd=round(analyzed * self._cost_per_frame_usd, 6),
        )

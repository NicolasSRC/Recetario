"""Descarga de metadatos y audio con yt-dlp (RF-02, RF-05, RF-14).

Incluye una comprobación básica de SSRF (RNF-05): la URL debe estar en la
lista de dominios permitidos y resolver a una IP pública.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.config import ConfigError
from app.domain.content import VideoMetadata
from app.domain.urls import normalize_tiktok_url


class VideoDownloadError(RuntimeError):
    """No se pudo obtener el video: privado, bloqueado, red o formato."""


def _assert_public_host(url: str) -> None:
    host = urlparse(url).hostname
    if not host:
        raise VideoDownloadError(f"URL sin host: {url}")

    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise VideoDownloadError(f"no se pudo resolver el host {host}: {exc}") from exc

    for family, _, _, _, sockaddr in addresses:
        if family not in {socket.AF_INET, socket.AF_INET6}:
            continue
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise VideoDownloadError(f"la URL resuelve a una IP interna ({ip}): posible SSRF")


class YtDlpExtractor:
    def __init__(self, *, tmp_dir: Path) -> None:
        self._tmp_dir = tmp_dir

    async def get_metadata(self, url: str) -> VideoMetadata:
        normalized = normalize_tiktok_url(url)
        return await asyncio.to_thread(self._get_metadata_sync, normalized)

    async def download_audio(self, url: str, dest: Path) -> Path:
        normalized = normalize_tiktok_url(url)
        return await asyncio.to_thread(self._download_audio_sync, normalized, dest)

    # ------------------------------------------------------------------ #

    def _get_metadata_sync(self, url: str) -> VideoMetadata:
        _assert_public_host(url)
        info = self._run_ydl(
            url,
            {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
            },
        )

        duration = info.get("duration")
        return VideoMetadata(
            url=url,
            canonical_url=info.get("webpage_url") or url,
            author=info.get("uploader") or info.get("channel"),
            caption=(info.get("description") or info.get("title") or "").strip(),
            duration_s=float(duration) if duration else None,
            hashtags=tuple(info.get("tags") or ()),
        )

    def _download_audio_sync(self, url: str, dest: Path) -> Path:
        _assert_public_host(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._tmp_dir.mkdir(parents=True, exist_ok=True)

        output_template = f"{dest.with_suffix('')}.%(ext)s"
        self._run_ydl(
            url,
            {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "format": "bestaudio/best",
                "outtmpl": output_template,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "m4a",
                        "preferredquality": "128",
                    }
                ],
            },
            download=True,
        )

        candidates = sorted(
            path
            for path in dest.parent.glob(f"{dest.stem}.*")
            if path.suffix not in {".part", ".ytdl"}
        )
        if not candidates:
            raise VideoDownloadError(f"yt-dlp no generó ningún audio para {url}")

        return candidates[0]

    @staticmethod
    def _run_ydl(
        url: str,
        options: dict[str, Any],
        *,
        download: bool = False,
    ) -> dict[str, Any]:
        try:
            from yt_dlp import YoutubeDL
        except ModuleNotFoundError as exc:
            raise ConfigError('falta yt-dlp: pip install -e "backend"') from exc

        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=download)
        except Exception as exc:  # yt-dlp lanza su propia jerarquía de errores
            raise VideoDownloadError(f"no se pudo procesar {url}: {exc}") from exc

        if not isinstance(info, dict):
            raise VideoDownloadError(f"yt-dlp no devolvió metadatos para {url}")

        return info

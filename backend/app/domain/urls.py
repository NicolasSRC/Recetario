"""Validación de URLs de entrada (RF-01, RNF-04)."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

ALLOWED_HOSTS = {
    "tiktok.com",
    "www.tiktok.com",
    "m.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
}


class InvalidUrlError(ValueError):
    """La URL no es un enlace de TikTok aceptable."""


def normalize_tiktok_url(raw: str) -> str:
    """Valida el dominio y devuelve una URL canónica con https.

    Acepta enlaces cortos (`vm.tiktok.com/XXXX`) y largos.
    """
    value = raw.strip()
    if not value:
        raise InvalidUrlError("la URL está vacía")

    if "://" not in value:
        value = f"https://{value}"

    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"}:
        raise InvalidUrlError(f"esquema no permitido: {parsed.scheme}")

    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS and not host.endswith(".tiktok.com"):
        raise InvalidUrlError(f"dominio no permitido: {host or '(vacío)'}")

    path = re.sub(r"/+", "/", parsed.path) or "/"

    return urlunparse(("https", host, path, "", parsed.query, ""))

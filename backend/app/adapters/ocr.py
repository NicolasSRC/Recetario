"""Lectura de texto en pantalla con Tesseract (RF-12, opción OCR).

Es el lector por defecto porque es local y barato. Requiere el binario de
Tesseract y el paquete `pytesseract` (extra `ocr`). Si falta, el agente registra
la llamada como fallida y sigue sin frames.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import ConfigError
from app.domain.content import Frame


class TesseractScreenTextReader:
    def __init__(
        self,
        *,
        lang: str = "spa+eng",
        min_confidence: int = 40,
    ) -> None:
        self._lang = lang
        self._min_confidence = min_confidence

    async def read(self, frame: Frame) -> str:
        return await asyncio.to_thread(self._read_sync, frame.path)

    def _read_sync(self, image_path: Path) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise ConfigError(
                'falta el OCR. Instala Tesseract y ejecuta: pip install -e "backend[ocr]"'
            ) from exc

        try:
            with Image.open(image_path) as image:
                data = pytesseract.image_to_data(
                    image,
                    lang=self._lang,
                    output_type=pytesseract.Output.DICT,
                )
        except Exception as exc:  # el binario falta o no soporta el idioma
            raise ConfigError(
                "Tesseract no pudo leer el frame. Comprueba que el binario está en el "
                f"PATH y que los idiomas '{self._lang}' están instalados: {exc}"
            ) from exc

        words: list[str] = []
        for text, confidence in zip(data.get("text", []), data.get("conf", []), strict=False):
            word = str(text).strip()
            if not word:
                continue
            try:
                score = float(confidence)
            except (TypeError, ValueError):
                continue
            if score >= self._min_confidence:
                words.append(word)

        return " ".join(words)

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

# Palabras de enlace que se conservan aunque sean cortas; el resto de tokens de
# una o dos letras suele ser ruido de texturas y logotipos.
_STOPWORDS = {
    "a",
    "al",
    "con",
    "de",
    "del",
    "el",
    "en",
    "la",
    "las",
    "los",
    "o",
    "para",
    "por",
    "que",
    "se",
    "sin",
    "su",
    "un",
    "una",
    "y",
}
_UNITS = {"g", "kg", "l", "ml", "oz", "lb"}


def _useful_token(token: str) -> bool:
    """Descarta ruido del OCR sin perder cantidades ni unidades."""
    letters = sum(char.isalpha() for char in token)
    digits = sum(char.isdigit() for char in token)
    folded = token.casefold()

    if folded in _STOPWORDS or folded in _UNITS:
        return True
    if letters >= 3:
        return True
    if digits and not letters and digits <= 4:
        return True
    return bool(letters and digits and len(token) <= 6)


class TesseractScreenTextReader:
    def __init__(
        self,
        *,
        lang: str = "spa+eng",
        min_confidence: int = 60,
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
            if score >= self._min_confidence and _useful_token(word):
                words.append(word)

        # Un frame sin una palabra fuerte (o sin al menos dos tokens) suele ser
        # textura, un logotipo o un número suelto: no aporta texto de receta.
        strong = any(sum(char.isalpha() for char in word) >= 3 for word in words)
        distinct = [word for word in words if word.casefold() not in _STOPWORDS]
        if not strong and len(distinct) < 2:
            return ""

        return " ".join(words)

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from PIL import Image

from app.adapters.ocr import TesseractScreenTextReader
from app.config import ConfigError
from app.domain.content import Frame


def _frame(tmp_path: Path) -> Frame:
    path = tmp_path / "frame.jpg"
    Image.new("RGB", (40, 20), "white").save(path)
    return Frame(path=path, timestamp_s=0.0)


class FakePytesseract:
    class Output:
        DICT = "dict"

    @staticmethod
    def image_to_data(image: object, *, lang: str, output_type: str) -> dict[str, list[str]]:
        assert lang == "spa+eng"
        assert output_type == "dict"
        return {
            "text": ["200", "g", "harina", "ruido"],
            "conf": ["95", "90", "80", "5"],
        }


def test_tesseract_conserva_palabras_con_confianza(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "pytesseract", FakePytesseract)
    reader = TesseractScreenTextReader(lang="spa+eng", min_confidence=40)

    text = asyncio.run(reader.read(_frame(tmp_path)))

    assert text == "200 g harina"


def test_sin_pytesseract_avisa_de_la_dependencia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "pytesseract", None)
    reader = TesseractScreenTextReader()

    with pytest.raises(ConfigError, match="OCR"):
        asyncio.run(reader.read(_frame(tmp_path)))


def test_tesseract_descarta_ruido_de_fondo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class NoisyPytesseract(FakePytesseract):
        @staticmethod
        def image_to_data(image: object, *, lang: str, output_type: str) -> dict[str, list[str]]:
            return {
                "text": ["ARROZ", "DE", "FR", "Ta", "Ca", "2229202", "200", "g", "harina"],
                "conf": ["95", "95", "95", "95", "95", "95", "95", "95", "95"],
            }

    monkeypatch.setitem(sys.modules, "pytesseract", NoisyPytesseract)
    reader = TesseractScreenTextReader()

    text = asyncio.run(reader.read(_frame(tmp_path)))

    assert text == "ARROZ DE 200 g harina"


def test_tesseract_descarta_un_digito_aislado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DigitPytesseract(FakePytesseract):
        @staticmethod
        def image_to_data(image: object, *, lang: str, output_type: str) -> dict[str, list[str]]:
            return {"text": ["7"], "conf": ["95"]}

    monkeypatch.setitem(sys.modules, "pytesseract", DigitPytesseract)
    reader = TesseractScreenTextReader()

    assert asyncio.run(reader.read(_frame(tmp_path))) == ""


def test_tesseract_sin_binario_avisa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class BrokenPytesseract(FakePytesseract):
        @staticmethod
        def image_to_data(image: object, *, lang: str, output_type: str) -> dict[str, list[str]]:
            raise RuntimeError("tesseract is not installed")

    monkeypatch.setitem(sys.modules, "pytesseract", BrokenPytesseract)
    reader = TesseractScreenTextReader()

    with pytest.raises(ConfigError, match="Tesseract no pudo leer"):
        asyncio.run(reader.read(_frame(tmp_path)))

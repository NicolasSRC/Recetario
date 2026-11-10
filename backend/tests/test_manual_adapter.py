from __future__ import annotations

from pathlib import Path

import pytest

from app.adapters.manual import parse_screen_text, parse_transcript, read_text


def test_parse_transcript_con_marcas_de_tiempo() -> None:
    transcript = parse_transcript(
        "[0.0s-3.4s] Primero calentamos el aceite.\n[3.4s-7.1s] Añadimos la cebolla."
    )

    assert transcript.text == "Primero calentamos el aceite. Añadimos la cebolla."
    assert len(transcript.segments) == 2
    assert transcript.segments[1].start_s == 3.4
    assert transcript.segments[1].end_s == 7.1


def test_parse_transcript_texto_plano() -> None:
    transcript = parse_transcript("Hervir la pasta durante ocho minutos.")
    assert transcript.segments == ()
    assert transcript.text == "Hervir la pasta durante ocho minutos."


def test_parse_transcript_conserva_idioma() -> None:
    assert parse_transcript("Boil the pasta.", language="en").language == "en"


def test_parse_screen_text_con_frames() -> None:
    items = parse_screen_text("[2.0s] 200 g de harina\n[3.5s] 2 huevos")
    assert len(items) == 2
    assert items[0].timestamp_s == 2.0
    assert items[1].text == "2 huevos"


def test_read_text_de_fixture(fixtures_dir: Path) -> None:
    text = read_text(fixtures_dir / "caption_01.txt")
    assert "pollo al limón" in text.lower()


def test_read_text_inexistente(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_text(tmp_path / "no-existe.txt")

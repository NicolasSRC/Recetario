from __future__ import annotations

import json
from pathlib import Path

from app.cli import EXIT_CONFIG, EXIT_OK, main


def test_parse_normaliza_un_ingrediente(capsys: object) -> None:
    assert main(["parse", "1 1/2 tazas de harina integral"]) == EXIT_OK

    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output["quantity"] == "1.5"
    assert output["unit"] == "taza"
    assert output["name"] == "harina integral"


def test_dry_run_muestra_el_contexto(fixtures_dir: Path, capsys: object) -> None:
    code = main(
        [
            "ingest",
            "--caption-file",
            str(fixtures_dir / "caption_01.txt"),
            "--dry-run",
        ]
    )

    assert code == EXIT_OK
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert '<fuente tipo="caption"' in output
    assert "pollo al limón" in output.lower()


def test_sin_entrada_devuelve_error_de_configuracion(capsys: object) -> None:
    assert main(["ingest"]) == EXIT_CONFIG
    assert "error de configuración" in capsys.readouterr().err  # type: ignore[attr-defined]

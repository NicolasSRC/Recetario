"""Interfaz de línea de comandos de F1.

Ejemplos:
    recetario parse "1 1/2 tazas de harina"
    recetario ingest --caption-file fixtures/caption_01.txt --dry-run
    recetario ingest --caption-file fixtures/caption_01.txt --out receta.json
    recetario ingest --url https://vm.tiktok.com/XXXX/
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from app.adapters.manual import build_metadata, parse_screen_text, parse_transcript, read_text
from app.adapters.openai_llm import OpenAIRecipeLLM
from app.adapters.opencode_llm import OpenCodeLLM, OpenCodeQuotaError
from app.adapters.whisper_transcriber import WhisperTranscriber
from app.adapters.ytdlp_extractor import VideoDownloadError, YtDlpExtractor
from app.config import ConfigError, Settings, get_settings
from app.domain.content import RecipeContext
from app.domain.units import parse_ingredient
from app.domain.validation import NotARecipeError
from app.pipeline.extract_recipe import ExtractionFailed, extract_recipe
from app.ports.llm import RecipeLLM

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CONFIG = 2
EXIT_NOT_A_RECIPE = 3
EXIT_QUOTA = 4


def build_llm(settings: Settings, model_override: str | None = None) -> tuple[RecipeLLM, str]:
    """Elige el proveedor según configuración (RA-07, RNF-09)."""
    if settings.llm_provider == "opencode":
        model = model_override or settings.opencode_model
        return (
            OpenCodeLLM(
                model=model,
                agent=settings.opencode_agent,
                executable=settings.opencode_executable,
                timeout_s=settings.opencode_timeout_s,
            ),
            model,
        )

    model = model_override or settings.llm_model
    return (
        OpenAIRecipeLLM(
            api_key=settings.require_api_key(),
            model=model,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
        ),
        model,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recetario",
        description="Convierte un video de TikTok en una receta estructurada.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Extrae una receta de una URL o de texto manual")
    ingest.add_argument("--url", help="URL de TikTok (corta o larga)")
    ingest.add_argument("--caption-file", type=Path, help="Archivo con el caption (RF-04)")
    ingest.add_argument("--transcript-file", type=Path, help="Archivo con la transcripción")
    ingest.add_argument("--screen-text-file", type=Path, help="Archivo con el texto en pantalla")
    ingest.add_argument("--source-url", default="", help="URL original cuando la entrada es manual")
    ingest.add_argument("--author", default=None, help="Autor del video (para citarlo)")
    ingest.add_argument("--model", default=None, help="Modelo a usar (por defecto el de .env)")
    ingest.add_argument("--out", type=Path, default=None, help="Guardar el JSON en este archivo")
    ingest.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar el contexto que se enviaría al modelo, sin llamarlo",
    )

    parse = subparsers.add_parser("parse", help="Normaliza un ingrediente escrito a mano")
    parse.add_argument("text", help='Ej.: "1 1/2 tazas de harina integral"')

    return parser


def _configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):
        reconfigure(encoding="utf-8", errors="replace")


def _manual_context(args: argparse.Namespace) -> RecipeContext:
    caption = read_text(args.caption_file) if args.caption_file else ""
    transcript = parse_transcript(read_text(args.transcript_file)) if args.transcript_file else None
    screen_text = (
        parse_screen_text(read_text(args.screen_text_file)) if args.screen_text_file else ()
    )

    metadata = build_metadata(
        url=args.source_url or "manual://captura",
        caption=caption,
        author=args.author,
    )
    return RecipeContext(metadata=metadata, transcript=transcript, screen_text=screen_text)


async def _url_context(args: argparse.Namespace) -> RecipeContext:
    settings = get_settings()
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)

    extractor = YtDlpExtractor(tmp_dir=settings.tmp_dir)
    metadata = await extractor.get_metadata(args.url)

    work_dir = Path(tempfile.mkdtemp(prefix="recetario-", dir=settings.tmp_dir))
    try:
        audio_path = await extractor.download_audio(args.url, work_dir / "audio.m4a")
        transcriber = WhisperTranscriber(
            model_size=settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        transcript = await transcriber.transcribe(audio_path)
    finally:
        # RF-14: el video y el audio temporales se borran al terminar.
        shutil.rmtree(work_dir, ignore_errors=True)

    return RecipeContext(metadata=metadata, transcript=transcript)


async def _run_ingest(args: argparse.Namespace) -> int:
    if args.url:
        context = await _url_context(args)
    elif args.caption_file or args.transcript_file or args.screen_text_file:
        context = _manual_context(args)
    else:
        raise ConfigError("indica --url o al menos un archivo de entrada manual")

    if args.dry_run:
        print(context.to_prompt())
        return EXIT_OK

    settings = get_settings()
    llm, model = build_llm(settings, args.model)

    recipe = await extract_recipe(
        context,
        llm,
        max_retries=settings.max_validation_retries,
        model_name=model,
    )

    payload = recipe.model_dump_json(indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
        print(f"receta guardada en {args.out}", file=sys.stderr)
    else:
        print(payload)

    print(
        f"estado={recipe.status.value} confianza={recipe.extraction.confidence:.2f} "
        f"flags={len(recipe.extraction.flags)}",
        file=sys.stderr,
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "parse":
            parsed = parse_ingredient(args.text)
            print(json.dumps(asdict(parsed), ensure_ascii=False, indent=2, default=str))
            return EXIT_OK

        return asyncio.run(_run_ingest(args))
    except NotARecipeError as exc:
        print(f"no es una receta: {exc.reason}", file=sys.stderr)
        return EXIT_NOT_A_RECIPE
    except OpenCodeQuotaError as exc:
        detail = ""
        if exc.retry_after_s:
            minutes = exc.retry_after_s / 60
            detail = f" Reintenta en ~{minutes:.0f} min o cambia de proveedor."
        print(f"cuota del modelo agotada: {exc}.{detail}", file=sys.stderr)
        return EXIT_QUOTA
    except ConfigError as exc:
        print(f"error de configuración: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except ExtractionFailed as exc:
        print(f"extracción fallida: {exc}", file=sys.stderr)
        return EXIT_FAILED
    except (VideoDownloadError, FileNotFoundError) as exc:
        print(f"error de entrada: {exc}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())

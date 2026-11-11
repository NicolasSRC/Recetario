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

from app.adapters.frames import FFmpegFrameSampler
from app.adapters.manual import build_metadata, parse_screen_text, parse_transcript, read_text
from app.adapters.opencode_llm import OpenCodeQuotaError
from app.adapters.whisper_transcriber import WhisperTranscriber
from app.adapters.ytdlp_extractor import VideoDownloadError, YtDlpExtractor
from app.config import ConfigError, Settings, get_settings
from app.domain.agent import AgentLimits, AgentTrace
from app.domain.content import RecipeContext, ScreenTextResult, Transcript, VideoMetadata
from app.domain.schemas import Recipe
from app.domain.units import parse_ingredient
from app.domain.validation import NotARecipeError
from app.llm_factory import build_llm
from app.pipeline.agent import AgentTools, BudgetExceeded, RecipeAgent
from app.pipeline.extract_recipe import ExtractionFailed, extract_recipe
from app.ports.llm import RecipeLLM
from app.vision_factory import build_frame_reader, build_video_screen_text_reader

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CONFIG = 2
EXIT_NOT_A_RECIPE = 3
EXIT_QUOTA = 4


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
    ingest.add_argument(
        "--no-frames",
        action="store_true",
        help="No leer texto en pantalla: el agente se salta los frames (F4)",
    )
    ingest.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Segundos entre frames (por defecto RECETARIO_FRAME_INTERVAL_S)",
    )
    ingest.add_argument("--out", type=Path, default=None, help="Guardar el JSON en este archivo")
    ingest.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar el contexto que se enviaría al modelo, sin llamarlo",
    )

    frames = subparsers.add_parser(
        "frames", help="Muestrea un video local y lee su texto en pantalla (RF-12)"
    )
    frames.add_argument("--video", type=Path, required=True, help="Archivo de video local")
    frames.add_argument("--interval", type=float, default=None, help="Segundos entre frames")
    frames.add_argument(
        "--reader",
        choices=["tesseract", "vision"],
        default=None,
        help="Lector a usar (por defecto el de .env)",
    )
    frames.add_argument("--out", type=Path, default=None, help="Guardar el texto en este archivo")

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


def _settings_for(args: argparse.Namespace) -> Settings:
    settings = get_settings()
    updates: dict[str, object] = {}
    if getattr(args, "no_frames", False):
        updates["frames_enabled"] = False
    if getattr(args, "interval", None) is not None:
        updates["frame_interval_s"] = args.interval
    if getattr(args, "reader", None):
        updates["screen_text_reader"] = args.reader
    return settings.model_copy(update=updates) if updates else settings


async def _url_recipe(
    args: argparse.Namespace,
    settings: Settings,
    llm: RecipeLLM,
    model: str,
) -> Recipe:
    """Ingesta por URL con el agente: decide si transcribe y si lee frames."""
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    extractor = YtDlpExtractor(tmp_dir=settings.tmp_dir)
    transcriber = WhisperTranscriber(
        model_size=settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    work_dir = Path(tempfile.mkdtemp(prefix="recetario-", dir=settings.tmp_dir))

    try:
        screen_reader = build_video_screen_text_reader(settings)
    except ConfigError as exc:
        screen_reader = None
        print(f"aviso: frames deshabilitados ({exc})", file=sys.stderr)

    async def get_metadata() -> VideoMetadata:
        return await extractor.get_metadata(args.url)

    async def transcribe_audio() -> Transcript:
        audio_path = await extractor.download_audio(args.url, work_dir / "audio.m4a")
        return await transcriber.transcribe(audio_path)

    async def extract_frames() -> ScreenTextResult:
        if screen_reader is None:
            raise ConfigError("no hay lector de texto en pantalla configurado")
        video_path = await extractor.download_video(args.url, work_dir / "video.mp4")
        return await screen_reader.read(video_path, work_dir / "frames")

    trace = AgentTrace(
        limits=AgentLimits(
            max_steps=settings.max_agent_steps,
            max_cost_usd=settings.max_cost_usd_per_video,
        )
    )
    agent = RecipeAgent(
        AgentTools(
            get_metadata=get_metadata,
            transcribe_audio=transcribe_audio,
            extract_frames=extract_frames if screen_reader is not None else None,
        ),
        llm,
        limits=trace.limits,
        trace=trace,
        max_retries=settings.max_validation_retries,
        model_name=model,
        extraction_cost_usd=settings.llm_cost_usd_per_extraction,
        frame_interval_s=settings.frame_interval_s,
    )

    try:
        result = await agent.run()
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    print(
        f"agente: {trace.steps} pasos, ${trace.total_cost_usd:.4f}"
        + (f", detenido por {trace.stopped_reason}" if trace.stopped_reason else ""),
        file=sys.stderr,
    )
    for call in trace.calls:
        mark = "ok" if call.ok else "falló"
        print(f"  [{call.step}] {call.tool} ({mark}): {call.output}", file=sys.stderr)
    return result.recipe


async def _run_frames(args: argparse.Namespace) -> int:
    settings = _settings_for(args)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)

    reader = build_frame_reader(settings)
    if reader is None:
        raise ConfigError("la lectura de texto en pantalla está deshabilitada")

    sampler = FFmpegFrameSampler(max_frames=settings.max_frames_per_video)
    work_dir = Path(tempfile.mkdtemp(prefix="recetario-frames-", dir=settings.tmp_dir))
    try:
        frames = await sampler.sample(args.video, work_dir, settings.frame_interval_s)
        lines: list[str] = []
        for frame in frames:
            text = (await reader.read(frame)).strip()
            if text:
                lines.append(f"[{frame.timestamp_s:.1f}s] {text}")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    output = "\n".join(lines)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
        print(f"texto guardado en {args.out}", file=sys.stderr)
    else:
        print(output)

    print(
        f"{len(frames)} frames muestreados, {len(lines)} con texto "
        f"(lector={settings.screen_text_reader})",
        file=sys.stderr,
    )
    return EXIT_OK


async def _run_ingest(args: argparse.Namespace) -> int:
    settings = _settings_for(args)

    if args.url and not args.dry_run:
        llm, model = build_llm(settings, args.model)
        recipe = await _url_recipe(args, settings, llm, model)
    else:
        if args.url:
            context = await _url_context(args)
        elif args.caption_file or args.transcript_file or args.screen_text_file:
            context = _manual_context(args)
        else:
            raise ConfigError("indica --url o al menos un archivo de entrada manual")

        if args.dry_run:
            print(context.to_prompt())
            return EXIT_OK

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
        if args.command == "frames":
            return asyncio.run(_run_frames(args))

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
    except BudgetExceeded as exc:
        print(f"el agente agotó su presupuesto: {exc}", file=sys.stderr)
        return EXIT_FAILED
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

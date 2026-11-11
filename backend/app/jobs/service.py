"""Trabajos de ingesta en segundo plano (F2).

Un trabajo recorre siempre las mismas etapas: descargar, transcribir, extraer y
guardar. La API solo crea la fila y lo lanza; aquí vive la lógica.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.manual import build_metadata, parse_screen_text, parse_transcript
from app.adapters.opencode_llm import OpenCodeQuotaError
from app.adapters.whisper_transcriber import WhisperTranscriber
from app.adapters.ytdlp_extractor import VideoDownloadError, YtDlpExtractor
from app.config import ConfigError, Settings
from app.db import repository
from app.db.models import JobEventRow, JobRow
from app.domain.agent import AgentLimits, AgentTrace
from app.domain.content import RecipeContext, ScreenTextResult, Transcript, VideoMetadata
from app.domain.schemas import Recipe
from app.domain.urls import InvalidUrlError, normalize_tiktok_url
from app.domain.validation import BusinessRuleError, NotARecipeError
from app.llm_factory import build_llm
from app.pipeline.agent import AgentResult, AgentTools, RecipeAgent
from app.pipeline.extract_recipe import ExtractionFailed, extract_recipe
from app.ports.llm import RecipeLLM
from app.vision_factory import build_video_screen_text_reader

logger = logging.getLogger(__name__)

LLMFactory = Callable[[Settings], tuple[RecipeLLM, str]]
SessionFactory = sessionmaker[Session]


class JobStatus(StrEnum):
    EN_COLA = "en_cola"
    PROCESANDO = "procesando"
    LISTA = "lista"
    FALLIDA = "fallida"
    CANCELADA = "cancelada"


class JobStage(StrEnum):
    DESCARGANDO = "descargando"
    TRANSCRIBIENDO = "transcribiendo"
    LEYENDO_PANTALLA = "leyendo_pantalla"
    EXTRAYENDO = "extrayendo"
    GUARDANDO = "guardando"


class JobErrorCode(StrEnum):
    URL_INVALIDA = "url_invalida"
    DESCARGA_BLOQUEADA = "descarga_bloqueada"
    TRANSCRIPCION_VACIA = "transcripcion_vacia"
    ESQUEMA_INVALIDO = "esquema_invalido"
    CUOTA_AGOTADA = "cuota_agotada"
    NO_ES_RECETA = "no_es_receta"
    ERROR_INTERNO = "error_interno"


class JobCancelled(RuntimeError):
    """El usuario canceló el trabajo mientras se procesaba."""


def classify_error(exc: BaseException) -> JobErrorCode:
    """Traduce la excepción del pipeline a un código estable para la UI."""
    if isinstance(exc, ExtractionFailed) and exc.last_error is not None:
        exc = exc.last_error

    if isinstance(exc, OpenCodeQuotaError):
        return JobErrorCode.CUOTA_AGOTADA
    if isinstance(exc, NotARecipeError):
        return JobErrorCode.NO_ES_RECETA
    if isinstance(exc, InvalidUrlError):
        return JobErrorCode.URL_INVALIDA
    if isinstance(exc, VideoDownloadError):
        return JobErrorCode.DESCARGA_BLOQUEADA
    if isinstance(exc, (ValidationError, BusinessRuleError)):
        return JobErrorCode.ESQUEMA_INVALIDO
    if isinstance(exc, ValueError) and "transcrip" in str(exc).lower():
        return JobErrorCode.TRANSCRIPCION_VACIA
    if isinstance(exc, ConfigError):
        return JobErrorCode.ERROR_INTERNO
    return JobErrorCode.ERROR_INTERNO


def error_message(exc: BaseException) -> str:
    original = exc
    if isinstance(exc, ExtractionFailed) and exc.last_error is not None:
        exc = exc.last_error

    if isinstance(exc, OpenCodeQuotaError) and exc.retry_after_s:
        minutes = exc.retry_after_s / 60
        return f"cuota del modelo agotada; reintenta en ~{minutes:.0f} min"
    if isinstance(original, ExtractionFailed):
        return f"no se pudo extraer una receta válida: {exc}"
    return str(exc) or exc.__class__.__name__


# --------------------------------------------------------------------------- #
# Acceso a la fila del trabajo


def _load(session_factory: SessionFactory, job_id: str) -> tuple[str, str | None, dict[str, Any]]:
    with session_factory() as session:
        job = session.get(JobRow, job_id)
        if job is None:
            raise LookupError(f"no existe el trabajo {job_id}")
        if job.status == JobStatus.CANCELADA:
            raise JobCancelled()
        return job.kind, job.source_url, dict(job.payload or {})


def _set_stage(session_factory: SessionFactory, job_id: str, stage: JobStage) -> None:
    """Cambia la etapa; si el trabajo fue cancelado, corta el procesamiento."""
    with session_factory() as session:
        job = session.get(JobRow, job_id)
        if job is None:
            raise LookupError(f"no existe el trabajo {job_id}")
        if job.status == JobStatus.CANCELADA:
            raise JobCancelled()
        job.stage = stage.value
        session.commit()


def _finish(
    session_factory: SessionFactory,
    job_id: str,
    *,
    recipe: Recipe,
    duration_s: float,
    cost_usd: float = 0.0,
) -> None:
    with session_factory() as session:
        job = session.get(JobRow, job_id)
        if job is None:
            return
        job.status = JobStatus.LISTA.value
        job.stage = None
        job.error_code = None
        job.error_message = None
        job.recipe_id = recipe.id
        job.duration_s = duration_s
        job.cost_usd = cost_usd
        session.commit()


def _fail(
    session_factory: SessionFactory,
    job_id: str,
    exc: BaseException,
    *,
    duration_s: float,
    cost_usd: float = 0.0,
) -> None:
    code = classify_error(exc)
    with session_factory() as session:
        job = session.get(JobRow, job_id)
        if job is None or job.status == JobStatus.CANCELADA:
            return
        job.status = JobStatus.FALLIDA.value
        job.stage = None
        job.error_code = code.value
        job.error_message = error_message(exc)[:2000]
        job.duration_s = duration_s
        job.cost_usd = cost_usd
        session.commit()


def _mark_cancelled(session_factory: SessionFactory, job_id: str) -> None:
    with session_factory() as session:
        job = session.get(JobRow, job_id)
        if job is None:
            return
        job.status = JobStatus.CANCELADA.value
        job.stage = None
        session.commit()


# --------------------------------------------------------------------------- #
# Construcción del contexto


def _save_trace(
    session_factory: SessionFactory,
    job_id: str,
    trace: AgentTrace | None,
) -> None:
    """Persiste las llamadas del agente en `job_events` (RA-04)."""
    if trace is None:
        return

    with session_factory() as session:
        session.execute(delete(JobEventRow).where(JobEventRow.job_id == job_id))
        for call in trace.calls:
            session.add(
                JobEventRow(
                    job_id=job_id,
                    tool=call.tool,
                    input={"step": call.step, **call.input},
                    output={"text": call.output, "ok": call.ok, "error": call.error},
                    duration_ms=round(call.duration_s * 1000),
                    cost_usd=call.cost_usd,
                )
            )
        session.commit()


async def _run_url_agent(
    session_factory: SessionFactory,
    job_id: str,
    url: str,
    settings: Settings,
    llm: RecipeLLM,
    model: str,
    trace: AgentTrace,
    save_recipe: Callable[[Recipe], Awaitable[Recipe]],
) -> AgentResult:
    """Prepara las herramientas reales (yt-dlp, whisper, frames) y ejecuta el agente."""
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
        trace.decision(f"frames deshabilitados: {exc}")

    async def get_metadata() -> VideoMetadata:
        _set_stage(session_factory, job_id, JobStage.DESCARGANDO)
        return await extractor.get_metadata(url)

    async def transcribe_audio() -> Transcript:
        _set_stage(session_factory, job_id, JobStage.TRANSCRIBIENDO)
        audio_path = await extractor.download_audio(url, work_dir / "audio.m4a")
        return await transcriber.transcribe(audio_path)

    async def extract_frames() -> ScreenTextResult:
        if screen_reader is None:
            raise ConfigError("no hay lector de texto en pantalla configurado")
        _set_stage(session_factory, job_id, JobStage.LEYENDO_PANTALLA)
        video_path = await extractor.download_video(url, work_dir / "video.mp4")
        return await screen_reader.read(video_path, work_dir / "frames")

    tools = AgentTools(
        get_metadata=get_metadata,
        transcribe_audio=transcribe_audio,
        extract_frames=extract_frames if screen_reader is not None else None,
        save_recipe=save_recipe,
        before_extract=lambda: _set_stage(session_factory, job_id, JobStage.EXTRAYENDO),
    )
    agent = RecipeAgent(
        tools,
        llm,
        limits=AgentLimits(
            max_steps=settings.max_agent_steps,
            max_cost_usd=settings.max_cost_usd_per_video,
        ),
        trace=trace,
        max_retries=settings.max_validation_retries,
        model_name=model,
        extraction_cost_usd=settings.llm_cost_usd_per_extraction,
        frame_interval_s=settings.frame_interval_s,
        fatal_exceptions=(JobCancelled,),
    )

    try:
        return await agent.run()
    finally:
        # RF-14: el video, el audio y los frames temporales se borran al terminar.
        shutil.rmtree(work_dir, ignore_errors=True)


def _context_from_text(job_id: str, payload: dict[str, Any]) -> RecipeContext:
    caption = str(payload.get("caption") or "")
    transcript_text = str(payload.get("transcript") or "")
    screen_text = str(payload.get("screen_text") or "")

    metadata = build_metadata(
        url=f"manual://{job_id}",
        caption=caption,
        author=payload.get("author"),
    )
    return RecipeContext(
        metadata=metadata,
        transcript=parse_transcript(transcript_text) if transcript_text.strip() else None,
        screen_text=parse_screen_text(screen_text) if screen_text.strip() else (),
    )


# --------------------------------------------------------------------------- #
# Procesamiento


async def process_job(
    job_id: str,
    session_factory: SessionFactory,
    settings: Settings,
    llm_factory: LLMFactory = build_llm,
) -> None:
    """Ejecuta un trabajo de principio a fin. Nunca propaga errores del pipeline."""
    started = time.monotonic()
    trace: AgentTrace | None = None

    def save_recipe(recipe: Recipe) -> Recipe:
        _set_stage(session_factory, job_id, JobStage.GUARDANDO)
        with session_factory() as session:
            saved, _created = repository.save_recipe(session, recipe)
        return saved

    try:
        kind, source_url, payload = _load(session_factory, job_id)
        _set_stage(
            session_factory,
            job_id,
            JobStage.DESCARGANDO if kind == "url" else JobStage.EXTRAYENDO,
        )

        llm, model = llm_factory(settings)

        if kind == "url":
            if not source_url:
                raise InvalidUrlError("el trabajo no tiene URL de origen")
            trace = AgentTrace(
                limits=AgentLimits(
                    max_steps=settings.max_agent_steps,
                    max_cost_usd=settings.max_cost_usd_per_video,
                )
            )

            async def save_async(recipe: Recipe) -> Recipe:
                return await asyncio.to_thread(save_recipe, recipe)

            result = await _run_url_agent(
                session_factory,
                job_id,
                normalize_tiktok_url(source_url),
                settings,
                llm,
                model,
                trace,
                save_async,
            )
            recipe = result.recipe
        else:
            context = _context_from_text(job_id, payload)
            recipe = await extract_recipe(
                context,
                llm,
                max_retries=settings.max_validation_retries,
                model_name=model,
            )
            recipe = await asyncio.to_thread(save_recipe, recipe)

        _save_trace(session_factory, job_id, trace)
        _finish(
            session_factory,
            job_id,
            recipe=recipe,
            duration_s=time.monotonic() - started,
            cost_usd=trace.total_cost_usd if trace else 0.0,
        )
    except JobCancelled:
        _save_trace(session_factory, job_id, trace)
        _mark_cancelled(session_factory, job_id)
    except Exception as exc:  # el pipeline falla de muchas formas posibles
        logger.warning("trabajo %s falló: %s", job_id, exc, exc_info=True)
        _save_trace(session_factory, job_id, trace)
        _fail(
            session_factory,
            job_id,
            exc,
            duration_s=time.monotonic() - started,
            cost_usd=trace.total_cost_usd if trace else 0.0,
        )

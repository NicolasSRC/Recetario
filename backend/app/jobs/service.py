"""Trabajos de ingesta en segundo plano (F2).

Un trabajo recorre siempre las mismas etapas: descargar, transcribir, extraer y
guardar. La API solo crea la fila y lo lanza; aquí vive la lógica.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.manual import build_metadata, parse_screen_text, parse_transcript
from app.adapters.opencode_llm import OpenCodeQuotaError
from app.adapters.whisper_transcriber import WhisperTranscriber
from app.adapters.ytdlp_extractor import VideoDownloadError, YtDlpExtractor
from app.config import ConfigError, Settings
from app.db import repository
from app.db.models import JobRow
from app.domain.content import RecipeContext
from app.domain.schemas import Recipe
from app.domain.urls import InvalidUrlError, normalize_tiktok_url
from app.domain.validation import BusinessRuleError, NotARecipeError
from app.llm_factory import build_llm
from app.pipeline.extract_recipe import ExtractionFailed, extract_recipe
from app.ports.llm import RecipeLLM

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
        session.commit()


def _fail(
    session_factory: SessionFactory,
    job_id: str,
    exc: BaseException,
    *,
    duration_s: float,
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


async def _context_from_url(
    session_factory: SessionFactory,
    job_id: str,
    url: str,
    settings: Settings,
) -> RecipeContext:
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    extractor = YtDlpExtractor(tmp_dir=settings.tmp_dir)

    metadata = await extractor.get_metadata(url)
    _set_stage(session_factory, job_id, JobStage.TRANSCRIBIENDO)

    work_dir = Path(tempfile.mkdtemp(prefix="recetario-", dir=settings.tmp_dir))
    try:
        audio_path = await extractor.download_audio(url, work_dir / "audio.m4a")
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

    try:
        kind, source_url, payload = _load(session_factory, job_id)
        _set_stage(
            session_factory,
            job_id,
            JobStage.DESCARGANDO if kind == "url" else JobStage.EXTRAYENDO,
        )

        if kind == "url":
            if not source_url:
                raise InvalidUrlError("el trabajo no tiene URL de origen")
            context = await _context_from_url(
                session_factory, job_id, normalize_tiktok_url(source_url), settings
            )
            _set_stage(session_factory, job_id, JobStage.EXTRAYENDO)
        else:
            context = _context_from_text(job_id, payload)

        llm, model = llm_factory(settings)
        recipe = await extract_recipe(
            context,
            llm,
            max_retries=settings.max_validation_retries,
            model_name=model,
        )

        _set_stage(session_factory, job_id, JobStage.GUARDANDO)
        with session_factory() as session:
            saved, _created = repository.save_recipe(session, recipe)

        _finish(
            session_factory,
            job_id,
            recipe=saved,
            duration_s=time.monotonic() - started,
        )
    except JobCancelled:
        _mark_cancelled(session_factory, job_id)
    except Exception as exc:  # el pipeline falla de muchas formas posibles
        logger.warning("trabajo %s falló: %s", job_id, exc, exc_info=True)
        _fail(session_factory, job_id, exc, duration_s=time.monotonic() - started)

"""Tarea Celery que ejecuta un trabajo de ingesta (F5).

La tarea es idempotente por partida doble:

1. `process_job` reclama el trabajo con un UPDATE atómico; si otro worker ya lo
   tomó, no hace nada.
2. Solo se reintentan errores transitorios, con espera exponencial (RP-01).
"""

from __future__ import annotations

import asyncio
import logging

from celery import Task

from app.config import Settings, get_settings
from app.db.session import create_db_engine, create_session_factory, init_db
from app.jobs.celery_app import celery_app
from app.jobs.service import (
    RETRYABLE_ERROR_CODES,
    JobErrorCode,
    SessionFactory,
    _requeue,
    process_job,
)

logger = logging.getLogger(__name__)

_session_factory: SessionFactory | None = None
_session_url: str | None = None


def _sessions(settings: Settings) -> SessionFactory:
    """Motor por proceso de worker; se reutiliza entre tareas."""
    global _session_factory, _session_url
    if _session_factory is None or _session_url != settings.database_url:
        engine = create_db_engine(settings.database_url)
        init_db(engine)
        _session_factory = create_session_factory(engine)
        _session_url = settings.database_url
    return _session_factory


def retry_countdown(settings: Settings, attempt: int) -> float:
    """Espera exponencial con tope (RP-01). `attempt` empieza en 0."""
    return min(
        settings.job_retry_backoff_s * (2**attempt),
        settings.job_retry_backoff_max_s,
    )


@celery_app.task(bind=True, name="recetario.process_job")
def process_job_task(self: Task, job_id: str) -> str | None:
    settings = get_settings()
    factory = _sessions(settings)

    code: JobErrorCode | None = asyncio.run(process_job(job_id, factory, settings))

    if code in RETRYABLE_ERROR_CODES and self.request.retries < settings.job_max_retries:
        _requeue(factory, job_id, code)
        countdown = retry_countdown(settings, self.request.retries)
        logger.warning(
            "trabajo %s se reintenta en %.0f s (intento %d, causa %s)",
            job_id,
            countdown,
            self.request.retries + 1,
            code,
        )
        raise self.retry(countdown=countdown)

    return code.value if code is not None else None

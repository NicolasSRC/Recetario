"""Ejecución de trabajos fuera del ciclo de la petición HTTP.

En desarrollo local basta un hilo por trabajo. En Docker se usa Celery con
Redis (`RECETARIO_JOB_RUNNER=celery`); la API solo cambia de implementación del
puerto `JobRunner`.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Protocol

from app.config import Settings
from app.jobs.service import LLMFactory, SessionFactory, process_job
from app.llm_factory import build_llm

logger = logging.getLogger(__name__)


class JobRunner(Protocol):
    def submit(self, job_id: str) -> None: ...


class ThreadJobRunner:
    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        settings: Settings,
        llm_factory: LLMFactory = build_llm,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._llm_factory = llm_factory

    def submit(self, job_id: str) -> None:
        thread = threading.Thread(
            target=self._run,
            args=(job_id,),
            name=f"recetario-job-{job_id[:8]}",
            daemon=True,
        )
        thread.start()

    def _run(self, job_id: str) -> None:
        try:
            asyncio.run(
                process_job(
                    job_id,
                    self._session_factory,
                    self._settings,
                    self._llm_factory,
                )
            )
        except Exception:  # el hilo no debe morir en silencio
            logger.exception("el hilo del trabajo %s terminó con error", job_id)


def _enqueue_in_celery(job_id: str) -> None:
    # Import perezoso: Celery solo es obligatorio cuando se usa esta cola.
    from app.jobs.tasks import process_job_task

    process_job_task.delay(job_id)


class CeleryJobRunner:
    """Publica el trabajo en la cola; el worker lo procesa."""

    def __init__(self, send: Callable[[str], None] | None = None) -> None:
        self._send = send or _enqueue_in_celery

    def submit(self, job_id: str) -> None:
        self._send(job_id)


def build_job_runner(
    settings: Settings,
    session_factory: SessionFactory,
    llm_factory: LLMFactory = build_llm,
) -> JobRunner:
    if settings.job_runner == "celery":
        return CeleryJobRunner()
    return ThreadJobRunner(
        session_factory=session_factory,
        settings=settings,
        llm_factory=llm_factory,
    )

"""Ejecución de trabajos fuera del ciclo de la petición HTTP.

Para el MVP basta un hilo por trabajo: el recetario es de un solo usuario y los
trabajos son pocos. Cuando haya varios workers, esta interfaz se sustituye por
una cola real (RQ, Dramatiq o similar) sin tocar la API.
"""

from __future__ import annotations

import asyncio
import logging
import threading
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

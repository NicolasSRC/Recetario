"""Aplicación Celery para la cola de ingesta (F5).

El worker se arranca con:

    celery -A app.jobs.celery_app:celery_app worker --loglevel=INFO

La API solo publica el id del trabajo; el worker abre su propia sesión de base
de datos y ejecuta el mismo `process_job` que usa el runner de hilos.
"""

from __future__ import annotations

from celery import Celery

from app.config import Settings, get_settings


def create_celery(settings: Settings | None = None) -> Celery:
    settings = settings or get_settings()
    app = Celery(
        "recetario",
        broker=settings.broker_url,
        backend=settings.result_backend,
        include=["app.jobs.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        broker_connection_retry_on_startup=True,
        # Un trabajo a la vez por worker: descargar y transcribir ya consume CPU
        # y memoria; además evita reentregas masivas si el worker se cae.
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_reject_on_worker_lost=True,
        result_expires=3600,
    )
    return app


celery_app = create_celery()

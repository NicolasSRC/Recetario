from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.config import Settings
from app.db.models import JobRow
from app.db.session import create_db_engine, create_session_factory, init_db
from app.jobs.runner import CeleryJobRunner, ThreadJobRunner, build_job_runner
from app.jobs.service import (
    RETRYABLE_ERROR_CODES,
    JobErrorCode,
    JobStatus,
    _claim,
    _requeue,
    process_job,
)


def _sessions() -> Any:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    return create_session_factory(engine)


def _job(factory: Any, **values: Any) -> str:
    data: dict[str, Any] = {"kind": "texto", "status": JobStatus.EN_COLA.value}
    data.update(values)
    with factory() as session:
        job = JobRow(**data)
        session.add(job)
        session.commit()
        return job.id


def test_claim_solo_gana_un_worker() -> None:
    factory = _sessions()
    job_id = _job(factory)

    assert _claim(factory, job_id) is True
    assert _claim(factory, job_id) is False

    with factory() as session:
        assert session.get(JobRow, job_id).status == JobStatus.PROCESANDO.value


def test_claim_ignora_trabajo_terminado() -> None:
    factory = _sessions()
    job_id = _job(factory, status=JobStatus.LISTA.value)

    assert _claim(factory, job_id) is False


def test_process_job_ignora_una_entrega_duplicada() -> None:
    factory = _sessions()
    job_id = _job(factory, status=JobStatus.PROCESANDO.value)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    def fail_llm(_settings: Settings) -> Any:
        pytest.fail("no debe llamarse al LLM si otro worker ya tomó el trabajo")

    assert asyncio.run(process_job(job_id, factory, settings, fail_llm)) is None


def test_requeue_devuelve_a_cola() -> None:
    factory = _sessions()
    job_id = _job(factory, status=JobStatus.PROCESANDO.value)

    _requeue(factory, job_id, JobErrorCode.ERROR_INTERNO)

    with factory() as session:
        job = session.get(JobRow, job_id)
        assert job.status == JobStatus.EN_COLA.value
        assert job.error_code == JobErrorCode.ERROR_INTERNO.value


def test_requeue_no_resucita_un_trabajo_cancelado() -> None:
    factory = _sessions()
    job_id = _job(factory, status=JobStatus.CANCELADA.value)

    _requeue(factory, job_id, JobErrorCode.ERROR_INTERNO)

    with factory() as session:
        assert session.get(JobRow, job_id).status == JobStatus.CANCELADA.value


def test_solo_los_errores_transitorios_se_reintentan() -> None:
    assert JobErrorCode.ERROR_INTERNO in RETRYABLE_ERROR_CODES
    assert JobErrorCode.DESCARGA_BLOQUEADA in RETRYABLE_ERROR_CODES
    assert JobErrorCode.NO_ES_RECETA not in RETRYABLE_ERROR_CODES
    assert JobErrorCode.CUOTA_AGOTADA not in RETRYABLE_ERROR_CODES


def test_un_error_de_configuracion_no_se_reintenta() -> None:
    factory = _sessions()
    job_id = _job(factory, payload={"caption": "2 huevos y sal"})
    settings = Settings(_env_file=None, llm_provider="openai")  # type: ignore[call-arg]

    assert asyncio.run(process_job(job_id, factory, settings)) is None

    with factory() as session:
        job = session.get(JobRow, job_id)
        assert job.status == JobStatus.FALLIDA.value
        assert job.error_code == JobErrorCode.ERROR_INTERNO.value


def test_retry_countdown_es_exponencial_y_tiene_tope() -> None:
    pytest.importorskip("celery")
    from app.jobs.tasks import retry_countdown

    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        job_retry_backoff_s=5,
        job_retry_backoff_max_s=60,
    )

    assert [retry_countdown(settings, attempt) for attempt in range(5)] == [
        5,
        10,
        20,
        40,
        60,
    ]


def test_el_runner_de_celery_publica_el_id() -> None:
    sent: list[str] = []
    runner = CeleryJobRunner(send=sent.append)

    runner.submit("job-1")

    assert sent == ["job-1"]


def test_build_job_runner_elige_thread_por_defecto() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert isinstance(build_job_runner(settings, _sessions()), ThreadJobRunner)


def test_build_job_runner_elige_celery_si_se_configura() -> None:
    settings = Settings(_env_file=None, job_runner="celery")  # type: ignore[call-arg]

    assert isinstance(build_job_runner(settings, _sessions()), CeleryJobRunner)

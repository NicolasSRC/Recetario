from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapters.opencode_llm import OpenCodeQuotaError
from app.config import Settings
from app.domain.schemas import RecipeDraft
from app.domain.validation import NotARecipeError
from app.jobs.service import (
    JobErrorCode,
    JobStage,
    JobStatus,
    classify_error,
    process_job,
)
from app.main import create_app


class RecordingRunner:
    """No procesa nada: los tests llaman a process_job cuando quieren."""

    def __init__(self) -> None:
        self.submitted: list[str] = []

    def submit(self, job_id: str) -> None:
        self.submitted.append(job_id)


class FakeLLM:
    def __init__(self, *, draft: RecipeDraft | None = None, error: BaseException | None = None):
        self._draft = draft
        self._error = error
        self.calls = 0

    async def extract(self, context: Any, *, previous_errors: str | None = None) -> RecipeDraft:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._draft is not None
        return self._draft


@pytest.fixture
def book(
    make_draft: Callable[..., RecipeDraft],
) -> Iterator[tuple[TestClient, Any, RecordingRunner, FakeLLM]]:
    settings = Settings(_env_file=None, database_url="sqlite://")  # type: ignore[call-arg]
    app = create_app(settings)
    runner = RecordingRunner()
    app.state.job_runner = runner

    llm = FakeLLM(draft=make_draft())
    app.state.llm_factory = lambda _settings: (llm, "fake-model")

    with TestClient(app) as client:
        yield client, app, runner, llm


def _run(app: Any, job_id: str) -> None:
    asyncio.run(
        process_job(
            job_id,
            app.state.session_factory,
            app.state.settings,
            app.state.llm_factory,
        )
    )


def _create(client: TestClient, **payload: Any) -> dict[str, Any]:
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202, response.text
    return response.json()


def test_crear_trabajo_por_url(book: tuple[TestClient, Any, RecordingRunner, FakeLLM]) -> None:
    client, _app, runner, _llm = book

    body = _create(client, source_url="tiktok.com/@chef/video/1")

    assert body["status"] == JobStatus.EN_COLA
    assert body["kind"] == "url"
    assert body["source_url"] == "https://tiktok.com/@chef/video/1"
    assert runner.submitted == [body["id"]]


def test_crear_trabajo_con_texto(book: tuple[TestClient, Any, RecordingRunner, FakeLLM]) -> None:
    client, _app, _runner, _llm = book

    body = _create(client, caption="2 pechugas de pollo con aceite")

    assert body["kind"] == "texto"
    assert body["source_url"] is None


def test_url_invalida(book: tuple[TestClient, Any, RecordingRunner, FakeLLM]) -> None:
    client, _app, _runner, _llm = book

    response = client.post("/api/v1/jobs", json={"source_url": "https://example.com/video/1"})

    assert response.status_code == 422


def test_payload_vacio(book: tuple[TestClient, Any, RecordingRunner, FakeLLM]) -> None:
    client, _app, _runner, _llm = book

    assert client.post("/api/v1/jobs", json={}).status_code == 422


def test_trabajo_inexistente(book: tuple[TestClient, Any, RecordingRunner, FakeLLM]) -> None:
    client, _app, _runner, _llm = book

    assert client.get("/api/v1/jobs/no-existe").status_code == 404


def test_procesar_trabajo_de_texto(
    book: tuple[TestClient, Any, RecordingRunner, FakeLLM],
) -> None:
    client, app, _runner, _llm = book
    job = _create(client, caption="2 pechugas de pollo con 2 cucharadas de aceite")

    _run(app, job["id"])

    body = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert body["status"] == JobStatus.LISTA
    assert body["stage"] is None
    assert body["recipe_id"]

    recipe = client.get(f"/api/v1/recipes/{body['recipe_id']}").json()
    assert recipe["title"] == "Pollo al limón"
    assert recipe["source"]["platform"] == "tiktok"


def test_no_es_receta(book: tuple[TestClient, Any, RecordingRunner, FakeLLM]) -> None:
    client, app, _runner, llm = book
    llm._draft = None
    llm._error = NotARecipeError("es maquillaje")
    job = _create(client, caption="un tutorial de maquillaje")

    _run(app, job["id"])

    body = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert body["status"] == JobStatus.FALLIDA
    assert body["error_code"] == JobErrorCode.NO_ES_RECETA
    assert "maquillaje" in body["error_message"]


def test_cuota_agotada(book: tuple[TestClient, Any, RecordingRunner, FakeLLM]) -> None:
    client, app, _runner, llm = book
    llm._draft = None
    llm._error = OpenCodeQuotaError("Free usage limit reached", retry_after_s=3600)
    job = _create(client, caption="una receta")

    _run(app, job["id"])

    body = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert body["status"] == JobStatus.FALLIDA
    assert body["error_code"] == JobErrorCode.CUOTA_AGOTADA
    assert "60 min" in body["error_message"]


def test_esquema_invalido(
    book: tuple[TestClient, Any, RecordingRunner, FakeLLM],
    make_draft: Callable[..., RecipeDraft],
) -> None:
    client, app, _runner, llm = book
    llm._draft = make_draft(title="   ")
    job = _create(client, caption="una receta sin título")

    _run(app, job["id"])

    body = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert body["status"] == JobStatus.FALLIDA
    assert body["error_code"] == JobErrorCode.ESQUEMA_INVALIDO


def test_cancelar_trabajo_en_cola(
    book: tuple[TestClient, Any, RecordingRunner, FakeLLM],
) -> None:
    client, app, _runner, _llm = book
    job = _create(client, caption="una receta")

    response = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == JobStatus.CANCELADA

    _run(app, job["id"])
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["status"] == JobStatus.CANCELADA


def test_no_cancelar_trabajo_terminado(
    book: tuple[TestClient, Any, RecordingRunner, FakeLLM],
) -> None:
    client, app, _runner, _llm = book
    job = _create(client, caption="una receta")
    _run(app, job["id"])

    assert client.post(f"/api/v1/jobs/{job['id']}/cancel").status_code == 409


def test_reintentar_trabajo_fallido(
    book: tuple[TestClient, Any, RecordingRunner, FakeLLM],
) -> None:
    client, app, runner, llm = book
    llm._draft = None
    llm._error = NotARecipeError("no es receta")
    job = _create(client, caption="una receta")
    _run(app, job["id"])

    llm._error = None
    response = client.post(f"/api/v1/jobs/{job['id']}/retry")

    assert response.status_code == 202
    assert response.json()["status"] == JobStatus.EN_COLA
    assert response.json()["error_code"] is None
    assert runner.submitted.count(job["id"]) == 2


def test_no_reintentar_trabajo_en_cola(
    book: tuple[TestClient, Any, RecordingRunner, FakeLLM],
) -> None:
    client, _app, _runner, _llm = book
    job = _create(client, caption="una receta")

    assert client.post(f"/api/v1/jobs/{job['id']}/retry").status_code == 409


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (NotARecipeError("x"), JobErrorCode.NO_ES_RECETA),
        (OpenCodeQuotaError("x"), JobErrorCode.CUOTA_AGOTADA),
        (ValueError("la transcripción quedó vacía"), JobErrorCode.TRANSCRIPCION_VACIA),
        (RuntimeError("boom"), JobErrorCode.ERROR_INTERNO),
    ],
)
def test_clasificacion_de_errores(exc: BaseException, expected: JobErrorCode) -> None:
    assert classify_error(exc) == expected


def test_etapas_definidas() -> None:
    assert [stage.value for stage in JobStage] == [
        "descargando",
        "transcribiendo",
        "extrayendo",
        "guardando",
    ]

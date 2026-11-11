"""Endpoints de trabajos de ingesta (RF-30, RF-31)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.api.schemas import JobCreate, JobOut
from app.db.models import JobRow
from app.domain.urls import InvalidUrlError, normalize_tiktok_url
from app.jobs.service import JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])

SessionDep = Annotated[Session, Depends(get_session)]


def _get_job(session: Session, job_id: str) -> JobRow:
    job = session.get(JobRow, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="trabajo no encontrado")
    return job


@router.post("", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreate, request: Request, session: SessionDep) -> JobRow:
    """Encola la ingesta y responde 202 con el trabajo (RF-30)."""
    source_url: str | None = None
    if payload.source_url:
        try:
            source_url = normalize_tiktok_url(payload.source_url)
        except InvalidUrlError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    kind = "url" if source_url else "texto"
    job_payload = None
    if kind == "texto":
        job_payload = {
            "author": payload.author,
            "caption": payload.caption,
            "transcript": payload.transcript,
            "screen_text": payload.screen_text,
        }

    job = JobRow(kind=kind, source_url=source_url, payload=job_payload)
    session.add(job)
    session.commit()
    session.refresh(job)

    request.app.state.job_runner.submit(job.id)
    session.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, session: SessionDep) -> JobRow:
    """Estado del trabajo para el polling de la UI (cada 2 s)."""
    return _get_job(session, job_id)


@router.post("/{job_id}/retry", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def retry_job(job_id: str, request: Request, session: SessionDep) -> JobRow:
    job = _get_job(session, job_id)
    if job.status not in {JobStatus.FALLIDA.value, JobStatus.CANCELADA.value}:
        raise HTTPException(
            status_code=409,
            detail="solo se reintentan trabajos fallidos o cancelados",
        )

    job.status = JobStatus.EN_COLA.value
    job.stage = None
    job.error_code = None
    job.error_message = None
    job.duration_s = None
    job.recipe_id = None
    session.commit()
    session.refresh(job)

    request.app.state.job_runner.submit(job.id)
    session.refresh(job)
    return job


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, session: SessionDep) -> JobRow:
    job = _get_job(session, job_id)
    if job.status not in {JobStatus.EN_COLA.value, JobStatus.PROCESANDO.value}:
        raise HTTPException(status_code=409, detail="el trabajo ya terminó")

    job.status = JobStatus.CANCELADA.value
    job.stage = None
    session.commit()
    session.refresh(job)
    return job

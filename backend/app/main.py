"""Aplicación FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.jobs import router as jobs_router
from app.api.routes.recipes import router as recipes_router
from app.config import Settings, get_settings
from app.db.session import create_db_engine, create_session_factory, init_db
from app.jobs.runner import build_job_runner
from app.llm_factory import build_llm


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    engine = create_db_engine(settings.database_url)
    init_db(engine)
    session_factory = create_session_factory(engine)

    app = FastAPI(
        title="Recetario API",
        version="0.2.0",
        description="De un TikTok a una receta estructurada, editable y exportable.",
    )
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.llm_factory = build_llm
    app.state.job_runner = build_job_runner(
        settings,
        session_factory=session_factory,
        llm_factory=build_llm,
    )

    # El libro (F3) corre en otro puerto durante el desarrollo.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(recipes_router, prefix="/api/v1")
    app.include_router(jobs_router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app

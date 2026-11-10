"""Aplicación FastAPI."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes.recipes import router as recipes_router
from app.config import Settings, get_settings
from app.db.session import create_db_engine, create_session_factory, init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    engine = create_db_engine(settings.database_url)
    init_db(engine)

    app = FastAPI(
        title="Recetario API",
        version="0.1.0",
        description="De un TikTok a una receta estructurada, editable y exportable.",
    )
    app.state.session_factory = create_session_factory(engine)

    app.include_router(recipes_router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app

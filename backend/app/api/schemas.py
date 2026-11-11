"""Esquemas de entrada y salida de la API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.domain.schemas import Ingredient, Nutrition, Recipe, RecipeDraft, Status, Step
from app.jobs.service import JobStage, JobStatus


class RecipeCreate(RecipeDraft):
    """Alta manual de una receta, sin video (F3)."""

    source_url: str | None = None
    author: str | None = None


class RecipeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    language: str | None = None
    servings: int | None = None
    prep_time_min: int | None = None
    cook_time_min: int | None = None
    difficulty: str | None = None
    ingredients: list[Ingredient] | None = None
    steps: list[Step] | None = None
    equipment: list[str] | None = None
    tags: list[str] | None = None
    nutrition: Nutrition | None = None
    notes: str | None = None
    status: Status | None = None


class RecipePage(BaseModel):
    items: list[Recipe]
    total: int
    limit: int
    offset: int


class JobCreate(BaseModel):
    """Ingesta por URL o con texto pegado a mano (RF-04)."""

    model_config = ConfigDict(extra="forbid")

    source_url: str | None = None
    author: str | None = None
    caption: str | None = None
    transcript: str | None = None
    screen_text: str | None = None

    @model_validator(mode="after")
    def _require_source(self) -> JobCreate:
        has_text = any(
            (value or "").strip() for value in (self.caption, self.transcript, self.screen_text)
        )
        if not (self.source_url or "").strip() and not has_text:
            raise ValueError("indica una URL de TikTok o algún texto de entrada")
        return self


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    source_url: str | None
    status: JobStatus
    stage: JobStage | None
    error_code: str | None
    error_message: str | None
    recipe_id: str | None
    cost_usd: float
    duration_s: float | None
    created_at: datetime
    updated_at: datetime

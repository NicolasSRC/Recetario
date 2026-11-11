"""Esquemas de entrada y salida de la API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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


class AgentEventOut(BaseModel):
    """Una llamada del agente (RA-04), tal como la ve la interfaz."""

    model_config = ConfigDict(from_attributes=True)

    step: int = 0
    tool: str
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    text: str = ""
    ok: bool = True
    error: str | None = None
    duration_ms: int | None = None
    cost_usd: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def _flatten_row(cls, value: Any) -> Any:
        """`job_events` guarda paso y resultado dentro de los JSON."""
        if isinstance(value, dict) or not hasattr(value, "tool"):
            return value

        payload = value.input or {}
        result = value.output or {}
        return {
            "step": payload.get("step", 0),
            "tool": value.tool,
            "input": value.input,
            "output": value.output,
            "text": result.get("text", ""),
            "ok": result.get("ok", True),
            "error": result.get("error"),
            "duration_ms": value.duration_ms,
            "cost_usd": value.cost_usd,
        }


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
    events: list[AgentEventOut] = []

"""Esquemas de entrada y salida de la API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domain.schemas import Ingredient, Nutrition, Recipe, RecipeDraft, Status, Step


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

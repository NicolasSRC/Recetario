"""Envoltorio de salida del LLM.

Permite expresar "esto no es una receta" (RF-26) sin inventar ingredientes ni
pasos, y mantiene el puerto `RecipeLLM` limpio: siempre devuelve un `RecipeDraft`.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.schemas import RecipeDraft


class LLMOutput(BaseModel):
    is_recipe: bool
    not_a_recipe_reason: str | None = None
    recipe: RecipeDraft | None = None

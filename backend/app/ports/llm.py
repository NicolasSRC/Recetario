"""Puerto del modelo de lenguaje (RF-20, RA-07)."""

from __future__ import annotations

from typing import Protocol

from app.domain.content import RecipeContext
from app.domain.schemas import RecipeDraft


class RecipeLLM(Protocol):
    async def extract(
        self,
        context: RecipeContext,
        *,
        previous_errors: str | None = None,
    ) -> RecipeDraft:
        """Convierte el contexto en un borrador de receta.

        `previous_errors` lleva el error de validación del intento anterior
        para que el modelo pueda corregirse (RF-23).
        """
        ...

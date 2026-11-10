"""Reglas de negocio del esquema (sección 3) y cálculo del estado final."""

from __future__ import annotations

from app.domain.confidence import REVIEW_THRESHOLD, compute_confidence
from app.domain.schemas import Recipe, Status


class BusinessRuleError(ValueError):
    """La receta incumple una regla que no puede arreglar el esquema."""


class NotARecipeError(RuntimeError):
    """El contenido no es una receta: no se crea ninguna entrada (RF-26)."""

    def __init__(self, reason: str = "el video no contiene una receta") -> None:
        self.reason = reason
        super().__init__(reason)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def validate_recipe(recipe: Recipe) -> Recipe:
    """Valida RE-01, normaliza el orden de pasos y fija confianza y estado.

    Devuelve una copia: no muta la entrada.
    """
    recipe = recipe.model_copy(deep=True)

    if not recipe.title.strip():
        raise BusinessRuleError("el título no puede estar vacío")
    if not recipe.ingredients:
        raise BusinessRuleError("la receta no tiene ingredientes")
    if not recipe.steps:
        raise BusinessRuleError("la receta no tiene pasos")

    for index, step in enumerate(recipe.steps, start=1):
        step.order = index

    score, flags, field_confidence = compute_confidence(recipe)

    # RE-01: sin evidencia el campo queda marcado, nunca inventado.
    merged_flags = _dedupe([*recipe.extraction.flags, *flags])
    needs_review = score < REVIEW_THRESHOLD or bool(merged_flags)

    recipe.extraction.confidence = score
    recipe.extraction.field_confidence = field_confidence
    recipe.extraction.flags = merged_flags
    recipe.extraction.needs_review = needs_review
    recipe.status = Status.POR_REVISAR if needs_review else Status.APROBADA

    return recipe

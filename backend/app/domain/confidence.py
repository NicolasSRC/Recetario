"""Puntaje de confianza y marca de "por revisar" (RF-24, RF-25)."""

from __future__ import annotations

from app.domain.schemas import Recipe

REVIEW_THRESHOLD = 0.75


def _ratio(numerator: int, denominator: int, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def compute_confidence(recipe: Recipe) -> tuple[float, list[str], dict[str, float]]:
    """Devuelve (confianza global, flags, confianza por campo).

    Es una heurística explicable, no una probabilidad calibrada: lo importante
    es que un campo sin evidencia baje el puntaje y marque la receta para revisión.
    """
    flags: list[str] = []

    with_evidence = sum(1 for item in recipe.ingredients if item.evidence is not None)
    ingredients_score = _ratio(with_evidence, len(recipe.ingredients))

    for item in recipe.ingredients:
        if item.evidence is None:
            flags.append(f"ingrediente_sin_evidencia:{item.name}")

    steps_score = 1.0 if len(recipe.steps) >= 2 else 0.5
    if len(recipe.steps) < 2:
        flags.append("pasos_insuficientes")

    servings_score = 1.0 if recipe.servings is not None else 0.5
    if recipe.servings is None:
        flags.append("porciones_sin_evidencia")

    language_score = 1.0 if recipe.language else 0.0

    field_confidence = {
        "title": 1.0 if recipe.title else 0.0,
        "ingredients": round(ingredients_score, 4),
        "steps": steps_score,
        "servings": servings_score,
        "language": language_score,
    }

    score = (
        0.45 * ingredients_score
        + 0.25 * steps_score
        + 0.10 * servings_score
        + 0.10 * language_score
        + 0.10 * (1.0 if recipe.description else 0.5)
    )

    return round(min(max(score, 0.0), 1.0), 4), flags, field_confidence

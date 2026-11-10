"""Exportación de una receta a JSON-LD y Markdown (RF-40)."""

from __future__ import annotations

from typing import Any

from app.domain.schemas import Recipe


def _iso_duration(minutes: int | None) -> str | None:
    return f"PT{minutes}M" if minutes is not None else None


def to_jsonld(recipe: Recipe) -> dict[str, Any]:
    """schema.org/Recipe. Los campos propios (confianza, estado) quedan fuera."""
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": recipe.title,
        "inLanguage": recipe.language,
        "recipeIngredient": [
            ingredient.raw_text or ingredient.name for ingredient in recipe.ingredients
        ],
        "recipeInstructions": [
            {"@type": "HowToStep", "position": step.order, "text": step.text}
            for step in recipe.steps
        ],
    }

    if recipe.description:
        data["description"] = recipe.description
    if recipe.servings is not None:
        data["recipeYield"] = str(recipe.servings)
    if (prep := _iso_duration(recipe.prep_time_min)) is not None:
        data["prepTime"] = prep
    if (cook := _iso_duration(recipe.cook_time_min)) is not None:
        data["cookTime"] = cook
    if (total := _iso_duration(recipe.total_time_min)) is not None:
        data["totalTime"] = total
    if recipe.tags:
        data["keywords"] = ", ".join(recipe.tags)
    if recipe.equipment:
        data["tool"] = list(recipe.equipment)
    if recipe.notes:
        data["comment"] = recipe.notes

    data["author"] = {
        "@type": "Person",
        "name": recipe.source.author or "Autor desconocido",
    }
    data["url"] = recipe.source.url
    data["datePublished"] = recipe.source.captured_at.date().isoformat()

    if recipe.nutrition is not None:
        nutrition = {
            key: value
            for key, value in recipe.nutrition.model_dump().items()
            if value is not None and key != "notes"
        }
        if nutrition:
            data["nutrition"] = {"@type": "NutritionInformation", **nutrition}

    return data


def to_markdown(recipe: Recipe) -> str:
    lines = [f"# {recipe.title}", ""]

    if recipe.description:
        lines.extend([recipe.description, ""])

    meta = []
    if recipe.servings is not None:
        meta.append(f"**Porciones:** {recipe.servings}")
    if recipe.total_time_min is not None:
        meta.append(f"**Tiempo total:** {recipe.total_time_min} min")
    if recipe.difficulty is not None:
        meta.append(f"**Dificultad:** {recipe.difficulty.value}")
    if meta:
        lines.extend([" · ".join(meta), ""])

    lines.extend(["## Ingredientes", ""])
    for ingredient in recipe.ingredients:
        lines.append(f"- {ingredient.raw_text or ingredient.name}")
    lines.append("")

    lines.extend(["## Pasos", ""])
    for step in recipe.steps:
        lines.append(f"{step.order}. {step.text}")
    lines.append("")

    if recipe.notes:
        lines.extend(["## Notas", "", recipe.notes, ""])

    if recipe.tags:
        lines.extend(["## Etiquetas", "", ", ".join(recipe.tags), ""])

    author = recipe.source.author or "Autor desconocido"
    lines.extend(["---", "", f"Fuente: {author} — {recipe.source.url}"])

    return "\n".join(lines)

"""Exportación de una receta a JSON-LD, Markdown y PDF (RF-40)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from fpdf import FPDF

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


# --------------------------------------------------------------------------- #
# PDF

_REPLACEMENTS = {
    "\u2014": "-",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u00a0": " ",
    "\u2022": "-",
    "\u2190": "<-",
    "\u2192": "->",
}


def _pdf_safe(text: str) -> str:
    """Las fuentes base de PDF solo cubren latin-1: normaliza lo demás."""
    for source, target in _REPLACEMENTS.items():
        text = text.replace(source, target)
    return text.encode("latin-1", "replace").decode("latin-1")


def pdf_filename(recipe: Recipe) -> str:
    ascii_title = (
        unicodedata.normalize("NFKD", recipe.title).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_title).strip("-").lower()
    return f"{slug or 'receta'}.pdf"


def _write(pdf: FPDF, height: float, text: str) -> None:
    """Escribe un párrafo y vuelve al margen izquierdo (multi_cell deja x a la derecha)."""
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, height, text, new_x="LMARGIN", new_y="NEXT")


def _heading(pdf: FPDF, text: str) -> None:
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(123, 45, 59)
    _write(pdf, 7, _pdf_safe(text))
    pdf.set_text_color(43, 33, 24)
    pdf.ln(1)


def to_pdf(recipe: Recipe) -> bytes:
    """Una receta por documento, con la misma jerarquía que la página del libro."""
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_margins(20, 18, 20)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_text_color(43, 33, 24)

    pdf.set_font("Helvetica", "B", 22)
    _write(pdf, 10, _pdf_safe(recipe.title))
    pdf.ln(1)

    if recipe.description:
        pdf.set_font("Helvetica", "I", 11)
        pdf.set_text_color(109, 91, 69)
        _write(pdf, 6, _pdf_safe(recipe.description))
        pdf.set_text_color(43, 33, 24)

    meta = []
    if recipe.servings is not None:
        meta.append(f"Porciones: {recipe.servings}")
    if recipe.total_time_min is not None:
        meta.append(f"Tiempo total: {recipe.total_time_min} min")
    if recipe.difficulty is not None:
        meta.append(f"Dificultad: {recipe.difficulty.value}")
    if meta:
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 10)
        _write(pdf, 5.5, _pdf_safe("  ·  ".join(meta)))

    pdf.ln(2)
    pdf.set_draw_color(180, 138, 74)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())

    _heading(pdf, "Ingredientes")
    pdf.set_font("Helvetica", "", 11)
    for ingredient in recipe.ingredients:
        text = ingredient.raw_text or ingredient.name
        if ingredient.optional:
            text = f"{text} (opcional)"
        _write(pdf, 6, _pdf_safe(f"- {text}"))

    _heading(pdf, "Preparación")
    pdf.set_font("Helvetica", "", 11)
    for step in recipe.steps:
        suffix = f" ({step.duration_min} min)" if step.duration_min is not None else ""
        _write(pdf, 6, _pdf_safe(f"{step.order}. {step.text}{suffix}"))
        pdf.ln(1)

    if recipe.notes:
        _heading(pdf, "Notas")
        pdf.set_font("Helvetica", "", 11)
        _write(pdf, 6, _pdf_safe(recipe.notes))

    if recipe.tags:
        pdf.ln(2)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(109, 91, 69)
        _write(pdf, 5, _pdf_safe("Etiquetas: " + ", ".join(recipe.tags)))

    pdf.ln(4)
    pdf.set_draw_color(109, 91, 69)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(109, 91, 69)
    author = recipe.source.author or "Autor desconocido"
    _write(pdf, 5, _pdf_safe(f"Fuente: {author} - {recipe.source.url}"))
    _write(pdf, 5, _pdf_safe(f"Recetario con IA · {recipe.status.value}"))

    return bytes(pdf.output())

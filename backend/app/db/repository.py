"""Acceso a datos: conversión dominio ↔ filas y operaciones CRUD."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import IngredientRow, RecipeRow, SourceRow, StepRow, TagRow
from app.domain.schemas import (
    Difficulty,
    Evidence,
    Extraction,
    Ingredient,
    Nutrition,
    Recipe,
    Source,
    Status,
    Step,
    Unit,
)
from app.domain.validation import validate_recipe

_LOAD_OPTIONS = (
    selectinload(RecipeRow.source),
    selectinload(RecipeRow.ingredients),
    selectinload(RecipeRow.steps),
    selectinload(RecipeRow.tags),
)


def _ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _ingredient_to_domain(row: IngredientRow) -> Ingredient:
    return Ingredient(
        name=row.name,
        quantity=Decimal(row.quantity) if row.quantity is not None else None,
        unit=Unit(row.unit) if row.unit else None,
        note=row.note,
        raw_text=row.raw_text,
        optional=row.optional,
        group=row.group,
        evidence=Evidence(row.evidence) if row.evidence else None,
    )


def _step_to_domain(row: StepRow) -> Step:
    return Step(
        order=row.position,
        text=row.text,
        duration_min=row.duration_min,
        timestamp_s=row.timestamp_s,
    )


def row_to_domain(row: RecipeRow) -> Recipe:
    return Recipe(
        id=row.id,
        schema_version=row.schema_version,
        title=row.title,
        description=row.description,
        language=row.language,
        servings=row.servings,
        prep_time_min=row.prep_time_min,
        cook_time_min=row.cook_time_min,
        difficulty=Difficulty(row.difficulty) if row.difficulty else None,
        ingredients=[_ingredient_to_domain(item) for item in row.ingredients],
        steps=[_step_to_domain(item) for item in row.steps],
        equipment=list(row.equipment or []),
        tags=[tag.name for tag in row.tags],
        nutrition=Nutrition(**row.nutrition) if row.nutrition else None,
        notes=row.notes,
        source=Source(
            url=row.source.url,
            author=row.source.author,
            platform=row.source.platform,
            captured_at=_ensure_utc(row.source.captured_at),
        ),
        extraction=Extraction(
            sources_used=[Evidence(value) for value in (row.sources_used or [])],
            confidence=row.confidence,
            field_confidence=dict(row.field_confidence or {}),
            model=row.model,
            needs_review=row.needs_review,
            flags=list(row.flags or []),
        ),
        status=Status(row.status),
    )


def _apply_recipe(session: Session, row: RecipeRow, recipe: Recipe) -> None:
    row.schema_version = recipe.schema_version
    row.title = recipe.title
    row.description = recipe.description
    row.language = recipe.language
    row.servings = recipe.servings
    row.prep_time_min = recipe.prep_time_min
    row.cook_time_min = recipe.cook_time_min
    row.difficulty = recipe.difficulty.value if recipe.difficulty else None
    row.equipment = list(recipe.equipment)
    row.notes = recipe.notes
    row.nutrition = recipe.nutrition.model_dump() if recipe.nutrition else None

    row.status = recipe.status.value
    row.confidence = recipe.extraction.confidence
    row.needs_review = recipe.extraction.needs_review
    row.model = recipe.extraction.model
    row.sources_used = [value.value for value in recipe.extraction.sources_used]
    row.flags = list(recipe.extraction.flags)
    row.field_confidence = dict(recipe.extraction.field_confidence)

    row.ingredients = [
        IngredientRow(
            position=index,
            name=item.name,
            quantity=item.quantity,
            unit=item.unit.value if item.unit else None,
            note=item.note,
            raw_text=item.raw_text,
            optional=item.optional,
            group=item.group,
            evidence=item.evidence.value if item.evidence else None,
        )
        for index, item in enumerate(recipe.ingredients, start=1)
    ]
    row.steps = [
        StepRow(
            position=index,
            text=item.text,
            duration_min=item.duration_min,
            timestamp_s=item.timestamp_s,
        )
        for index, item in enumerate(recipe.steps, start=1)
    ]
    row.tags = _get_or_create_tags(session, recipe.tags)


def _get_or_create_tags(session: Session, names: list[str]) -> list[TagRow]:
    normalized = [name.strip().lower() for name in names if name.strip()]
    if not normalized:
        return []

    existing = {
        tag.name: tag for tag in session.scalars(select(TagRow).where(TagRow.name.in_(normalized)))
    }
    tags: list[TagRow] = []
    for name in dict.fromkeys(normalized):
        tag = existing.get(name)
        if tag is None:
            tag = TagRow(name=name)
            session.add(tag)
            existing[name] = tag
        tags.append(tag)
    return tags


def find_by_source_url(session: Session, url: str) -> Recipe | None:
    row = session.scalar(
        select(RecipeRow).join(SourceRow).where(SourceRow.url == url).options(*_LOAD_OPTIONS)
    )
    return row_to_domain(row) if row else None


def save_recipe(session: Session, recipe: Recipe, *, dedupe: bool = True) -> tuple[Recipe, bool]:
    """Guarda la receta. Devuelve (receta, creada) y respeta la idempotencia (RP-02)."""
    if dedupe:
        existing = session.scalar(
            select(RecipeRow)
            .join(SourceRow)
            .where(SourceRow.url == recipe.source.url)
            .options(*_LOAD_OPTIONS)
        )
        if existing is not None:
            return row_to_domain(existing), False

    source = SourceRow(
        url=recipe.source.url,
        author=recipe.source.author,
        platform=recipe.source.platform,
        captured_at=recipe.source.captured_at,
    )
    row = RecipeRow(source=source)
    _apply_recipe(session, row, recipe)

    session.add(row)
    session.commit()
    session.refresh(row)
    return row_to_domain(row), True


def get_recipe(session: Session, recipe_id: str) -> Recipe | None:
    row = session.scalar(select(RecipeRow).where(RecipeRow.id == recipe_id).options(*_LOAD_OPTIONS))
    return row_to_domain(row) if row else None


def list_recipes(
    session: Session,
    *,
    limit: int = 20,
    offset: int = 0,
    status: Status | None = None,
    query: str | None = None,
) -> tuple[list[Recipe], int]:
    statement = select(RecipeRow)
    count_statement = select(func.count(distinct(RecipeRow.id))).select_from(RecipeRow)

    if status is not None:
        statement = statement.where(RecipeRow.status == status.value)
        count_statement = count_statement.where(RecipeRow.status == status.value)

    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.join(RecipeRow.ingredients).where(
            or_(RecipeRow.title.ilike(pattern), IngredientRow.name.ilike(pattern))
        )
        count_statement = count_statement.join(RecipeRow.ingredients).where(
            or_(RecipeRow.title.ilike(pattern), IngredientRow.name.ilike(pattern))
        )

    total = session.scalar(count_statement) or 0
    rows = session.scalars(
        statement.options(*_LOAD_OPTIONS)
        .distinct()
        .order_by(RecipeRow.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return [row_to_domain(row) for row in rows], int(total)


def update_recipe(
    session: Session,
    recipe_id: str,
    patch: dict[str, Any],
    *,
    status: Status | None = None,
) -> Recipe | None:
    row = session.scalar(select(RecipeRow).where(RecipeRow.id == recipe_id).options(*_LOAD_OPTIONS))
    if row is None:
        return None

    current = row_to_domain(row)
    data = current.model_dump()
    data.update(patch)

    updated = validate_recipe(Recipe.model_validate(data))
    if status is not None:
        updated.status = status

    _apply_recipe(session, row, updated)
    row.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(row)
    return row_to_domain(row)


def delete_recipe(session: Session, recipe_id: str) -> bool:
    row = session.get(RecipeRow, recipe_id)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True

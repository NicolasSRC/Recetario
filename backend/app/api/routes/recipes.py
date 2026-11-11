"""Endpoints de recetas: listar, ver, crear, editar, borrar y exportar."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.api.export import to_jsonld, to_markdown
from app.api.schemas import RecipeCreate, RecipePage, RecipeUpdate
from app.db import repository
from app.domain.schemas import Evidence, Extraction, Recipe, RecipeDraft, Source, Status
from app.domain.validation import BusinessRuleError, validate_recipe

router = APIRouter(prefix="/recipes", tags=["recipes"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post("", response_model=Recipe, status_code=201)
def create_recipe(payload: RecipeCreate, session: SessionDep) -> Recipe:
    draft_data = payload.model_dump(exclude={"source_url", "author"})
    draft = RecipeDraft(**draft_data)

    # Una receta manual la escribe el usuario: su evidencia es el texto aportado.
    ingredients = [
        item.model_copy(update={"evidence": item.evidence or Evidence.CAPTION})
        for item in draft.ingredients
    ]
    draft = draft.model_copy(update={"ingredients": ingredients})

    source = Source(
        url=payload.source_url or f"manual://{uuid4()}",
        author=payload.author,
        platform="manual" if payload.source_url is None else "tiktok",
    )
    recipe = Recipe(
        **draft.model_dump(),
        source=source,
        extraction=Extraction(sources_used=[Evidence.CAPTION]),
    )

    try:
        recipe = validate_recipe(recipe)
    except BusinessRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Una receta escrita a mano no la extrajo el modelo: el usuario es la
    # fuente y la aprueba al guardarla. Los trabajos de ingesta sí conservan
    # el estado `por_revisar` que calcula la validación.
    recipe.extraction.confidence = 1.0
    recipe.extraction.flags = []
    recipe.extraction.needs_review = False
    recipe.status = Status.APROBADA

    saved, created = repository.save_recipe(session, recipe, dedupe=payload.source_url is not None)
    if not created:
        raise HTTPException(status_code=409, detail="ya existe una receta para esa URL")
    return saved


@router.get("", response_model=RecipePage)
def list_recipes(
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Status | None = None,
    q: str | None = Query(default=None, description="Busca en título e ingredientes"),
) -> RecipePage:
    items, total = repository.list_recipes(
        session, limit=limit, offset=offset, status=status, query=q
    )
    return RecipePage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{recipe_id}", response_model=Recipe)
def get_recipe(recipe_id: str, session: SessionDep) -> Recipe:
    recipe = repository.get_recipe(session, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="receta no encontrada")
    return recipe


@router.patch("/{recipe_id}", response_model=Recipe)
def update_recipe(recipe_id: str, payload: RecipeUpdate, session: SessionDep) -> Recipe:
    patch = payload.model_dump(exclude_unset=True)
    status = patch.pop("status", None)

    try:
        updated = repository.update_recipe(session, recipe_id, patch, status=status)
    except BusinessRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=404, detail="receta no encontrada")
    return updated


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: str, session: SessionDep) -> Response:
    if not repository.delete_recipe(session, recipe_id):
        raise HTTPException(status_code=404, detail="receta no encontrada")
    return Response(status_code=204)


@router.get("/{recipe_id}/export")
def export_recipe(
    recipe_id: str,
    session: SessionDep,
    format: Literal["jsonld", "md"] = "jsonld",
) -> Response:
    recipe = repository.get_recipe(session, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="receta no encontrada")

    if format == "md":
        return PlainTextResponse(to_markdown(recipe), media_type="text/markdown; charset=utf-8")

    return JSONResponse(to_jsonld(recipe))

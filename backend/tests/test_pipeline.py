from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from app.domain.content import RecipeContext, VideoMetadata
from app.domain.schemas import Evidence, Ingredient, RecipeDraft, Status, Unit
from app.domain.validation import NotARecipeError
from app.pipeline.extract_recipe import ExtractionFailed, extract_recipe


class FakeLLM:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[str | None] = []

    async def extract(
        self,
        context: RecipeContext,
        *,
        previous_errors: str | None = None,
    ) -> RecipeDraft:
        self.calls.append(previous_errors)
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item  # type: ignore[no-any-return]


def _context() -> RecipeContext:
    return RecipeContext(
        metadata=VideoMetadata(
            url="https://www.tiktok.com/@chef/video/1",
            author="chef",
            caption="2 pechugas de pollo con 2 cucharadas de aceite de oliva.",
        )
    )


def _draft_without_evidence(make_draft: Callable[..., RecipeDraft]) -> RecipeDraft:
    return make_draft(
        ingredients=[
            Ingredient(
                name="pechuga de pollo",
                quantity=Decimal(2),
                unit=Unit.UNIDAD,
                raw_text="2 pechugas de pollo",
            ),
            Ingredient(
                name="aceite de oliva",
                quantity=Decimal(2),
                unit=Unit.CUCHARADA,
                raw_text="2 cucharadas de aceite de oliva",
            ),
        ]
    )


async def test_infiere_evidencia_desde_el_caption(
    make_draft: Callable[..., RecipeDraft],
) -> None:
    llm = FakeLLM([_draft_without_evidence(make_draft)])

    recipe = await extract_recipe(_context(), llm, model_name="fake")

    assert all(item.evidence is Evidence.CAPTION for item in recipe.ingredients)
    assert recipe.status is Status.APROBADA
    assert llm.calls == [None]


async def test_reintenta_con_el_error_como_feedback(
    make_draft: Callable[..., RecipeDraft],
) -> None:
    llm = FakeLLM([RuntimeError("timeout del proveedor"), make_draft()])

    recipe = await extract_recipe(_context(), llm, max_retries=2, model_name="fake")

    assert recipe.status is Status.APROBADA
    assert len(llm.calls) == 2
    assert llm.calls[0] is None
    assert llm.calls[1] is not None
    assert "timeout del proveedor" in (llm.calls[1] or "")


async def test_falla_tras_agotar_reintentos(make_draft: Callable[..., RecipeDraft]) -> None:
    llm = FakeLLM([RuntimeError("boom"), RuntimeError("boom"), RuntimeError("boom")])

    with pytest.raises(ExtractionFailed) as excinfo:
        await extract_recipe(_context(), llm, max_retries=2)

    assert excinfo.value.attempts == 3
    assert len(llm.calls) == 3


async def test_no_es_receta_no_se_reintenta() -> None:
    llm = FakeLLM([NotARecipeError("es un tutorial de maquillaje")])

    with pytest.raises(NotARecipeError):
        await extract_recipe(_context(), llm, max_retries=2)

    assert len(llm.calls) == 1

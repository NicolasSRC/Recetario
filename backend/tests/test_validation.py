from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from app.domain.content import RecipeContext, VideoMetadata
from app.domain.schemas import Evidence, Ingredient, RecipeDraft, Status, Unit
from app.domain.validation import validate_recipe
from app.pipeline.extract_recipe import assemble_recipe


def _context() -> RecipeContext:
    return RecipeContext(
        metadata=VideoMetadata(
            url="https://www.tiktok.com/@chef/video/1",
            author="chef",
            caption="2 pechugas de pollo con 2 cucharadas de aceite de oliva y limón.",
        )
    )


def test_receta_con_evidencia_completa_queda_aprobada(
    make_draft: Callable[..., RecipeDraft],
) -> None:
    recipe = assemble_recipe(make_draft(), _context(), model_name="fake")
    validated = validate_recipe(recipe)

    assert validated.status is Status.APROBADA
    assert validated.extraction.confidence == 1.0
    assert validated.extraction.needs_review is False
    assert validated.extraction.flags == []


def test_ingrediente_sin_evidencia_marca_por_revisar(
    make_draft: Callable[..., RecipeDraft],
) -> None:
    ingredients = [
        Ingredient(
            name="pechuga de pollo",
            quantity=Decimal(2),
            unit=Unit.UNIDAD,
            raw_text="2 pechugas de pollo",
        ),
        # No aparece en el caption: no se puede inferir la evidencia.
        Ingredient(
            name="azafrán",
            quantity=Decimal(1),
            unit=Unit.CUCHARADITA,
            raw_text="1 cucharadita de azafrán",
        ),
    ]
    recipe = assemble_recipe(
        make_draft(ingredients=ingredients),
        _context(),
        model_name="fake",
    )
    validated = validate_recipe(recipe)

    assert validated.status is Status.POR_REVISAR
    assert validated.extraction.needs_review is True
    assert "ingrediente_sin_evidencia:azafrán" in validated.extraction.flags


def test_validate_recipe_no_muta_la_entrada(make_draft: Callable[..., RecipeDraft]) -> None:
    recipe = assemble_recipe(make_draft(), _context(), model_name="fake")
    validate_recipe(recipe)
    assert recipe.extraction.confidence == 0.0
    assert recipe.status is Status.POR_REVISAR


def test_ordena_los_pasos(make_draft: Callable[..., RecipeDraft]) -> None:
    draft = make_draft()
    draft.steps[0].order = 7
    draft.steps[1].order = 3

    validated = validate_recipe(assemble_recipe(draft, _context(), model_name="fake"))

    assert [step.order for step in validated.steps] == [1, 2]


def test_usa_decimal_en_las_cantidades(make_draft: Callable[..., RecipeDraft]) -> None:
    recipe = assemble_recipe(make_draft(), _context(), model_name="fake")
    assert recipe.ingredients[0].quantity == Decimal(2)
    assert isinstance(recipe.ingredients[0].quantity, Decimal)


def test_source_se_construye_desde_los_metadatos(
    make_draft: Callable[..., RecipeDraft],
) -> None:
    recipe = assemble_recipe(make_draft(), _context(), model_name="fake")
    assert recipe.source.url == "https://www.tiktok.com/@chef/video/1"
    assert recipe.source.author == "chef"
    assert recipe.source.platform == "tiktok"
    assert recipe.extraction.sources_used == [Evidence.CAPTION]

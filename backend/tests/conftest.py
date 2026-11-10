from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.schemas import Evidence, Ingredient, RecipeDraft, Step, Unit

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def make_draft() -> Callable[..., RecipeDraft]:
    def factory(**overrides: object) -> RecipeDraft:
        data: dict[str, object] = {
            "title": "Pollo al limón",
            "description": "Pollo marinado y cocinado a la plancha.",
            "language": "es",
            "servings": 2,
            "prep_time_min": 10,
            "cook_time_min": 15,
            "difficulty": "facil",
            "ingredients": [
                Ingredient(
                    name="pechuga de pollo",
                    quantity=Decimal(2),
                    unit=Unit.UNIDAD,
                    raw_text="2 pechugas de pollo",
                    evidence=Evidence.CAPTION,
                ),
                Ingredient(
                    name="aceite de oliva",
                    quantity=Decimal(2),
                    unit=Unit.CUCHARADA,
                    raw_text="2 cucharadas de aceite de oliva",
                    evidence=Evidence.CAPTION,
                ),
            ],
            "steps": [
                Step(order=1, text="Mezcla el jugo de limón con el aceite y las especias."),
                Step(order=2, text="Cocina el pollo a fuego medio 6 minutos por lado."),
            ],
            "tags": ["pollo"],
        }
        data.update(overrides)
        return RecipeDraft(**data)  # type: ignore[arg-type]

    return factory

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.schemas import Unit
from app.domain.units import normalize_unit, parse_ingredient, parse_quantity


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("g", Unit.G),
        ("gramos", Unit.G),
        ("KG", Unit.KG),
        ("ml", Unit.ML),
        ("litros", Unit.L),
        ("tazas", Unit.TAZA),
        ("cda", Unit.CUCHARADA),
        ("cdta", Unit.CUCHARADITA),
        ("piezas", Unit.UNIDAD),
        ("", None),
        ("dientes", None),
    ],
)
def test_normalize_unit(raw: str, expected: Unit | None) -> None:
    assert normalize_unit(raw) is expected


@pytest.mark.parametrize(
    ("raw", "quantity", "rest"),
    [
        ("2 tazas de leche", Decimal(2), "tazas de leche"),
        ("1 1/2 tazas de harina", Decimal("1.5"), "tazas de harina"),
        ("1/2 cucharadita de sal", Decimal("0.5"), "cucharadita de sal"),
        ("1,5 l de agua", Decimal("1.5"), "l de agua"),
        ("½ taza de azúcar", Decimal("0.5"), "taza de azúcar"),
        ("media taza de leche", Decimal("0.5"), "taza de leche"),
        ("una cebolla", Decimal(1), "cebolla"),
        ("una docena de huevos", Decimal(12), "de huevos"),
        ("sal", None, "sal"),
        ("al gusto", None, "al gusto"),
    ],
)
def test_parse_quantity(raw: str, quantity: Decimal | None, rest: str) -> None:
    parsed_quantity, parsed_rest = parse_quantity(raw)
    assert parsed_quantity == quantity
    assert parsed_rest == rest


@pytest.mark.parametrize(
    ("raw", "quantity", "unit", "name"),
    [
        ("1 1/2 tazas de harina integral", Decimal("1.5"), Unit.TAZA, "harina integral"),
        ("media taza de leche", Decimal("0.5"), Unit.TAZA, "leche"),
        ("200 gr de pollo", Decimal(200), Unit.G, "pollo"),
        ("2 cdas de aceite de oliva", Decimal(2), Unit.CUCHARADA, "aceite de oliva"),
        ("1,5 l de agua", Decimal("1.5"), Unit.L, "agua"),
        ("3 huevos", Decimal(3), None, "huevos"),
        ("sal al gusto", None, None, "sal"),
        ("cebolla, picada fina", None, None, "cebolla"),
    ],
)
def test_parse_ingredient(raw: str, quantity: Decimal | None, unit: Unit | None, name: str) -> None:
    parsed = parse_ingredient(raw)
    assert parsed.quantity == quantity
    assert parsed.unit is unit
    assert parsed.name == name
    assert parsed.raw_text == raw


def test_parse_ingredient_conserva_raw_text_y_detecta_opcional() -> None:
    parsed = parse_ingredient("1 cucharadita de sal (opcional)")
    assert parsed.raw_text == "1 cucharadita de sal (opcional)"
    assert parsed.optional is True
    assert parsed.note == "opcional"


def test_parse_ingredient_nota_tras_coma() -> None:
    parsed = parse_ingredient("2 cebollas, picadas finas")
    assert parsed.name == "cebollas"
    assert parsed.note == "picadas finas"


def test_parse_ingredient_al_gusto_queda_sin_cantidad() -> None:
    parsed = parse_ingredient("pimienta al gusto")
    assert parsed.quantity is None
    assert parsed.unit is None
    assert parsed.name == "pimienta"
    assert parsed.note == "al gusto"

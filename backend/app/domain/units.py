"""Normalización de cantidades y unidades (RF-21, RF-22).

No es el extractor principal: el LLM estructura la receta. Este módulo es el
normalizador determinista que convierte texto libre en el conjunto fijo de
unidades y garantiza que `raw_text` se conserve para auditoría.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.domain.schemas import Unit

# --------------------------------------------------------------------------- #
# Unidades
# --------------------------------------------------------------------------- #

UNIT_ALIASES: dict[str, Unit] = {
    "g": Unit.G,
    "gr": Unit.G,
    "grs": Unit.G,
    "gramo": Unit.G,
    "gramos": Unit.G,
    "kg": Unit.KG,
    "kilo": Unit.KG,
    "kilos": Unit.KG,
    "kilogramo": Unit.KG,
    "kilogramos": Unit.KG,
    "ml": Unit.ML,
    "mililitro": Unit.ML,
    "mililitros": Unit.ML,
    "cc": Unit.ML,
    "l": Unit.L,
    "lt": Unit.L,
    "litro": Unit.L,
    "litros": Unit.L,
    "taza": Unit.TAZA,
    "tazas": Unit.TAZA,
    "cup": Unit.TAZA,
    "cups": Unit.TAZA,
    "cucharada": Unit.CUCHARADA,
    "cucharadas": Unit.CUCHARADA,
    "cda": Unit.CUCHARADA,
    "cdas": Unit.CUCHARADA,
    "cuch": Unit.CUCHARADA,
    "tbsp": Unit.CUCHARADA,
    "cucharadita": Unit.CUCHARADITA,
    "cucharaditas": Unit.CUCHARADITA,
    "cdta": Unit.CUCHARADITA,
    "cdtas": Unit.CUCHARADITA,
    "tsp": Unit.CUCHARADITA,
    "unidad": Unit.UNIDAD,
    "unidades": Unit.UNIDAD,
    "u": Unit.UNIDAD,
    "ud": Unit.UNIDAD,
    "uds": Unit.UNIDAD,
    "pza": Unit.UNIDAD,
    "pzas": Unit.UNIDAD,
    "pieza": Unit.UNIDAD,
    "piezas": Unit.UNIDAD,
}


def normalize_unit(raw: str | None) -> Unit | None:
    """Devuelve la unidad del conjunto fijo, o None si no se reconoce."""
    if not raw:
        return None
    return UNIT_ALIASES.get(raw.strip().lower().rstrip("."))


# --------------------------------------------------------------------------- #
# Cantidades
# --------------------------------------------------------------------------- #

_FRACTIONS = {
    "½": "1/2",
    "⅓": "1/3",
    "⅔": "2/3",
    "¼": "1/4",
    "¾": "3/4",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
}

NUMBER_WORDS: dict[str, Decimal] = {
    "un": Decimal(1),
    "una": Decimal(1),
    "uno": Decimal(1),
    "medio": Decimal("0.5"),
    "media": Decimal("0.5"),
    "dos": Decimal(2),
    "tres": Decimal(3),
    "cuatro": Decimal(4),
    "cinco": Decimal(5),
    "seis": Decimal(6),
    "siete": Decimal(7),
    "ocho": Decimal(8),
    "nueve": Decimal(9),
    "diez": Decimal(10),
    "docena": Decimal(12),
    "docenas": Decimal(12),
}

_QUANTITY_RE = re.compile(
    r"""
    ^\s*
    (?:
        (?P<whole>\d+)\s+(?P<num>\d+)\s*/\s*(?P<den>\d+)   # 1 1/2
      | (?P<frac_num>\d+)\s*/\s*(?P<frac_den>\d+)          # 1/2
      | (?P<decimal>\d+[.,]\d+)                            # 1,5 / 1.5
      | (?P<integer>\d+)                                   # 2
      | (?P<word>[a-záéíóúüñ]+)                            # media
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_VAGUE_QUANTITIES = re.compile(
    r"\b(al\s+gusto|a\s+gusto|c/n|al\s+ojo|lo\s+necesario|suficiente)\b",
    re.IGNORECASE,
)


def _to_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None


def parse_quantity(raw: str) -> tuple[Decimal | None, str]:
    """Extrae la cantidad del inicio del texto. Devuelve (cantidad, resto)."""
    text = raw.strip()
    for char, replacement in _FRACTIONS.items():
        text = text.replace(char, replacement)

    match = _QUANTITY_RE.match(text)
    if not match:
        return None, text

    groups = match.groupdict()
    rest = text[match.end() :].strip()

    if groups["whole"]:
        quantity = _to_decimal(groups["whole"])
        denominator = _to_decimal(groups["den"] or "")
        numerator = _to_decimal(groups["num"] or "")
        if quantity is not None and denominator and numerator:
            quantity += numerator / denominator
        return quantity, rest

    if groups["frac_num"]:
        numerator = _to_decimal(groups["frac_num"])
        denominator = _to_decimal(groups["frac_den"] or "")
        if numerator is None or not denominator:
            return None, text
        return numerator / denominator, rest

    if groups["decimal"]:
        return _to_decimal(groups["decimal"]), rest

    if groups["integer"]:
        return _to_decimal(groups["integer"]), rest

    word = (groups["word"] or "").lower()
    if word in NUMBER_WORDS:
        first = NUMBER_WORDS[word]
        # "una docena", "media docena": el segundo número multiplica.
        parts = rest.split(maxsplit=1)
        if parts:
            second = NUMBER_WORDS.get(parts[0].lower())
            if second is not None:
                remaining = parts[1] if len(parts) > 1 else ""
                return first * second, remaining
        return first, rest

    # La palabra no era un número ("sal", "cebolla"): no se consume.
    return None, text


# --------------------------------------------------------------------------- #
# Ingredientes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ParsedIngredient:
    quantity: Decimal | None
    unit: Unit | None
    name: str
    note: str | None
    raw_text: str
    optional: bool


def _clean_name(value: str) -> str:
    name = re.sub(r"^(de|del)\s+", "", value.strip(), flags=re.IGNORECASE)
    name = re.sub(r"[,.;:]+$", "", name.strip())
    return " ".join(name.lower().split())


def parse_ingredient(raw: str) -> ParsedIngredient:
    """Convierte "1 1/2 tazas de harina" en cantidad/unidad/nombre/nota.

    Solo cubre los formatos frecuentes; el LLM sigue siendo el extractor
    principal y este parser se usa para normalizar su salida o entradas manuales.
    """
    text = raw.strip()
    original = text
    optional = bool(re.search(r"\b(opcional|optional)\b", text, re.IGNORECASE))

    note: str | None = None

    # Nota entre paréntesis: "harina (integral)"
    if paren := re.search(r"\(([^)]*)\)", text):
        note = paren.group(1).strip() or None
        text = f"{text[: paren.start()]} {text[paren.end() :]}".strip()

    # Nota vaga: "sal al gusto"
    if vague := _VAGUE_QUANTITIES.search(text):
        note = note or vague.group(1).strip().lower()
        text = f"{text[: vague.start()]} {text[vague.end() :]}".strip()

    quantity, rest = parse_quantity(text)

    unit: Unit | None = None
    parts = rest.split(maxsplit=1)
    if parts:
        unit = normalize_unit(parts[0])
        if unit is not None:
            rest = parts[1] if len(parts) > 1 else ""

    # Nota tras coma: "cebolla, picada fina"
    if "," in rest:
        name_part, _, note_part = rest.partition(",")
        rest = name_part
        note = note or note_part.strip() or None

    return ParsedIngredient(
        quantity=quantity,
        unit=unit,
        name=_clean_name(rest),
        note=note,
        raw_text=original,
        optional=optional,
    )

"""Esquema de datos de la receta (sección 3 del documento de requerimientos).

Este módulo es puro: no importa FastAPI, base de datos ni SDKs de LLM.
El mismo esquema se usa para:

- validar la salida estructurada del LLM (`RecipeDraft`),
- persistir la receta (`Recipe`),
- exportar a JSON-LD de schema.org (F2/F6).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, field_serializer, field_validator

SCHEMA_VERSION = 1

# Decimal es el tipo correcto para cantidades, pero su JSON Schema por defecto
# (number | string) rompe el modo estricto de las APIs de salida estructurada.
Quantity = Annotated[
    Decimal | None,
    WithJsonSchema({"anyOf": [{"type": "number"}, {"type": "null"}]}),
]


class Unit(StrEnum):
    """Conjunto fijo de unidades de RF-22."""

    G = "g"
    KG = "kg"
    ML = "ml"
    L = "l"
    TAZA = "taza"
    CUCHARADA = "cucharada"
    CUCHARADITA = "cucharadita"
    UNIDAD = "unidad"


class Evidence(StrEnum):
    """De dónde salió cada dato (RE-01)."""

    CAPTION = "caption"
    AUDIO = "audio"
    PANTALLA = "pantalla"


class Status(StrEnum):
    EN_COLA = "en_cola"
    PROCESANDO = "procesando"
    POR_REVISAR = "por_revisar"
    APROBADA = "aprobada"
    FALLIDA = "fallida"


class Difficulty(StrEnum):
    FACIL = "facil"
    MEDIA = "media"
    DIFICIL = "dificil"


class Ingredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Nombre normalizado, en minúsculas")
    quantity: Quantity = None
    unit: Unit | None = None
    note: str | None = Field(default=None, description="Preparación: picada fina, en cubos...")
    raw_text: str = Field(default="", description="Frase original, para auditoría")
    optional: bool = False
    group: str | None = Field(default=None, description="Subreceta: salsa, masa...")
    evidence: Evidence | None = None

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        return " ".join(value.strip().lower().split())

    @field_serializer("quantity")
    def _serialize_quantity(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int = Field(ge=1)
    text: str = Field(min_length=1)
    duration_min: int | None = Field(default=None, ge=0)
    timestamp_s: float | None = Field(default=None, ge=0)


class Nutrition(BaseModel):
    """Solo se rellena si el autor lo dice; nunca se estima (RF-24)."""

    model_config = ConfigDict(extra="forbid")

    calories_kcal: float | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)
    fiber_g: float | None = Field(default=None, ge=0)
    sugar_g: float | None = Field(default=None, ge=0)
    sodium_mg: float | None = Field(default=None, ge=0)
    notes: str | None = None


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    author: str | None = None
    platform: str = "tiktok"
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Extraction(BaseModel):
    """Metadatos del proceso: no forman parte del JSON-LD."""

    model_config = ConfigDict(extra="forbid")

    sources_used: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    model: str | None = None
    needs_review: bool = True
    flags: list[str] = Field(default_factory=list)


class RecipeDraft(BaseModel):
    """Lo que produce el LLM. Sin campos de infraestructura (fuente, estado, costo)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    description: str | None = None
    language: str = Field(min_length=2, max_length=8, description="Código ISO 639-1: es, en")
    servings: int | None = Field(default=None, ge=1)
    prep_time_min: int | None = Field(default=None, ge=0)
    cook_time_min: int | None = Field(default=None, ge=0)
    difficulty: Difficulty | None = None
    ingredients: list[Ingredient] = Field(min_length=1)
    steps: list[Step] = Field(min_length=1)
    equipment: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    nutrition: Nutrition | None = None
    notes: str | None = None

    @field_validator("language")
    @classmethod
    def _normalize_language(cls, value: str) -> str:
        return value.strip().lower()

    @property
    def total_time_min(self) -> int | None:
        times = [t for t in (self.prep_time_min, self.cook_time_min) if t is not None]
        return sum(times) if times else None


class Recipe(RecipeDraft):
    """Receta completa: contenido + trazabilidad."""

    schema_version: int = SCHEMA_VERSION
    source: Source
    extraction: Extraction = Field(default_factory=Extraction)
    status: Status = Status.POR_REVISAR

"""Modelos SQLAlchemy de F2.

El contenido de la receta vive en tablas normalizadas; los metadatos del proceso
(confianza, flags, fuente) se guardan junto a la receta.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


recipe_tags = Table(
    "recipe_tags",
    Base.metadata,
    Column("recipe_id", ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class SourceRow(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    author: Mapped[str | None] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(50), default="tiktok")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    recipe: Mapped[RecipeRow | None] = relationship(back_populates="source")


class RecipeRow(Base):
    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_version: Mapped[int] = mapped_column(default=1)
    title: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8), default="es")
    servings: Mapped[int | None]
    prep_time_min: Mapped[int | None]
    cook_time_min: Mapped[int | None]
    difficulty: Mapped[str | None] = mapped_column(String(20))
    equipment: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    nutrition: Mapped[dict | None] = mapped_column(JSON)

    status: Mapped[str] = mapped_column(String(20), default="por_revisar", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)
    model: Mapped[str | None] = mapped_column(String(120))
    sources_used: Mapped[list[str]] = mapped_column(JSON, default=list)
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    field_confidence: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    source: Mapped[SourceRow] = relationship(back_populates="recipe")
    ingredients: Mapped[list[IngredientRow]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", order_by="IngredientRow.position"
    )
    steps: Mapped[list[StepRow]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", order_by="StepRow.position"
    )
    tags: Mapped[list[TagRow]] = relationship(secondary=recipe_tags, back_populates="recipes")


class IngredientRow(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), index=True)
    position: Mapped[int]
    name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    unit: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    optional: Mapped[bool] = mapped_column(Boolean, default=False)
    group: Mapped[str | None] = mapped_column(String(100))
    evidence: Mapped[str | None] = mapped_column(String(20))

    recipe: Mapped[RecipeRow] = relationship(back_populates="ingredients")


class StepRow(Base):
    __tablename__ = "steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), index=True)
    position: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    duration_min: Mapped[int | None]
    timestamp_s: Mapped[float | None] = mapped_column(Float)

    recipe: Mapped[RecipeRow] = relationship(back_populates="steps")


class TagRow(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)

    recipes: Mapped[list[RecipeRow]] = relationship(secondary=recipe_tags, back_populates="tags")


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(20), default="url")
    source_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="en_cola", index=True)
    stage: Mapped[str | None] = mapped_column(String(50))
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    duration_s: Mapped[float | None] = mapped_column(Float)
    recipe_id: Mapped[str | None] = mapped_column(ForeignKey("recipes.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class JobEventRow(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    tool: Mapped[str] = mapped_column(String(50))
    input: Mapped[dict | None] = mapped_column(JSON)
    output: Mapped[dict | None] = mapped_column(JSON)
    duration_ms: Mapped[int | None]
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

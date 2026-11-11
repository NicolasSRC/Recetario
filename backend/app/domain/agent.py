"""Reglas, trazabilidad y presupuesto del agente (RA-01 a RA-05).

Este módulo es puro: no conoce adaptadores ni base de datos. Solo decide qué
fuentes hacen falta y lleva la cuenta de lo que costó cada llamada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.domain.schemas import Ingredient, Recipe, RecipeDraft

# --------------------------------------------------------------------------- #
# RA-01: ¿el caption basta?

_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
_QUANTITY_LINE_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])?\s*\d+(?:[.,/]\d+)?(?:\s+\d+/\d+)?\s+\S")
_STEP_RE = re.compile(r"(?im)^\s*(?:paso\s*\d+|\d+[.)]\s+)")

_TO_TASTE = ("al gusto", "a gusto", "c/n", "cuanto baste", "opcional", "para servir")


def _quantity_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if _QUANTITY_LINE_RE.match(line))


def caption_is_complete(caption: str) -> bool:
    """RA-01: hay al menos dos ingredientes con cantidad y dos pasos marcados.

    La heurística es deliberadamente conservadora: si duda, el agente
    transcribe el audio. Un falso negativo cuesta una transcripción local; un
    falso positivo costaría datos.
    """
    if not caption.strip():
        return False
    return _quantity_lines(caption) >= 2 and len(_STEP_RE.findall(caption)) >= 2


# --------------------------------------------------------------------------- #
# RA-02: ¿faltan cantidades o pasos?


def _is_to_taste(ingredient: Ingredient) -> bool:
    haystack = " ".join(
        part for part in (ingredient.raw_text, ingredient.note, ingredient.name) if part
    ).casefold()
    return any(marker in haystack for marker in _TO_TASTE)


def missing_quantities(recipe: RecipeDraft) -> bool:
    return any(item.quantity is None and not _is_to_taste(item) for item in recipe.ingredients)


def needs_screen_text(recipe: RecipeDraft) -> bool:
    """RA-02: faltan cantidades (salvo "al gusto") o no hay pasos."""
    return missing_quantities(recipe) or not recipe.steps


def recipe_quality(recipe: Recipe) -> tuple[int, int, float]:
    """Ordena dos extracciones: más cantidades, más pasos y más confianza."""
    quantified = sum(1 for item in recipe.ingredients if item.quantity is not None)
    return (quantified, len(recipe.steps), recipe.extraction.confidence)


# --------------------------------------------------------------------------- #
# RA-03 y RA-04: presupuesto y registro


@dataclass(frozen=True, slots=True)
class AgentLimits:
    max_steps: int = 8
    max_cost_usd: float = 0.25


@dataclass(slots=True)
class ToolCall:
    """Una llamada registrada: entrada, salida, duración y costo (RA-04)."""

    step: int
    tool: str
    input: dict[str, Any]
    output: str
    duration_s: float
    cost_usd: float = 0.0
    ok: bool = True
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "tool": self.tool,
            "input": self.input,
            "output": self.output,
            "duration_s": round(self.duration_s, 4),
            "cost_usd": round(self.cost_usd, 6),
            "ok": self.ok,
            "error": self.error,
        }


@dataclass(slots=True)
class AgentTrace:
    limits: AgentLimits = field(default_factory=AgentLimits)
    calls: list[ToolCall] = field(default_factory=list)
    stopped_reason: str | None = None

    @property
    def steps(self) -> int:
        """Llamadas a herramientas; las decisiones no gastan presupuesto."""
        return sum(1 for call in self.calls if call.tool != "decision")

    @property
    def total_cost_usd(self) -> float:
        return round(sum(call.cost_usd for call in self.calls), 6)

    def add(self, call: ToolCall) -> None:
        self.calls.append(call)

    def decision(self, message: str) -> None:
        self.add(
            ToolCall(
                step=self.steps,
                tool="decision",
                input={},
                output=message,
                duration_s=0.0,
            )
        )

    def can_spend(self, cost_usd: float = 0.0) -> bool:
        if self.steps >= self.limits.max_steps:
            return False
        return self.total_cost_usd + cost_usd <= self.limits.max_cost_usd + 1e-9

    def as_dict(self) -> dict[str, Any]:
        return {
            "steps": self.steps,
            "total_cost_usd": self.total_cost_usd,
            "stopped_reason": self.stopped_reason,
            "calls": [call.as_dict() for call in self.calls],
        }

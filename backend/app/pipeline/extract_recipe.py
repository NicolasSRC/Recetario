"""Pipeline de extracción: contexto -> LLM -> ensamblado -> validación.

La parte predecible es fija (una llamada al LLM con reintentos). Las decisiones
dependientes del contenido llegan en F4, con el agente.
"""

from __future__ import annotations

from pydantic import ValidationError

from app.config import ConfigError
from app.domain.content import RecipeContext
from app.domain.schemas import Extraction, Recipe, RecipeDraft, Source
from app.domain.validation import BusinessRuleError, NotARecipeError, validate_recipe
from app.ports.llm import RecipeLLM


class ExtractionFailed(RuntimeError):
    """No se obtuvo una receta válida tras agotar los reintentos."""

    def __init__(self, attempts: int, last_error: BaseException | None) -> None:
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"no se pudo obtener una receta válida tras {attempts} intento(s): {last_error}"
        )


def build_source(context: RecipeContext, *, platform: str = "tiktok") -> Source:
    if context.metadata is None:
        raise ValueError("el contexto no tiene metadatos de origen")
    metadata = context.metadata
    return Source(
        url=metadata.canonical_url or metadata.url,
        author=metadata.author,
        platform=platform,
        captured_at=metadata.captured_at,
    )


def _infer_evidence(draft: RecipeDraft, context: RecipeContext) -> None:
    """RE-01: si el LLM no dijo la fuente, se busca el ingrediente en las fuentes."""
    for ingredient in draft.ingredients:
        if ingredient.evidence is not None:
            continue
        ingredient.evidence = context.contains(ingredient.raw_text) or context.contains(
            ingredient.name
        )


def assemble_recipe(
    draft: RecipeDraft,
    context: RecipeContext,
    *,
    platform: str = "tiktok",
    model_name: str | None = None,
) -> Recipe:
    draft = draft.model_copy(deep=True)
    _infer_evidence(draft, context)

    content = {name: getattr(draft, name) for name in RecipeDraft.model_fields}

    return Recipe(
        **content,
        source=build_source(context, platform=platform),
        extraction=Extraction(
            sources_used=context.sources_used(),
            model=model_name,
            needs_review=True,
        ),
    )


def _format_errors(exc: BaseException) -> str:
    if isinstance(exc, ValidationError):
        lines = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "(raíz)"
            lines.append(f"- {location}: {error['msg']}")
        return "\n".join(lines)
    return str(exc)


async def extract_recipe(
    context: RecipeContext,
    llm: RecipeLLM,
    *,
    max_retries: int = 2,
    platform: str = "tiktok",
    model_name: str | None = None,
) -> Recipe:
    """Extrae la receta y la valida, reintentando con el error como feedback.

    `max_retries` cuenta reintentos, así que se hacen como máximo
    `max_retries + 1` llamadas al modelo (RF-23).
    """
    attempts = max(0, max_retries) + 1
    previous_errors: str | None = None
    last_error: BaseException | None = None

    for _ in range(attempts):
        try:
            draft = await llm.extract(context, previous_errors=previous_errors)
        except (NotARecipeError, ConfigError):
            raise
        except Exception as exc:  # el proveedor puede fallar de muchas formas
            last_error = exc
            previous_errors = f"error del modelo: {exc}"
            continue

        try:
            recipe = assemble_recipe(
                draft,
                context,
                platform=platform,
                model_name=model_name,
            )
            return validate_recipe(recipe)
        except (ValidationError, BusinessRuleError) as exc:
            last_error = exc
            previous_errors = _format_errors(exc)

    raise ExtractionFailed(attempts, last_error)

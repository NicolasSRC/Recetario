"""Agente de fuentes (F4): decide qué mirar y lo deja registrado.

El pipeline fijo se encarga de lo predecible; este agente toma solo las
decisiones que dependen del contenido:

- RA-01: si el caption ya trae ingredientes y pasos, no se descarga audio ni
  se muestrean frames.
- RA-02: si faltan cantidades o pasos, se piden frames (texto en pantalla).
- RA-03: hay un máximo de pasos y un tope de costo; al agotarse, se guarda lo
  obtenido como `por_revisar`.
- RA-04: cada llamada queda registrada con entrada, salida, duración y costo.
- RA-05: si una fuente no confirma un dato, no se inventa; la validación lo
  marca para revisión.

La política es determinista a propósito: cuesta cero, es auditable y se puede
probar sin cuota de modelo. Las herramientas siguen siendo intercambiables.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any

from app.domain.agent import (
    AgentLimits,
    AgentTrace,
    ToolCall,
    caption_is_complete,
    needs_screen_text,
    recipe_quality,
)
from app.domain.content import (
    RecipeContext,
    ScreenTextResult,
    Transcript,
    VideoMetadata,
)
from app.domain.schemas import Recipe, Status
from app.domain.validation import validate_recipe
from app.pipeline.extract_recipe import ExtractionFailed, extract_recipe
from app.ports.llm import RecipeLLM

logger = logging.getLogger(__name__)


class BudgetExceeded(RuntimeError):
    """Se agotaron los pasos o el costo permitido para un video (RA-03)."""


@dataclass(slots=True)
class AgentTools:
    """Herramientas del agente, inyectadas por quien las conoce (jobs o CLI)."""

    get_metadata: Callable[[], Awaitable[VideoMetadata]]
    transcribe_audio: Callable[[], Awaitable[Transcript]] | None = None
    extract_frames: Callable[[], Awaitable[ScreenTextResult]] | None = None
    save_recipe: Callable[[Recipe], Awaitable[Recipe]] | None = None
    ask_user: Callable[[str], Awaitable[str | None]] | None = None
    before_extract: Callable[[], None] | None = None


@dataclass(slots=True)
class AgentResult:
    recipe: Recipe
    trace: AgentTrace
    skipped_audio: bool = False
    used_screen_text: bool = False


def _summarize(output: Any) -> str:
    if output is None:
        return "sin resultado"
    if isinstance(output, VideoMetadata):
        return f"caption de {len(output.caption)} caracteres, duración {output.duration_s}"
    if isinstance(output, Transcript):
        return f"{len(output.segments)} segmentos, {len(output.text)} caracteres"
    if isinstance(output, ScreenTextResult):
        return f"{len(output.items)} textos en {output.frames_analyzed} frames"
    if isinstance(output, Recipe):
        return f"{output.title}: {len(output.ingredients)} ingredientes, {len(output.steps)} pasos"
    text = str(output)
    return text[:200] + ("…" if len(text) > 200 else "")


class RecipeAgent:
    def __init__(
        self,
        tools: AgentTools,
        llm: RecipeLLM,
        *,
        limits: AgentLimits | None = None,
        trace: AgentTrace | None = None,
        max_retries: int = 2,
        platform: str = "tiktok",
        model_name: str | None = None,
        extraction_cost_usd: float = 0.0,
        frame_interval_s: float = 2.0,
        fatal_exceptions: tuple[type[BaseException], ...] = (),
    ) -> None:
        self._tools = tools
        self._llm = llm
        self._trace = trace or AgentTrace(limits=limits or AgentLimits())
        if limits is not None:
            self._trace.limits = limits
        self._max_retries = max_retries
        self._platform = platform
        self._model_name = model_name
        self._extraction_cost_usd = extraction_cost_usd
        self._frame_interval_s = frame_interval_s
        self._fatal = fatal_exceptions
        self._best: Recipe | None = None
        self._skipped_audio = False
        self._used_screen = False

    async def run(self) -> AgentResult:
        try:
            return await self._run()
        except BudgetExceeded as exc:
            self._trace.stopped_reason = str(exc)
            self._trace.decision(f"RA-03: {exc}")
            if self._best is None:
                raise
            recipe = self._for_review(self._best)
            recipe = await self._save(recipe)
            return AgentResult(
                recipe=recipe,
                trace=self._trace,
                skipped_audio=self._skipped_audio,
                used_screen_text=self._used_screen,
            )

    # ------------------------------------------------------------------ #

    async def _run(self) -> AgentResult:
        metadata = await self._call("get_metadata", {"source": "url"}, self._tools.get_metadata)
        context = RecipeContext(metadata=metadata)

        self._skipped_audio = caption_is_complete(metadata.caption)
        if self._skipped_audio:
            self._trace.decision(
                "RA-01: el caption trae ingredientes y pasos; se omiten audio y frames"
            )
        else:
            transcript = await self._transcribe()
            if transcript is not None:
                context = replace(context, transcript=transcript)

        extraction_error: ExtractionFailed | None = None
        recipe: Recipe | None = None
        try:
            recipe = await self._extract(context)
        except ExtractionFailed as exc:
            extraction_error = exc

        if recipe is None and not self._skipped_audio:
            self._trace.decision("RA-02: la primera extracción falló; se piden frames")
            frames = await self._read_frames()
            if frames is not None and frames.items:
                context = replace(context, screen_text=frames.items)
                recipe = await self._extract(context)
                self._used_screen = True

        if recipe is None:
            if extraction_error is not None:
                raise extraction_error
            raise ExtractionFailed(1, None)

        self._best = recipe

        if needs_screen_text(recipe) and not self._skipped_audio and not self._used_screen:
            frames = await self._read_frames()
            if frames is not None and frames.items:
                context = replace(context, screen_text=frames.items)
                candidate = await self._extract(context)
                self._used_screen = True
                if recipe_quality(candidate) > recipe_quality(recipe):
                    recipe = candidate
                    self._best = recipe
                    self._trace.decision(
                        "RA-02: el texto en pantalla mejora la receta; se usa esa versión"
                    )
                else:
                    self._trace.decision(
                        "RA-02: el texto en pantalla no mejora la receta; se conserva la anterior"
                    )
            elif frames is not None:
                self._trace.decision("RA-02: no se leyó texto útil en los frames")

        if needs_screen_text(recipe):
            recipe = await self._ask_for_missing(context, recipe)
            self._best = recipe

        current = recipe
        validated = await self._call(
            "validate_recipe",
            {"title": current.title},
            lambda: _validated(current),
        )
        recipe = await self._save(validated)

        return AgentResult(
            recipe=recipe,
            trace=self._trace,
            skipped_audio=self._skipped_audio,
            used_screen_text=self._used_screen,
        )

    # ------------------------------------------------------------------ #
    # Herramientas

    async def _transcribe(self) -> Transcript | None:
        if self._tools.transcribe_audio is None:
            return None
        result = await self._call(
            "transcribe_audio",
            {"source": "audio"},
            self._tools.transcribe_audio,
            optional=True,
        )
        if isinstance(result, Transcript) and result.text.strip():
            return result
        self._trace.decision("el audio no aportó texto; se continúa con el caption")
        return None

    async def _read_frames(self) -> ScreenTextResult | None:
        if self._tools.extract_frames is None:
            return None
        result = await self._call(
            "extract_frames",
            {"interval_s": self._frame_interval_s},
            self._tools.extract_frames,
            optional=True,
        )
        return result if isinstance(result, ScreenTextResult) else None

    async def _ask_for_missing(self, context: RecipeContext, recipe: Recipe) -> Recipe:
        if self._tools.ask_user is None:
            return recipe

        question = "Faltan cantidades o pasos. ¿Puedes completar la receta?"
        answer = await self._call(
            "ask_user",
            {"question": question},
            lambda: self._tools.ask_user(question),  # type: ignore[misc]
            optional=True,
        )
        if not isinstance(answer, str) or not answer.strip():
            return recipe

        # La respuesta del usuario entra como caption: es una fuente, no una
        # instrucción para el modelo (RA-06).
        metadata = context.metadata
        if metadata is not None:
            metadata = replace(
                metadata,
                caption=f"{metadata.caption}\n{answer.strip()}".strip(),
            )
        candidate = await self._extract(replace(context, metadata=metadata))
        return candidate if recipe_quality(candidate) > recipe_quality(recipe) else recipe

    async def _extract(self, context: RecipeContext) -> Recipe:
        if self._tools.before_extract is not None:
            self._tools.before_extract()

        async def run() -> Recipe:
            return await extract_recipe(
                context,
                self._llm,
                max_retries=self._max_retries,
                platform=self._platform,
                model_name=self._model_name,
            )

        return await self._call(
            "extract_recipe",
            {"sources": [source.value for source in context.sources_used()]},
            run,
            cost_usd=self._extraction_cost_usd,
        )

    async def _save(self, recipe: Recipe) -> Recipe:
        if self._tools.save_recipe is None:
            return recipe

        started = time.monotonic()
        saved = await self._tools.save_recipe(recipe)
        self._trace.add(
            ToolCall(
                step=self._trace.steps + 1,
                tool="save_recipe",
                input={"title": recipe.title},
                output=_summarize(saved),
                duration_s=time.monotonic() - started,
            )
        )
        return saved

    # ------------------------------------------------------------------ #
    # Presupuesto y registro

    async def _call(
        self,
        tool: str,
        payload: dict[str, Any],
        fn: Callable[[], Awaitable[Any]],
        *,
        optional: bool = False,
        cost_usd: float = 0.0,
    ) -> Any:
        if not self._trace.can_spend(cost_usd):
            raise BudgetExceeded(
                f"tope del agente alcanzado ({self._trace.steps}/"
                f"{self._trace.limits.max_steps} pasos, "
                f"${self._trace.total_cost_usd:.4f})"
            )

        step = self._trace.steps + 1
        started = time.monotonic()
        try:
            output = await fn()
        except Exception as exc:
            if self._fatal and isinstance(exc, self._fatal):
                raise
            self._trace.add(
                ToolCall(
                    step=step,
                    tool=tool,
                    input=payload,
                    output="error",
                    duration_s=time.monotonic() - started,
                    cost_usd=cost_usd,
                    ok=False,
                    error=str(exc)[:500],
                )
            )
            if optional:
                logger.warning("herramienta %s falló y era opcional: %s", tool, exc)
                return None
            raise

        actual_cost = cost_usd + float(getattr(output, "cost_usd", 0.0) or 0.0)
        self._trace.add(
            ToolCall(
                step=step,
                tool=tool,
                input=payload,
                output=_summarize(output),
                duration_s=time.monotonic() - started,
                cost_usd=actual_cost,
            )
        )
        return output

    def _for_review(self, recipe: Recipe) -> Recipe:
        recipe = recipe.model_copy(deep=True)
        recipe.status = Status.POR_REVISAR
        recipe.extraction.needs_review = True
        flags = list(recipe.extraction.flags)
        if "agente_presupuesto" not in flags:
            flags.append("agente_presupuesto")
        recipe.extraction.flags = flags
        return recipe


async def _validated(recipe: Recipe) -> Recipe:
    return validate_recipe(recipe)


__all__ = [
    "AgentResult",
    "AgentTools",
    "BudgetExceeded",
    "RecipeAgent",
]

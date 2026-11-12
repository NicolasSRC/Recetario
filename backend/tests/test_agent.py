from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from app.domain.agent import (
    AgentLimits,
    AgentTrace,
    ToolCall,
    caption_is_complete,
    needs_screen_text,
)
from app.domain.content import (
    RecipeContext,
    ScreenText,
    ScreenTextResult,
    Transcript,
    VideoMetadata,
)
from app.domain.schemas import Evidence, Ingredient, Recipe, RecipeDraft, Status, Step, Unit
from app.pipeline.agent import AgentTools, BudgetExceeded, RecipeAgent

CAPTION_COMPLETO = (
    "Ingredientes:\n"
    "- 2 pechugas de pollo\n"
    "- 1 limón\n"
    "\n"
    "Paso 1: Marina el pollo.\n"
    "Paso 2: Cocínalo a la plancha."
)


def _draft(*, quantity: Decimal | None = Decimal(2)) -> RecipeDraft:
    return RecipeDraft(
        title="Pollo al limón",
        language="es",
        ingredients=[
            Ingredient(
                name="pechuga de pollo",
                quantity=quantity,
                unit=Unit.UNIDAD if quantity is not None else None,
                raw_text="2 pechugas de pollo",
                evidence=Evidence.CAPTION,
            )
        ],
        steps=[
            Step(order=1, text="Marina el pollo."),
            Step(order=2, text="Cocínalo a la plancha."),
        ],
    )


class ContextLLM:
    def __init__(self, factory: Callable[[RecipeContext], RecipeDraft]) -> None:
        self._factory = factory
        self.contexts: list[RecipeContext] = []

    async def extract(
        self, context: RecipeContext, *, previous_errors: str | None = None
    ) -> RecipeDraft:
        self.contexts.append(context)
        return self._factory(context)


def _metadata(caption: str) -> VideoMetadata:
    return VideoMetadata(url="https://www.tiktok.com/@chef/video/1", caption=caption)


async def test_ra01_caption_completo_se_salta_audio_y_frames() -> None:
    calls = {"transcribe": 0, "frames": 0}
    llm = ContextLLM(lambda _context: _draft())

    async def get_metadata() -> VideoMetadata:
        return _metadata(CAPTION_COMPLETO)

    async def transcribe() -> Transcript:
        calls["transcribe"] += 1
        return Transcript(text="no debería usarse")

    async def frames() -> ScreenTextResult:
        calls["frames"] += 1
        return ScreenTextResult()

    async def save(recipe: Recipe) -> Recipe:
        return recipe.model_copy(update={"id": "rec-1"})

    agent = RecipeAgent(
        AgentTools(
            get_metadata=get_metadata,
            transcribe_audio=transcribe,
            extract_frames=frames,
            save_recipe=save,
        ),
        llm,
    )

    result = await agent.run()

    assert result.skipped_audio is True
    assert result.used_screen_text is False
    assert calls == {"transcribe": 0, "frames": 0}
    assert result.recipe.id == "rec-1"
    assert [call.tool for call in result.trace.calls if call.tool != "decision"] == [
        "get_metadata",
        "extract_recipe",
        "validate_recipe",
        "save_recipe",
    ]
    assert result.trace.steps == 4


async def test_sin_voz_continua_con_el_caption() -> None:
    # Caso real (videos 02, 03 y 10): no hay voz, pero el caption trae datos.
    llm = ContextLLM(lambda _context: _draft())

    async def get_metadata() -> VideoMetadata:
        return _metadata("Pechuga de pollo cremosa: 2 pechugas y 1 limón")

    async def transcribe() -> Transcript:
        raise ValueError("la transcripción quedó vacía (¿el video no tiene voz?)")

    agent = RecipeAgent(
        AgentTools(get_metadata=get_metadata, transcribe_audio=transcribe),
        llm,
    )

    result = await agent.run()

    assert result.recipe.title == "Pollo al limón"
    assert llm.contexts[0].transcript is None
    failed = [call for call in result.trace.calls if call.tool == "transcribe_audio"]
    assert len(failed) == 1
    assert failed[0].ok is False
    assert any(
        call.tool == "decision" and "no aportó texto" in call.output for call in result.trace.calls
    )


async def test_ra02_frames_completan_las_cantidades() -> None:
    calls = {"transcribe": 0, "frames": 0}
    llm = ContextLLM(lambda context: _draft(quantity=None) if not context.screen_text else _draft())

    async def get_metadata() -> VideoMetadata:
        return _metadata("Pollo al limón en 25 minutos")

    async def transcribe() -> Transcript:
        calls["transcribe"] += 1
        return Transcript(text="Marina el pollo y cocínalo.")

    async def frames() -> ScreenTextResult:
        calls["frames"] += 1
        return ScreenTextResult(
            items=(ScreenText(timestamp_s=2.0, text="2 pechugas de pollo"),),
            frames_analyzed=1,
        )

    agent = RecipeAgent(
        AgentTools(
            get_metadata=get_metadata,
            transcribe_audio=transcribe,
            extract_frames=frames,
        ),
        llm,
    )

    result = await agent.run()

    assert calls == {"transcribe": 1, "frames": 1}
    assert result.used_screen_text is True
    assert result.recipe.ingredients[0].quantity == Decimal(2)
    assert len(llm.contexts) == 2
    assert llm.contexts[0].screen_text == ()
    assert llm.contexts[1].screen_text[0].text == "2 pechugas de pollo"

    extract_call = next(call for call in result.trace.calls if call.tool == "extract_recipe")
    assert extract_call.input["sources"] == ["caption", "audio"]
    assert extract_call.output.startswith("Pollo al limón")
    assert extract_call.duration_s >= 0


async def test_ra03_al_agotar_pasos_guarda_por_revisar() -> None:
    llm = ContextLLM(lambda _context: _draft(quantity=None))

    async def get_metadata() -> VideoMetadata:
        return _metadata("Pollo al limón en 25 minutos")

    async def transcribe() -> Transcript:
        return Transcript(text="Marina el pollo.")

    async def frames() -> ScreenTextResult:
        return ScreenTextResult()

    agent = RecipeAgent(
        AgentTools(
            get_metadata=get_metadata,
            transcribe_audio=transcribe,
            extract_frames=frames,
        ),
        llm,
        limits=AgentLimits(max_steps=3, max_cost_usd=0.25),
    )

    result = await agent.run()

    assert result.trace.stopped_reason is not None
    assert result.recipe.status is Status.POR_REVISAR
    assert result.recipe.extraction.needs_review is True
    assert "agente_presupuesto" in result.recipe.extraction.flags
    assert any(call.tool == "decision" and "RA-03" in call.output for call in result.trace.calls)


async def test_ra03_tope_de_costo_antes_de_extraer() -> None:
    llm = ContextLLM(lambda _context: _draft())

    async def get_metadata() -> VideoMetadata:
        return _metadata("Pollo al limón en 25 minutos")

    agent = RecipeAgent(
        AgentTools(get_metadata=get_metadata),
        llm,
        limits=AgentLimits(max_steps=8, max_cost_usd=0.05),
        extraction_cost_usd=0.06,
    )

    with pytest.raises(BudgetExceeded):
        await agent.run()


def test_ra04_la_traza_guarda_entrada_salida_duracion_y_costo() -> None:
    trace = AgentTrace(limits=AgentLimits(max_steps=8, max_cost_usd=1.0))
    trace.add(
        ToolCall(
            step=1,
            tool="extract_frames",
            input={"interval_s": 2.0},
            output="2 textos en 4 frames",
            duration_s=0.25,
            cost_usd=0.02,
        )
    )

    data = trace.as_dict()

    assert data["steps"] == 1
    assert data["total_cost_usd"] == 0.02
    assert data["calls"][0] == {
        "step": 1,
        "tool": "extract_frames",
        "input": {"interval_s": 2.0},
        "output": "2 textos en 4 frames",
        "duration_s": 0.25,
        "cost_usd": 0.02,
        "ok": True,
        "error": None,
    }


def test_ra05_no_se_inventan_cantidades() -> None:
    draft = _draft(quantity=None)
    assert needs_screen_text(draft) is True

    al_gusto = _draft(quantity=None)
    al_gusto.ingredients[0].raw_text = "sal al gusto"
    al_gusto.ingredients[0].name = "sal"
    assert needs_screen_text(al_gusto) is False


def test_heuristica_del_caption() -> None:
    assert caption_is_complete(CAPTION_COMPLETO) is True
    assert caption_is_complete("Pollo al limón en 25 minutos") is False
    assert caption_is_complete("Ingredientes: 2 pechugas, 1 limón") is False


def test_heuristica_acepta_captions_en_prosa_con_vinetas_inline() -> None:
    # Estilo real de TikTok: una sola línea, viñetas y pasos numerados.
    numerado = (
        "Ingredientes: 6 cdas. mantequilla 3 dientes de ajo 1 cdta. mostaza "
        "Preparación: 1. Derrite la mantequilla. 2. Agrega el ajo y mezcla."
    )
    assert caption_is_complete(numerado) is True

    con_verbos = (
        "PECHUGAS JUGOSAS • INGREDIENTES: 3 pechugas de pollo 3 dientes de ajo "
        "1 cs. mantequilla 30 grs. miel • Haz unos cortes, salpimenta y lleva a "
        "la sartén. Añade la miel y cocina dos minutos."
    )
    assert caption_is_complete(con_verbos) is True


def test_heuristica_rechaza_solo_ingredientes_o_solo_pasos() -> None:
    solo_ingredientes = "POLLO CREMOSO -4 filetes de pechuga -1 taza de crema -2 dientes de ajo"
    assert caption_is_complete(solo_ingredientes) is False

    solo_pasos = "1. Pela las papas y córtalas. 2. Cocina la carne. 3. Añade el queso."
    assert caption_is_complete(solo_pasos) is False

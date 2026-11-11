"""Aplicación de pruebas e2e: API real con LLM simulado.

Playwright arranca este módulo con uvicorn. El pipeline, la base de datos y los
trabajos son los de verdad; solo se sustituye el modelo para no gastar cuota ni
depender de la red. La receta falsa no trae porciones, así que nace
`por_revisar` y el e2e puede aprobarla.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.config import Settings
from app.domain.schemas import Evidence, Ingredient, RecipeDraft, Step, Unit
from app.jobs.runner import ThreadJobRunner
from app.main import create_app

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "e2e.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_PATH.unlink(missing_ok=True)


class FakeLLM:
    """Devuelve siempre la misma receta, con una fuente que existe en el texto."""

    async def extract(self, context: object, *, previous_errors: str | None = None) -> RecipeDraft:
        return RecipeDraft(
            title="Pollo al limón de prueba",
            description="Receta simulada para el flujo e2e, sin llamar al modelo.",
            language="es",
            servings=None,
            prep_time_min=10,
            cook_time_min=15,
            difficulty="facil",
            ingredients=[
                Ingredient(
                    name="pechuga de pollo",
                    quantity=Decimal(2),
                    unit=Unit.UNIDAD,
                    raw_text="2 pechugas de pollo",
                    evidence=Evidence.CAPTION,
                ),
                Ingredient(
                    name="limón",
                    quantity=Decimal(1),
                    unit=Unit.UNIDAD,
                    raw_text="1 limón",
                    evidence=Evidence.CAPTION,
                ),
            ],
            steps=[
                Step(order=1, text="Marinar el pollo con el jugo de limón."),
                Step(order=2, text="Cocinarlo a la plancha 6 minutos por lado."),
                Step(order=3, text="Dejar reposar y servir."),
            ],
            tags=["pollo", "e2e"],
        )


def _fake_factory(_settings: Settings) -> tuple[FakeLLM, str]:
    return FakeLLM(), "fake-e2e"


settings = Settings(  # type: ignore[call-arg]
    _env_file=None,
    database_url=f"sqlite:///{DB_PATH.as_posix()}",
)
app = create_app(settings)
app.state.llm_factory = _fake_factory
app.state.job_runner = ThreadJobRunner(
    session_factory=app.state.session_factory,
    settings=settings,
    llm_factory=_fake_factory,
)

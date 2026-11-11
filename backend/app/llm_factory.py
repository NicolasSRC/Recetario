"""Fábrica del proveedor de LLM (RA-07, RNF-09)."""

from __future__ import annotations

from app.adapters.openai_llm import OpenAIRecipeLLM
from app.adapters.opencode_llm import OpenCodeLLM
from app.config import Settings
from app.ports.llm import RecipeLLM


def build_llm(settings: Settings, model_override: str | None = None) -> tuple[RecipeLLM, str]:
    """Devuelve (cliente, nombre del modelo) según la configuración."""
    if settings.llm_provider == "opencode":
        model = model_override or settings.opencode_model
        return (
            OpenCodeLLM(
                model=model,
                agent=settings.opencode_agent,
                executable=settings.opencode_executable,
                timeout_s=settings.opencode_timeout_s,
            ),
            model,
        )

    model = model_override or settings.llm_model
    return (
        OpenAIRecipeLLM(
            api_key=settings.require_api_key(),
            model=model,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
        ),
        model,
    )


def model_name(settings: Settings) -> str:
    return settings.opencode_model if settings.llm_provider == "opencode" else settings.llm_model

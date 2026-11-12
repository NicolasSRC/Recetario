from __future__ import annotations

from app.adapters.openai_llm import OpenAIRecipeLLM
from app.adapters.opencode_llm import OpenCodeLLM
from app.config import Settings
from app.llm_factory import build_llm


def test_proveedor_por_defecto_es_opencode() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    llm, model = build_llm(settings)
    assert isinstance(llm, OpenCodeLLM)
    assert model == "opencode/deepseek-v4.1-flash-free"


def test_proveedor_openai_usa_la_llave() -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        llm_provider="openai",
        llm_api_key="test-key",
        llm_model="gpt-test",
    )
    llm, model = build_llm(settings)
    assert isinstance(llm, OpenAIRecipeLLM)
    assert model == "gpt-test"


def test_override_de_modelo() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    _, model = build_llm(settings, "opencode/otro-modelo")
    assert model == "opencode/otro-modelo"


def test_base_url_vacia_se_trata_como_none() -> None:
    settings = Settings(_env_file=None, llm_base_url="")  # type: ignore[call-arg]

    assert settings.llm_base_url is None

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from app.adapters.opencode_llm import (
    OpenCodeError,
    OpenCodeLLM,
    OpenCodeQuotaError,
    extract_json_payload,
    parse_event_stream,
)
from app.domain.content import RecipeContext, VideoMetadata
from app.domain.schemas import RecipeDraft
from app.domain.validation import NotARecipeError


def _text_event(text: str) -> str:
    return json.dumps({"type": "text", "part": {"text": text}})


def _context() -> RecipeContext:
    return RecipeContext(
        metadata=VideoMetadata(
            url="https://www.tiktok.com/@chef/video/1",
            author="chef",
            caption="2 pechugas de pollo con 2 cucharadas de aceite de oliva.",
        )
    )


def _payload(recipe: RecipeDraft) -> str:
    return json.dumps(
        {
            "is_recipe": True,
            "not_a_recipe_reason": None,
            "recipe": json.loads(recipe.model_dump_json()),
        }
    )


def test_parse_event_stream_concatena_texto() -> None:
    stdout = f"{_text_event('Hola ')}\n{_text_event('mundo')}\n"
    text, errors = parse_event_stream(stdout)
    assert text == "Hola mundo"
    assert errors == []


def test_parse_event_stream_ignora_lineas_invalidas() -> None:
    text, errors = parse_event_stream("basura\n" + _text_event("ok"))
    assert text == "ok"
    assert errors == []


def test_parse_event_stream_detecta_error() -> None:
    stdout = json.dumps({"type": "error", "error": {"message": "boom"}})
    _, errors = parse_event_stream(stdout)
    assert len(errors) == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('Aquí está: {"a": 1} listo', '{"a": 1}'),
        ('{"a": {"b": 2}}', '{"a": {"b": 2}}'),
    ],
)
def test_extract_json_payload(raw: str, expected: str) -> None:
    assert extract_json_payload(raw) == expected


def test_extract_json_payload_sin_json() -> None:
    with pytest.raises(OpenCodeError):
        extract_json_payload("no hay nada")


async def test_extract_devuelve_el_draft(
    monkeypatch: pytest.MonkeyPatch,
    make_draft: Callable[..., RecipeDraft],
) -> None:
    draft = make_draft()

    async def fake_run(self: OpenCodeLLM, prompt: str) -> str:
        return _text_event(_payload(draft))

    monkeypatch.setattr(OpenCodeLLM, "_run", fake_run)

    result = await OpenCodeLLM().extract(_context())

    assert result.title == draft.title
    assert result.ingredients[0].name == "pechuga de pollo"


async def test_extract_no_es_receta(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        {"is_recipe": False, "not_a_recipe_reason": "es maquillaje", "recipe": None}
    )

    async def fake_run(self: OpenCodeLLM, prompt: str) -> str:
        return _text_event(payload)

    monkeypatch.setattr(OpenCodeLLM, "_run", fake_run)

    with pytest.raises(NotARecipeError):
        await OpenCodeLLM().extract(_context())


async def test_extract_json_invalido(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(self: OpenCodeLLM, prompt: str) -> str:
        return _text_event("esto no es JSON")

    monkeypatch.setattr(OpenCodeLLM, "_run", fake_run)

    with pytest.raises(OpenCodeError):
        await OpenCodeLLM().extract(_context())


async def test_cuota_agotada_se_clasifica(monkeypatch: pytest.MonkeyPatch) -> None:
    event: dict[str, Any] = {
        "type": "error",
        "error": {"type": "provider.free-limit", "message": "Free usage limit reached"},
        "retryAfterMs": 12_690_000,
    }

    async def fake_run(self: OpenCodeLLM, prompt: str) -> str:
        return json.dumps(event)

    monkeypatch.setattr(OpenCodeLLM, "_run", fake_run)

    with pytest.raises(OpenCodeQuotaError) as excinfo:
        await OpenCodeLLM().extract(_context())

    assert excinfo.value.retry_after_s == 12_690.0

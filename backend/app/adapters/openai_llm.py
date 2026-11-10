"""Adaptador del LLM con salida estructurada sobre una API compatible con OpenAI."""

from __future__ import annotations

from typing import cast

import instructor
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.adapters.llm_output import LLMOutput
from app.adapters.prompts import SYSTEM_PROMPT, build_user_prompt
from app.domain.content import RecipeContext
from app.domain.schemas import RecipeDraft
from app.domain.validation import NotARecipeError


class OpenAIRecipeLLM:
    """Implementación sobre cualquier API compatible con OpenAI."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._client = instructor.from_openai(client)
        self._model = model
        self._temperature = temperature

    async def extract(
        self,
        context: RecipeContext,
        *,
        previous_errors: str | None = None,
    ) -> RecipeDraft:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(context, previous_errors)},
        ]

        response = await self._client.chat.completions.create(
            model=self._model,
            response_model=LLMOutput,
            messages=messages,
            temperature=self._temperature,
            max_retries=0,
        )
        output = cast(LLMOutput, response)

        if not output.is_recipe or output.recipe is None:
            raise NotARecipeError(output.not_a_recipe_reason or "el video no contiene una receta")

        return output.recipe

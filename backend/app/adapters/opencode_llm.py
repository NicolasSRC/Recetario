"""Adaptador que usa OpenCode local como proveedor de LLM (RA-07).

Los modelos gratuitos de OpenCode solo se pueden invocar desde OpenCode, no desde
un cliente externo. Este adaptador ejecuta `opencode run` con un agente sin
herramientas y parsea el flujo de eventos JSON.

Ventajas: no requiere llave de API y usa el modelo configurado en el repo.
Límites: depende del ejecutable local y de la cuota gratuita del proveedor.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.adapters.llm_output import LLMOutput
from app.adapters.prompts import SYSTEM_PROMPT, build_user_prompt
from app.config import ConfigError
from app.domain.content import RecipeContext
from app.domain.schemas import RecipeDraft
from app.domain.validation import NotARecipeError


class OpenCodeError(RuntimeError):
    """Fallo al ejecutar OpenCode o al interpretar su respuesta."""


class OpenCodeQuotaError(OpenCodeError):
    """La cuota gratuita del proveedor se agotó."""

    def __init__(self, message: str, *, retry_after_s: float | None = None) -> None:
        self.retry_after_s = retry_after_s
        super().__init__(message)


def parse_event_stream(stdout: str) -> tuple[str, list[dict[str, Any]]]:
    """Extrae el texto del asistente y los eventos de error del flujo JSONL."""
    texts: list[str] = []
    errors: list[dict[str, Any]] = []

    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue

        if event.get("type") == "text":
            part = event.get("part") or {}
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
        elif event.get("type") == "error":
            errors.append(event)

    return "".join(texts).strip(), errors


def extract_json_payload(text: str) -> str:
    """Aísla el objeto JSON aunque venga en un bloque de código o con prosa."""
    cleaned = text.strip()

    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise OpenCodeError("la respuesta del modelo no contiene un objeto JSON")

    return cleaned[start : end + 1]


def _resolve_executable(name: str) -> str:
    """En Windows, PowerShell bloquea el .ps1: se usa el .cmd equivalente."""
    resolved = shutil.which(name)
    if resolved is None:
        raise ConfigError(
            f"no se encontró el ejecutable '{name}'. Instala OpenCode o ajusta "
            "RECETARIO_OPENCODE_EXECUTABLE."
        )
    if resolved.lower().endswith(".ps1"):
        cmd = Path(resolved).with_suffix(".cmd")
        if cmd.exists():
            return str(cmd)
    return resolved


class OpenCodeLLM:
    def __init__(
        self,
        *,
        model: str = "opencode/deepseek-v4.1-flash-free",
        agent: str = "recetario-extractor",
        executable: str = "opencode",
        timeout_s: float = 300.0,
    ) -> None:
        self._model = model
        self._agent = agent
        self._executable = executable
        self._timeout_s = timeout_s

    async def extract(
        self,
        context: RecipeContext,
        *,
        previous_errors: str | None = None,
    ) -> RecipeDraft:
        prompt = f"{SYSTEM_PROMPT}\n\n{build_user_prompt(context, previous_errors, json_only=True)}"
        stdout = await self._run(prompt)
        text, errors = parse_event_stream(stdout)

        if errors:
            self._raise_from_events(errors)

        if not text:
            raise OpenCodeError("OpenCode no devolvió texto")

        payload = extract_json_payload(text)
        try:
            output = LLMOutput.model_validate_json(payload)
        except ValidationError as exc:
            raise OpenCodeError(f"el modelo devolvió un JSON inválido: {exc}") from exc

        if not output.is_recipe or output.recipe is None:
            raise NotARecipeError(output.not_a_recipe_reason or "el video no contiene una receta")

        return output.recipe

    # ------------------------------------------------------------------ #

    async def _run(self, prompt: str) -> str:
        executable = _resolve_executable(self._executable)
        args = [
            executable,
            "run",
            "--agent",
            self._agent,
            "--model",
            self._model,
            "--format",
            "json",
            prompt,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise ConfigError(f"no se pudo ejecutar {executable}") from exc
        except OSError as exc:
            raise ConfigError(
                f"no se pudo ejecutar {executable}: {exc}. En Windows prueba con el .cmd"
            ) from exc

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout_s
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            raise OpenCodeError(
                f"OpenCode tardó más de {self._timeout_s:.0f}s en responder"
            ) from None

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")

        if process.returncode != 0 and not stdout.strip():
            detail = stderr.strip()[:500] or "sin salida"
            raise OpenCodeError(f"OpenCode falló con código {process.returncode}: {detail}")

        return stdout

    @staticmethod
    def _raise_from_events(errors: list[dict[str, Any]]) -> None:
        event = errors[-1]
        error = event.get("error") or {}
        message = error.get("message") or "error desconocido de OpenCode"

        if error.get("type") == "provider.free-limit":
            retry_ms = event.get("retryAfterMs") or error.get("retryAfterMs")
            retry_after = float(retry_ms) / 1000 if retry_ms else None
            raise OpenCodeQuotaError(message, retry_after_s=retry_after)

        raise OpenCodeError(message)

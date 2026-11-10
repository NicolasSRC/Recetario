"""Configuración por variables de entorno (RA-07, RNF-04)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """Falta configuración obligatoria o una dependencia opcional."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RECETARIO_",
        extra="ignore",
    )

    # Proveedor del LLM: opencode (local, sin llave) u openai (API compatible)
    llm_provider: Literal["opencode", "openai"] = "opencode"

    # LLM por API compatible con OpenAI
    llm_api_key: SecretStr | None = None
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    llm_temperature: float = 0.0

    # LLM a través de OpenCode local
    opencode_model: str = "opencode/deepseek-v4.1-flash-free"
    opencode_agent: str = "recetario-extractor"
    opencode_executable: str = "opencode"
    opencode_timeout_s: float = 300.0

    # Validación y costo
    max_validation_retries: int = 2
    max_cost_usd_per_video: float = 0.25

    # Base de datos (F2)
    database_url: str = "sqlite:///./data/recetario.db"

    # Transcripción
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # Archivos temporales (RF-14)
    tmp_dir: Path = Path("data/tmp")

    def require_api_key(self) -> str:
        if self.llm_api_key is None or not self.llm_api_key.get_secret_value().strip():
            raise ConfigError(
                "falta RECETARIO_LLM_API_KEY. Copia .env.example a .env y rellena la llave."
            )
        return self.llm_api_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

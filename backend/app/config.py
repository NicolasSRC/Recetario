"""Configuración por variables de entorno (RA-07, RNF-04)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
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

    @field_validator("llm_base_url", mode="before")
    @classmethod
    def _empty_base_url_is_none(cls, value: object) -> object:
        # Docker Compose pasa `RECETARIO_LLM_BASE_URL=` cuando no se define;
        # un string vacío no es una URL válida para el cliente de OpenAI.
        return None if isinstance(value, str) and not value.strip() else value

    # LLM a través de OpenCode local
    opencode_model: str = "opencode/deepseek-v4.1-flash-free"
    opencode_agent: str = "recetario-extractor"
    opencode_executable: str = "opencode"
    opencode_timeout_s: float = 300.0

    # Validación y costo
    max_validation_retries: int = 2
    max_cost_usd_per_video: float = 0.25

    # Base de datos (F2). En Docker se usa Postgres con psycopg.
    database_url: str = "sqlite:///./data/recetario.db"

    # Cola de trabajos (F5): thread para desarrollo local, celery en Docker.
    job_runner: Literal["thread", "celery"] = "thread"
    redis_url: str = "redis://127.0.0.1:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    job_max_retries: int = 3
    job_retry_backoff_s: float = 5.0
    job_retry_backoff_max_s: float = 300.0

    # CORS para el frontend del libro (F3)
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    # En desarrollo el frontend puede cambiar de puerto (3000, 3001…).
    cors_origin_regex: str = r"http://(localhost|127\.0\.0\.1):\d+"

    # Transcripción
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # F4: texto en pantalla y agente
    frames_enabled: bool = True
    frame_interval_s: float = 2.0
    max_frames_per_video: int = 24
    screen_text_reader: Literal["tesseract", "vision", "none"] = "tesseract"
    tesseract_lang: str = "spa+eng"
    tesseract_min_confidence: int = 60
    vision_model: str = "gpt-4o-mini"
    vision_api_key: SecretStr | None = None
    vision_base_url: str | None = None
    vision_cost_usd_per_frame: float = 0.0
    max_agent_steps: int = 8
    llm_cost_usd_per_extraction: float = 0.0

    # Archivos temporales (RF-14)
    tmp_dir: Path = Path("data/tmp")

    def require_api_key(self) -> str:
        if self.llm_api_key is None or not self.llm_api_key.get_secret_value().strip():
            raise ConfigError(
                "falta RECETARIO_LLM_API_KEY. Copia .env.example a .env y rellena la llave."
            )
        return self.llm_api_key.get_secret_value()

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

"""Fábrica del lector de texto en pantalla (RNF-09, F4).

`tesseract` es local y barato; `vision` usa un modelo con imágenes. Cambiar de
uno a otro es una variable de entorno (`RECETARIO_SCREEN_TEXT_READER`).
"""

from __future__ import annotations

from app.adapters.frames import FFmpegFrameSampler, VideoScreenTextReader
from app.adapters.ocr import TesseractScreenTextReader
from app.adapters.vision import VisionScreenTextReader
from app.config import ConfigError, Settings
from app.ports import ScreenTextExtractor, ScreenTextReader


def build_frame_reader(settings: Settings) -> ScreenTextReader | None:
    if not settings.frames_enabled or settings.screen_text_reader == "none":
        return None

    if settings.screen_text_reader == "vision":
        key = settings.vision_api_key or settings.llm_api_key
        if key is None:
            raise ConfigError(
                "la lectura por visión necesita RECETARIO_VISION_API_KEY (o RECETARIO_LLM_API_KEY)."
            )
        return VisionScreenTextReader(
            api_key=key.get_secret_value(),
            model=settings.vision_model,
            base_url=settings.vision_base_url or settings.llm_base_url,
        )

    return TesseractScreenTextReader(
        lang=settings.tesseract_lang,
        min_confidence=settings.tesseract_min_confidence,
    )


def build_video_screen_text_reader(settings: Settings) -> ScreenTextExtractor | None:
    reader = build_frame_reader(settings)
    if reader is None:
        return None

    cost_per_frame = (
        settings.vision_cost_usd_per_frame if settings.screen_text_reader == "vision" else 0.0
    )
    return VideoScreenTextReader(
        sampler=FFmpegFrameSampler(max_frames=settings.max_frames_per_video),
        reader=reader,
        interval_s=settings.frame_interval_s,
        max_frames=settings.max_frames_per_video,
        cost_per_frame_usd=cost_per_frame,
    )

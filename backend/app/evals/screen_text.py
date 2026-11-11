"""Eval de texto en pantalla: OCR vs visión sobre los mismos frames (F4).

Uso:
    python -m app.evals.screen_text --video ruta.mp4 --expected fixtures/screen_text_01.txt \
        --readers tesseract,vision --out evals/reports/screen_text.json

No descarga nada ni llama a TikTok: recibe un video local y el texto esperado.
Así la comparación es reproducible y se puede repetir con los 15 videos.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path

from app.adapters.frames import FFmpegFrameSampler
from app.config import ConfigError, get_settings
from app.vision_factory import build_frame_reader

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(char for char in normalized if not unicodedata.combining(char))
    return [token for token in _TOKEN_RE.findall(plain) if len(token) > 1]


def token_f1(expected: str, actual: str) -> float:
    """F1 por multiconjunto de palabras: mide lo que se leyó y lo que sobra."""
    expected_tokens = Counter(tokenize(expected))
    actual_tokens = Counter(tokenize(actual))
    if not expected_tokens or not actual_tokens:
        return 0.0

    overlap = sum((expected_tokens & actual_tokens).values())
    precision = overlap / sum(actual_tokens.values())
    recall = overlap / sum(expected_tokens.values())
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


async def evaluate(
    video: Path,
    expected: str,
    readers: list[str],
    *,
    interval_s: float,
) -> dict[str, object]:
    settings = get_settings()
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="recetario-eval-", dir=settings.tmp_dir))

    report: dict[str, object] = {
        "video": str(video),
        "interval_s": interval_s,
        "readers": {},
    }
    try:
        sampler = FFmpegFrameSampler(max_frames=settings.max_frames_per_video)
        frames = await sampler.sample(video, work_dir, interval_s)
        results: dict[str, object] = {}

        for name in readers:
            reader = build_frame_reader(
                settings.model_copy(
                    update={
                        "screen_text_reader": name,
                        "frame_interval_s": interval_s,
                    }
                )
            )
            if reader is None:
                results[name] = {"error": "lector deshabilitado"}
                continue
            try:
                texts = [await reader.read(frame) for frame in frames]
            except ConfigError as exc:
                results[name] = {"error": str(exc)}
                continue

            actual = "\n".join(text for text in texts if text.strip())
            results[name] = {
                "f1": token_f1(expected, actual),
                "frames": len(frames),
                "text": actual,
            }

        report["readers"] = results
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.evals.screen_text",
        description="Compara lectores de texto en pantalla sobre un video local.",
    )
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument(
        "--readers",
        default="tesseract,vision",
        help="Lectores separados por coma (tesseract, vision)",
    )
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    expected = args.expected.read_text(encoding="utf-8")
    readers = [name.strip() for name in args.readers.split(",") if name.strip()]

    try:
        report = asyncio.run(evaluate(args.video, expected, readers, interval_s=args.interval))
    except (FileNotFoundError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
        print(f"reporte guardado en {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

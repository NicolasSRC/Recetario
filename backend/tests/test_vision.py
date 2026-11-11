from __future__ import annotations

import asyncio
from pathlib import Path

import openai
import pytest

from app.adapters.vision import VisionScreenTextReader
from app.config import ConfigError
from app.domain.content import Frame


def test_vision_envia_el_frame_y_transcribe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"jpeg-falso")
    captured: dict[str, object] = {}

    class Message:
        content = "200 g de harina\n2 huevos"

    class Choice:
        message = Message()

    class Response:
        choices = (Choice(),)

    class Completions:
        def create(self, **kwargs: object) -> Response:
            captured.update(kwargs)
            return Response()

    class Chat:
        completions = Completions()

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured["client"] = kwargs
            self.chat = Chat()

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    reader = VisionScreenTextReader(api_key="test-key", model="vision-test")

    text = asyncio.run(reader.read(Frame(path=image, timestamp_s=0.0)))

    assert text == "200 g de harina\n2 huevos"
    assert captured["model"] == "vision-test"
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert "DATO" in messages[0]["content"]
    image_url = messages[1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")


def test_vision_sin_llave_avisa() -> None:
    with pytest.raises(ConfigError, match="VISION_API_KEY"):
        VisionScreenTextReader(api_key="  ", model="vision-test")

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from app.adapters.frames import FFmpegFrameSampler, VideoScreenTextReader
from app.config import ConfigError
from app.domain.content import Frame


class FakeSampler:
    def __init__(self, total: int, interval: float = 2.0) -> None:
        self._total = total
        self._interval = interval
        self.calls: list[tuple[Path, Path, float]] = []

    async def sample(
        self, video_path: Path, dest_dir: Path, interval_s: float
    ) -> tuple[Frame, ...]:
        self.calls.append((video_path, dest_dir, interval_s))
        return tuple(
            Frame(path=Path(f"frame-{index}.jpg"), timestamp_s=index * self._interval)
            for index in range(self._total)
        )


class FakeReader:
    def __init__(self, texts: dict[float, str]) -> None:
        self._texts = texts
        self.seen: list[float] = []

    async def read(self, frame: Frame) -> str:
        self.seen.append(frame.timestamp_s)
        return self._texts.get(frame.timestamp_s, "")


def test_muestrea_frames_con_ffmpeg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    dest = tmp_path / "frames"
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        dest.mkdir(parents=True, exist_ok=True)
        for index in range(1, 4):
            (dest / f"frame_{index:04d}.jpg").write_bytes(b"jpg")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(shutil, "which", lambda _name: "C:/ffmpeg.exe")
    monkeypatch.setattr(subprocess, "run", fake_run)

    frames = asyncio.run(FFmpegFrameSampler(max_frames=3).sample(video, dest, 2.0))

    assert [frame.timestamp_s for frame in frames] == [0.0, 2.0, 4.0]
    assert "fps=1/2" in commands[0]
    assert commands[0][commands[0].index("-frames:v") + 1] == "3"


def test_sin_ffmpeg_avisa_de_la_dependencia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(ConfigError, match="ffmpeg"):
        asyncio.run(FFmpegFrameSampler().sample(video, tmp_path / "frames", 2.0))


def test_video_screen_text_reader_deduplica_y_limita(tmp_path: Path) -> None:
    sampler = FakeSampler(total=4)
    reader = FakeReader(
        {
            0.0: "200 g de harina",
            2.0: "200 g   de harina",
            4.0: "PASOS",
            6.0: "no se analiza",
        }
    )
    video_reader = VideoScreenTextReader(
        sampler=sampler,
        reader=reader,
        interval_s=2.0,
        max_frames=3,
        cost_per_frame_usd=0.01,
    )

    result = asyncio.run(video_reader.read(tmp_path / "video.mp4", tmp_path / "frames"))

    assert [item.text for item in result.items] == ["200 g de harina", "PASOS"]
    assert result.frames_analyzed == 3
    assert result.cost_usd == 0.03
    assert reader.seen == [0.0, 2.0, 4.0]

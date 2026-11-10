from __future__ import annotations

import pytest

from app.domain.urls import InvalidUrlError, normalize_tiktok_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://vm.tiktok.com/ZM12345/", "https://vm.tiktok.com/ZM12345/"),
        ("vm.tiktok.com/ZM12345", "https://vm.tiktok.com/ZM12345"),
        (
            "https://www.tiktok.com/@chef/video/123?is_from_webapp=1",
            "https://www.tiktok.com/@chef/video/123?is_from_webapp=1",
        ),
        ("http://tiktok.com/@chef/video/123", "https://tiktok.com/@chef/video/123"),
        ("https://www.tiktok.com//@chef//video/123", "https://www.tiktok.com/@chef/video/123"),
    ],
)
def test_normalize_tiktok_url(raw: str, expected: str) -> None:
    assert normalize_tiktok_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "https://youtube.com/watch?v=1",
        "https://tiktok.com.evil.com/@chef/video/1",
        "ftp://tiktok.com/video/1",
        "https://192.168.1.10/video/1",
    ],
)
def test_normalize_tiktok_url_rechaza(raw: str) -> None:
    with pytest.raises(InvalidUrlError):
        normalize_tiktok_url(raw)

import os
import tempfile
from pathlib import Path
from typing import Dict

import pytest

from src.models.tile_server import TileServer
from src.services.tile_download_service import TileDownloadService


class DummyResponse:
    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise Exception(f"HTTP {self.status_code}")


class DummySession:
    def __init__(self, url_to_payload: Dict[str, bytes]):
        self.url_to_payload = url_to_payload

    def get(self, url, headers=None, timeout=None):
        payload = self.url_to_payload.get(url)
        if payload is None:
            return DummyResponse(404, b"")
        return DummyResponse(200, payload)


def make_service_with_mocked_session(url_to_payload: Dict[str, bytes]) -> TileDownloadService:
    service = TileDownloadService(max_workers=2, retry_attempts=1, timeout=5)

    def create_session_override():
        return DummySession(url_to_payload)

    # Monkeypatch instance method
    service.create_session = create_session_override  # type: ignore
    return service


def test_vector_then_raster_fallback_skips_empty_and_uses_next(tmp_path: Path):
    # Arrange: vector server returns empty, raster returns small PNG bytes
    vector = TileServer(name="VectorA", url="https://v.example.com/{z}/{x}/{y}.pbf", headers={}, tile_type="vector")
    raster = TileServer(name="RasterB", url="https://r.example.com/{z}/{x}/{y}.png", headers={}, tile_type="raster")

    z, x, y = 5, 10, 12
    vector_url = vector.get_tile_url(z, x, y)
    raster_url = raster.get_tile_url(z, x, y)

    # Fake PNG header bytes + some body
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"valid"

    service = make_service_with_mocked_session({
        vector_url: b"",  # empty content should be rejected
        raster_url: png_bytes,
    })

    out_dir = tmp_path.as_posix()
    result = service.download_tiles_batch([(z, x, y)], out_dir, "testRegion", [vector, raster])

    assert result["downloaded"] == 1
    tile_path = tmp_path / "testRegion" / "raster" / raster.name / str(z) / str(x) / f"{y}.png"
    assert tile_path.exists() and tile_path.stat().st_size > 0


def test_skip_existing_non_empty_but_not_zero_byte(tmp_path: Path):
    raster = TileServer(name="RasterB", url="https://r.example.com/{z}/{x}/{y}.png", headers={}, tile_type="raster")
    z, x, y = 3, 1, 2
    url = raster.get_tile_url(z, x, y)

    service = make_service_with_mocked_session({url: b"newcontent"})

    # Pre-create a non-empty file
    out_dir = tmp_path.as_posix()
    tile_dir = tmp_path / "testRegion" / "raster" / raster.name / str(z) / str(x)
    tile_dir.mkdir(parents=True, exist_ok=True)
    tile_path = tile_dir / f"{y}.png"
    tile_path.write_bytes(b"oldcontent")

    result = service.download_tiles_batch([(z, x, y)], out_dir, "testRegion", [raster])
    assert result["downloaded"] == 1
    # Must not overwrite existing non-empty file (size stays as before or >= existing)
    assert tile_path.read_bytes() == b"oldcontent"



"""POST /v1/image-to-video."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ltx_api.config import Settings
from ltx_api.main import create_app


@pytest.fixture
def client(tmp_path: Path, test_video_path: Path) -> TestClient:
  app = create_app(
    settings=Settings(
      auth_token="",
      inference_backend="mock",
      storage_dir=tmp_path / "storage",
      public_base_url="http://testserver",
    ),
  )
  return TestClient(app)


def test_image_to_video_via_ltx_uri(client: TestClient, test_video_path: Path) -> None:
  # upload an image file via PUT
  up = client.post("/v1/upload").json()
  uid = up["storage_uri"].replace("ltx://uploads/", "")
  path = up["upload_url"].replace("http://testserver", "")
  png_bytes = b"\x89PNG\r\n\x1a\n"
  client.put(path, content=png_bytes, headers={"Content-Type": "image/png"})
  r = client.post(
    "/v1/image-to-video",
    json={
      "image_uri": up["storage_uri"],
      "prompt": "move",
      "model": "ltx-2-3-fast",
      "duration": 6,
      "resolution": "1920x1080",
    },
  )
  assert r.status_code == 200
  assert r.content == test_video_path.read_bytes()

"""POST /v1/retake and /v1/extend."""

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


def test_retake(client: TestClient, test_video_path: Path) -> None:
  up = client.post("/v1/upload").json()
  path = up["upload_url"].replace("http://testserver", "")
  client.put(path, content=test_video_path.read_bytes(), headers={"Content-Type": "video/mp4"})
  r = client.post(
    "/v1/retake",
    json={
      "video_uri": up["storage_uri"],
      "start_time": 0.0,
      "duration": 2.0,
      "prompt": "fix",
      "mode": "replace_audio_and_video",
    },
  )
  assert r.status_code == 200
  assert r.content == test_video_path.read_bytes()


def test_extend(client: TestClient, test_video_path: Path) -> None:
  up = client.post("/v1/upload").json()
  path = up["upload_url"].replace("http://testserver", "")
  client.put(path, content=test_video_path.read_bytes(), headers={"Content-Type": "video/mp4"})
  r = client.post(
    "/v1/extend",
    json={
      "video_uri": up["storage_uri"],
      "duration": 3.0,
      "prompt": "continue",
      "mode": "end",
    },
  )
  assert r.status_code == 200
  assert r.content == test_video_path.read_bytes()

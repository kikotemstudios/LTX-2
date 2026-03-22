"""POST /v1/audio-to-video."""

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


def test_audio_to_video_requires_prompt_or_image(client: TestClient) -> None:
  r = client.post(
    "/v1/audio-to-video",
    json={"audio_uri": "ltx://uploads/x", "model": "ltx-2-3-pro"},
  )
  assert r.status_code == 422


def test_audio_to_video_ok(client: TestClient, test_video_path: Path, tmp_path: Path) -> None:
  up = client.post("/v1/upload").json()
  path = up["upload_url"].replace("http://testserver", "")
  wav = Path(__file__).resolve().parent / "fixtures" / "test_audio.wav"
  client.put(path, content=wav.read_bytes(), headers={"Content-Type": "audio/wav"})
  r = client.post(
    "/v1/audio-to-video",
    json={
      "audio_uri": up["storage_uri"],
      "prompt": "sync",
      "model": "ltx-2-3-pro",
      "resolution": "1920x1080",
    },
  )
  assert r.status_code == 200
  assert r.content == test_video_path.read_bytes()

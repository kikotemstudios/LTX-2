"""POST /v1/text-to-video."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ltx_api.config import Settings
from ltx_api.main import create_app


@pytest.fixture
def t2v_app(tmp_path: Path, test_video_path: Path):
  return create_app(
    settings=Settings(
      auth_token="",
      inference_backend="mock",
      storage_dir=tmp_path / "storage",
      public_base_url="http://testserver",
    ),
  )


def _valid_payload() -> dict:
  return {
    "prompt": "A cat",
    "model": "ltx-2-3-fast",
    "duration": 6,
    "resolution": "1920x1080",
    "fps": 24,
    "generate_audio": True,
  }


def test_text_to_video_returns_mp4(t2v_app, test_video_path: Path) -> None:
  client = TestClient(t2v_app)
  r = client.post("/v1/text-to-video", json=_valid_payload())
  assert r.status_code == 200
  assert r.headers.get("content-type", "").startswith("application/octet-stream")
  assert "x-request-id" in r.headers
  assert r.content == test_video_path.read_bytes()


def test_text_to_video_requires_fields(t2v_app) -> None:
  client = TestClient(t2v_app)
  r = client.post("/v1/text-to-video", json={"prompt": "x"})
  assert r.status_code == 422
  body = r.json()
  assert body["type"] == "error"


def test_text_to_video_invalid_model(t2v_app) -> None:
  client = TestClient(t2v_app)
  p = _valid_payload()
  p["model"] = "not-a-model"
  r = client.post("/v1/text-to-video", json=p)
  assert r.status_code == 422

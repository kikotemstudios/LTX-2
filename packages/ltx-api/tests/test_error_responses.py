"""Error JSON matches commercial shape { type: error, error: { type, message } }."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from ltx_api.config import Settings
from ltx_api.main import create_app
from ltx_api.services.vastai_client import VastAPIError


@pytest.fixture
def app_minimal():
  return create_app(
    settings=Settings(
      auth_token="",
      inference_backend="mock",
      storage_dir="/tmp/ltx-api-test-storage",
      public_base_url="http://testserver",
    ),
  )


def _assert_error_shape(body: dict) -> None:
  assert body["type"] == "error"
  assert "error" in body
  assert "type" in body["error"]
  assert "message" in body["error"]


def test_validation_error_uses_commercial_shape(app_minimal) -> None:
  client = TestClient(app_minimal)
  r = client.post(
    "/v1/text-to-video",
    json={"prompt": "x"},
  )
  assert r.status_code == 422
  body = r.json()
  _assert_error_shape(body)


def test_not_found_uses_commercial_shape(app_minimal) -> None:
  client = TestClient(app_minimal)
  r = client.get("/does-not-exist")
  assert r.status_code == 404
  body = r.json()
  _assert_error_shape(body)


def test_route_404_preserves_specific_message(app_minimal) -> None:
  """Normalize404Middleware must not clobber HTTPException(404, error_payload(...))."""
  client = TestClient(app_minimal)
  r = client.get("/v1/jobs/00000000-0000-0000-0000-000000000000")
  assert r.status_code == 404
  body = r.json()
  _assert_error_shape(body)
  assert body["error"]["message"] == "Unknown job"


def test_vast_api_error_returns_502_gpu_provider_shape(tmp_path) -> None:
  app = create_app(
    settings=Settings(
      auth_token="",
      inference_backend="mock",
      storage_dir=tmp_path / "storage",
      public_base_url="http://testserver",
    ),
  )
  app.state.inference = MagicMock()
  app.state.inference.text_to_video.side_effect = VastAPIError("Vast: insufficient balance")
  client = TestClient(app)
  r = client.post(
    "/v1/text-to-video",
    json={
      "prompt": "x",
      "model": "ltx-2-3-fast",
      "duration": 6,
      "resolution": "1920x1080",
      "fps": 24,
      "generate_audio": True,
    },
  )
  assert r.status_code == 502
  body = r.json()
  _assert_error_shape(body)
  assert body["error"]["type"] == "gpu_provider_error"
  assert "Vast" in body["error"]["message"]

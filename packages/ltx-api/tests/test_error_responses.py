"""Error JSON matches commercial shape { type: error, error: { type, message } }."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ltx_api.config import Settings
from ltx_api.main import create_app


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

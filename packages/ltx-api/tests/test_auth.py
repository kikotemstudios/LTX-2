"""Auth: Bearer token when LTX_API_AUTH_TOKEN is set."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ltx_api.config import Settings
from ltx_api.main import create_app


@pytest.fixture
def auth_token() -> str:
  return "test-secret-token"


@pytest.fixture
def app_with_auth(auth_token: str):
  return create_app(
    settings=Settings(
      auth_token=auth_token,
      inference_backend="mock",
      storage_dir="/tmp/ltx-api-test-storage",
      public_base_url="http://testserver",
    ),
  )


@pytest.fixture
def app_no_auth():
  return create_app(
    settings=Settings(
      auth_token="",
      inference_backend="mock",
      storage_dir="/tmp/ltx-api-test-storage",
      public_base_url="http://testserver",
    ),
  )


def test_health_public_without_auth(app_with_auth) -> None:
  client = TestClient(app_with_auth)
  r = client.get("/health")
  assert r.status_code == 200
  assert r.json().get("status") == "ok"


def test_protected_route_requires_auth_when_token_set(app_with_auth) -> None:
  client = TestClient(app_with_auth)
  r = client.get("/v1/_auth_probe")
  assert r.status_code == 401
  body = r.json()
  assert body["type"] == "error"
  assert body["error"]["type"] == "authentication_error"


def test_protected_route_accepts_valid_bearer(app_with_auth, auth_token: str) -> None:
  client = TestClient(app_with_auth)
  r = client.get("/v1/_auth_probe", headers={"Authorization": f"Bearer {auth_token}"})
  assert r.status_code == 200
  assert r.json() == {"ok": True}


def test_invalid_bearer_rejected(app_with_auth) -> None:
  client = TestClient(app_with_auth)
  r = client.get("/v1/_auth_probe", headers={"Authorization": "Bearer wrong"})
  assert r.status_code == 401


def test_auth_disabled_allows_probe_without_header(app_no_auth) -> None:
  client = TestClient(app_no_auth)
  r = client.get("/v1/_auth_probe")
  assert r.status_code == 200
  assert r.json() == {"ok": True}

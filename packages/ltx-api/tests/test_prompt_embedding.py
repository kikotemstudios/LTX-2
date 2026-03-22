"""POST /v1/prompt-embedding."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ltx_api.config import Settings
from ltx_api.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
  app = create_app(
    settings=Settings(
      auth_token="",
      inference_backend="mock",
      storage_dir=tmp_path / "storage",
      public_base_url="http://testserver",
    ),
  )
  return TestClient(app)


def test_prompt_embedding_returns_bytes(client: TestClient) -> None:
  r = client.post("/v1/prompt-embedding", json={"prompt": "hello"})
  assert r.status_code == 200
  assert r.content == b"mock-embedding:hello"
  assert "x-request-id" in r.headers

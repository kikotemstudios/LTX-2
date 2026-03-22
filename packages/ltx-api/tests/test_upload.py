"""POST /v1/upload and local storage PUT."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ltx_api.config import Settings
from ltx_api.main import create_app


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
  d = tmp_path / "storage"
  d.mkdir(parents=True)
  return d


@pytest.fixture
def upload_app(storage_root: Path):
  return create_app(
    settings=Settings(
      auth_token="",
      inference_backend="mock",
      storage_dir=storage_root,
      public_base_url="http://testserver",
    ),
  )


def test_post_upload_returns_shape(upload_app) -> None:
  client = TestClient(upload_app)
  r = client.post("/v1/upload")
  assert r.status_code == 200
  data = r.json()
  assert "upload_url" in data
  assert "storage_uri" in data
  assert data["storage_uri"].startswith("ltx://uploads/")
  assert "expires_at" in data
  assert "required_headers" in data
  assert isinstance(data["required_headers"], dict)
  assert data["upload_url"].startswith("http://testserver/v1/storage/")


def test_put_storage_uploads_file(upload_app, storage_root: Path) -> None:
  client = TestClient(upload_app)
  up = client.post("/v1/upload").json()
  upload_url = up["upload_url"]
  # upload_url is absolute path on testserver
  path = upload_url.replace("http://testserver", "")
  put = client.put(path, content=b"hello", headers={"Content-Type": "application/octet-stream"})
  assert put.status_code == 204
  # uuid from storage_uri ltx://uploads/{uuid}
  uri = up["storage_uri"]
  uid = uri.replace("ltx://uploads/", "")
  stored = storage_root / "uploads" / uid
  assert stored.read_bytes() == b"hello"


def test_upload_requires_auth_when_configured(storage_root: Path) -> None:
  app = create_app(
    settings=Settings(
      auth_token="secret",
      inference_backend="mock",
      storage_dir=storage_root,
      public_base_url="http://testserver",
    ),
  )
  client = TestClient(app)
  assert client.post("/v1/upload").status_code == 401
  assert client.post("/v1/upload", headers={"Authorization": "Bearer secret"}).status_code == 200

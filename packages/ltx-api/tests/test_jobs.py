"""Async jobs."""

from __future__ import annotations

import time
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


def test_async_text_to_video_job(client: TestClient, test_video_path: Path) -> None:
  r = client.post(
    "/v1/async/text-to-video",
    json={
      "prompt": "x",
      "model": "ltx-2-3-fast",
      "duration": 6,
      "resolution": "1920x1080",
    },
  )
  assert r.status_code == 200
  job_id = r.json()["job_id"]
  assert r.json()["status"] == "pending"
  for _ in range(200):
    st = client.get(f"/v1/jobs/{job_id}").json()
    if st["status"] == "completed":
      break
    if st["status"] == "failed":
      raise AssertionError(st)
    time.sleep(0.01)
  else:
    raise AssertionError("job did not complete")
  dl = client.get(f"/v1/jobs/{job_id}/download")
  assert dl.status_code == 200
  assert dl.content == test_video_path.read_bytes()

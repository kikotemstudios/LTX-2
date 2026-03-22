"""Local filesystem storage for ltx://uploads/{id}."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field


class UploadTicket(BaseModel):
  upload_url: str
  storage_uri: str
  expires_at: str = Field(description="ISO8601 UTC")
  required_headers: dict[str, str] = Field(default_factory=dict)


class StorageService:
  def __init__(self, *, root: Path, public_base_url: str) -> None:
    self._root = root
    self._uploads = root / "uploads"
    self._uploads.mkdir(parents=True, exist_ok=True)
    self._public_base_url = public_base_url.rstrip("/")

  def create_upload_ticket(self) -> UploadTicket:
    uid = str(uuid.uuid4())
    upload_url = f"{self._public_base_url}/v1/storage/{uid}"
    storage_uri = f"ltx://uploads/{uid}"
    expires_at = (datetime.now(tz=UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    return UploadTicket(
      upload_url=upload_url,
      storage_uri=storage_uri,
      expires_at=expires_at,
      required_headers={},
    )

  def path_for_storage_uri(self, storage_uri: str) -> Path:
    if not storage_uri.startswith("ltx://uploads/"):
      msg = f"Invalid storage URI: {storage_uri}"
      raise ValueError(msg)
    uid = storage_uri.removeprefix("ltx://uploads/")
    if not uid or "/" in uid or ".." in uid:
      msg = "Invalid upload id"
      raise ValueError(msg)
    return self._uploads / uid

  def path_for_upload_id(self, upload_id: str) -> Path:
    if not upload_id or ".." in upload_id or "/" in upload_id:
      msg = "Invalid upload id"
      raise ValueError(msg)
    return self._uploads / upload_id

  def write_upload(self, upload_id: str, data: bytes) -> Path:
    path = self.path_for_upload_id(upload_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path

"""Resolve image_uri / video_uri / audio_uri to local paths."""

from __future__ import annotations

import base64
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from ltx_api.services.storage import StorageService


def _write_temp_bytes(data: bytes, suffix: str) -> Path:
  fd, name = tempfile.mkstemp(suffix=suffix)
  try:
    with os.fdopen(fd, "wb") as f:
      f.write(data)
  except Exception:
    os.close(fd)
    raise
  return Path(name)


def _decode_data_uri(uri: str) -> Path:
  m = re.match(r"^data:([^;,]+)?;base64,(.+)$", uri, re.DOTALL)
  if not m:
    msg = "Invalid data URI"
    raise ValueError(msg)
  raw = base64.b64decode(m.group(2).strip())
  ct = m.group(1) or ""
  suffix = ".bin"
  if "png" in ct:
    suffix = ".png"
  elif "jpeg" in ct or "jpg" in ct:
    suffix = ".jpg"
  elif "webp" in ct:
    suffix = ".webp"
  elif "wav" in ct:
    suffix = ".wav"
  elif "mpeg" in ct or "mp3" in ct:
    suffix = ".mp3"
  elif "mp4" in ct:
    suffix = ".mp4"
  return _write_temp_bytes(raw, suffix)


async def _download_url(url: str, *, client: httpx.AsyncClient | None) -> Path:
  use_client = client or httpx.AsyncClient(timeout=30.0)
  close = client is None
  try:
    r = await use_client.get(url, follow_redirects=False)
    r.raise_for_status()
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name or "download.bin"
    suffix = Path(name).suffix or ".bin"
    return _write_temp_bytes(r.content, suffix)
  finally:
    if close:
      await use_client.aclose()


async def resolve_uri_to_path(
  uri: str,
  *,
  storage: StorageService,
  httpx_client: httpx.AsyncClient | None = None,
) -> Path:
  if uri.startswith("ltx://uploads/"):
    return storage.path_for_storage_uri(uri)
  if uri.startswith("data:"):
    return _decode_data_uri(uri)
  if uri.startswith("https://") or uri.startswith("http://"):
    return await _download_url(uri, client=httpx_client)
  msg = f"Unsupported URI scheme: {uri[:48]}"
  raise ValueError(msg)

"""Commercial-style error JSON."""

from __future__ import annotations

from typing import Any


def error_payload(*, error_type: str, message: str) -> dict[str, Any]:
  return {"type": "error", "error": {"type": error_type, "message": message}}

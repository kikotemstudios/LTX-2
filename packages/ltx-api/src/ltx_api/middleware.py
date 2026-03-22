"""HTTP middleware."""

from __future__ import annotations

import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ltx_api.errors import error_payload


def _is_commercial_error_body(raw: bytes) -> bool:
  """True if body matches { type: 'error', error: { ... } } from error_payload / HTTPException."""
  if not raw.strip():
    return False
  try:
    data = json.loads(raw.decode("utf-8"))
  except (json.JSONDecodeError, UnicodeDecodeError):
    return False
  return isinstance(data, dict) and data.get("type") == "error" and isinstance(data.get("error"), dict)


class Normalize404Middleware(BaseHTTPMiddleware):
  """Replace default Starlette 404 with commercial error shape; keep handler 404s that already use it."""

  async def dispatch(self, request: Request, call_next) -> Response:
    response = await call_next(request)
    if response.status_code != 404:
      return response

    body = b""
    async for chunk in response.body_iterator:
      body += chunk

    if _is_commercial_error_body(body):
      return Response(
        content=body,
        status_code=404,
        media_type=response.media_type or "application/json",
      )

    return JSONResponse(
      status_code=404,
      content=error_payload(error_type="not_found", message="Not Found"),
    )

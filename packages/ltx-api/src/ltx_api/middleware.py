"""HTTP middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ltx_api.errors import error_payload


class Normalize404Middleware(BaseHTTPMiddleware):
  """Replace default Starlette 404 JSON with commercial error shape."""

  async def dispatch(self, request: Request, call_next) -> Response:
    response = await call_next(request)
    if response.status_code != 404:
      return response
    return JSONResponse(
      status_code=404,
      content=error_payload(error_type="not_found", message="Not Found"),
    )

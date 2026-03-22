"""Exception handlers for commercial-style errors."""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ltx_api.errors import error_payload


def format_validation_message(exc: RequestValidationError) -> str:
  parts: list[str] = []
  for err in exc.errors():
    loc = ".".join(str(x) for x in err.get("loc", ()) if x != "body")
    msg = err.get("msg", "")
    parts.append(f"{loc}: {msg}" if loc else msg)
  return "; ".join(parts) if parts else "Invalid request"


async def request_validation_exception_handler(
  _request: Request,
  exc: RequestValidationError,
) -> JSONResponse:
  return JSONResponse(
    status_code=422,
    content=error_payload(
      error_type="validation_error",
      message=format_validation_message(exc),
    ),
  )

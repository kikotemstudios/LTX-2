"""Bearer token verification."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ltx_api.config import Settings
from ltx_api.errors import error_payload

security = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
  return request.app.state.settings


async def require_bearer_if_configured(
  request: Request,
  credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
  settings: Settings = request.app.state.settings
  if not settings.auth_token:
    return
  if credentials is None or credentials.scheme.lower() != "bearer":
    raise HTTPException(
      status_code=401,
      detail=error_payload(error_type="authentication_error", message="Missing or invalid Authorization header"),
    )
  if credentials.credentials != settings.auth_token:
    raise HTTPException(
      status_code=401,
      detail=error_payload(error_type="authentication_error", message="Invalid API key"),
    )

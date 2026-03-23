"""FastAPI application factory."""

from __future__ import annotations

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ltx_api.auth import require_bearer_if_configured
from ltx_api.config import Settings
from ltx_api.errors import error_payload
from ltx_api.exceptions import request_validation_exception_handler
from ltx_api.jobs.manager import JobManager
from ltx_api.middleware import Normalize404Middleware
from ltx_api.routes.generation import router as generation_router
from ltx_api.routes.jobs import router as jobs_router
from ltx_api.routes.upload import router as upload_router
from ltx_api.services.mock_inference import MockInferenceBackend
from ltx_api.services.storage import StorageService
from ltx_api.services.vastai_client import VastAPIError


def create_app(*, settings: Settings | None = None) -> FastAPI:
  app_settings = settings or Settings()
  app = FastAPI(title="LTX API", version="0.1.0")
  app.add_middleware(Normalize404Middleware)

  app.state.settings = app_settings
  app.state.storage = StorageService(root=app_settings.storage_dir, public_base_url=app_settings.public_base_url)
  work_dir = app_settings.storage_dir / "work"
  work_dir.mkdir(parents=True, exist_ok=True)
  if app_settings.inference_backend == "mock":
    app.state.inference = MockInferenceBackend(work_dir=work_dir)
  elif app_settings.inference_backend == "real":
    from ltx_api.services.real_inference import RealInferenceBackend  # noqa: PLC0415

    app.state.inference = RealInferenceBackend(settings=app_settings, work_dir=work_dir)
  elif app_settings.inference_backend == "vastai":
    from ltx_api.services.vastai_inference import VastaiInferenceBackend  # noqa: PLC0415

    app.state.inference = VastaiInferenceBackend(settings=app_settings, work_dir=work_dir)
  else:
    msg = f"Unknown inference backend: {app_settings.inference_backend}"
    raise RuntimeError(msg)
  app.state.job_manager = JobManager(app.state.inference)

  app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

  @app.exception_handler(VastAPIError)
  async def vast_api_error_handler(_request: Request, exc: VastAPIError) -> JSONResponse:
    msg = str(exc)
    if len(msg) > 800:
      msg = msg[:797] + "..."
    return JSONResponse(
      status_code=502,
      content=error_payload(
        error_type="gpu_provider_error",
        message=msg,
      ),
    )

  @app.exception_handler(HTTPException)
  async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and detail.get("type") == "error":
      return JSONResponse(status_code=exc.status_code, content=detail)
    if exc.status_code == 404:
      message = str(detail) if detail else "Not Found"
      return JSONResponse(
        status_code=404,
        content=error_payload(error_type="not_found", message=message),
      )
    return JSONResponse(
      status_code=exc.status_code,
      content=error_payload(error_type="internal_error", message=str(detail)),
    )

  app.include_router(upload_router)
  app.include_router(generation_router)
  app.include_router(jobs_router)

  @app.get("/health")
  async def health() -> dict[str, str]:
    return {"status": "ok"}

  @app.get("/v1/_auth_probe", dependencies=[Depends(require_bearer_if_configured)])
  async def auth_probe() -> dict[str, bool]:
    return {"ok": True}

  return app


def run() -> None:
  settings = Settings()
  app = create_app(settings=settings)
  uvicorn.run(app, host=settings.host, port=settings.port)


def create_app_instance() -> FastAPI:
  return create_app(settings=Settings())

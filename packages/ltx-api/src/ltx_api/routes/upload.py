"""Upload and storage PUT routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from ltx_api.auth import require_bearer_if_configured
from ltx_api.config import Settings
from ltx_api.errors import error_payload
from ltx_api.services.storage import StorageService

router = APIRouter(prefix="/v1", dependencies=[Depends(require_bearer_if_configured)])


def get_storage(request: Request) -> StorageService:
  return request.app.state.storage


@router.post("/upload")
async def create_upload(storage: StorageService = Depends(get_storage)) -> dict[str, object]:
  ticket = storage.create_upload_ticket()
  return ticket.model_dump()


@router.put("/storage/{upload_id}")
async def put_storage(
  upload_id: str,
  request: Request,
  storage: StorageService = Depends(get_storage),
) -> Response:
  body = await request.body()
  try:
    storage.write_upload(upload_id, body)
  except ValueError as e:
    raise HTTPException(
      status_code=400,
      detail=error_payload(error_type="invalid_request_error", message=str(e)),
    ) from e
  return Response(status_code=204)

"""Async job endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from ltx_api.auth import require_bearer_if_configured
from ltx_api.errors import error_payload
from ltx_api.models.text_to_video import TextToVideoRequest

router = APIRouter(prefix="/v1", dependencies=[Depends(require_bearer_if_configured)])


@router.post("/async/text-to-video")
async def async_text_to_video(
  req: TextToVideoRequest,
  request: Request,
  background_tasks: BackgroundTasks,
) -> JSONResponse:
  jm = request.app.state.job_manager
  job_id = jm.enqueue_text_to_video(req)
  background_tasks.add_task(jm.run_text_to_video_job, job_id, req)
  return JSONResponse(content={"job_id": job_id, "status": "pending"})


@router.get("/jobs/{job_id}")
async def job_status(job_id: str, request: Request) -> JSONResponse:
  jm = request.app.state.job_manager
  rec = jm.get(job_id)
  if rec is None:
    raise HTTPException(
      status_code=404,
      detail=error_payload(error_type="not_found", message="Unknown job"),
    )
  body: dict[str, object] = {
    "job_id": job_id,
    "status": rec.status,
    "created_at": rec.created_at,
  }
  if rec.error:
    body["error"] = rec.error
  return JSONResponse(content=body)


@router.get("/jobs/{job_id}/download")
async def job_download(job_id: str, request: Request) -> FileResponse:
  jm = request.app.state.job_manager
  rec = jm.get(job_id)
  if rec is None or rec.status != "completed" or rec.result_path is None:
    raise HTTPException(
      status_code=400,
      detail=error_payload(error_type="invalid_request_error", message="Job not ready"),
    )
  return FileResponse(rec.result_path, media_type="application/octet-stream", filename="video.mp4")

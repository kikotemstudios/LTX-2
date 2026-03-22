"""Video generation routes (sync)."""

from __future__ import annotations

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response

from ltx_api.auth import require_bearer_if_configured
from ltx_api.errors import error_payload
from ltx_api.models.audio_to_video import AudioToVideoRequest
from ltx_api.models.extend import ExtendVideoRequest
from ltx_api.models.image_to_video import ImageToVideoRequest
from ltx_api.models.prompt_embedding import PromptEmbeddingRequest
from ltx_api.models.retake import RetakeRequest
from ltx_api.models.text_to_video import TextToVideoRequest
from ltx_api.services.media_uri import resolve_uri_to_path

router = APIRouter(prefix="/v1", dependencies=[Depends(require_bearer_if_configured)])


def _bad_request(message: str) -> HTTPException:
  return HTTPException(
    status_code=400,
    detail=error_payload(error_type="invalid_request_error", message=message),
  )


async def _resolve(storage, uri: str):
  try:
    async with httpx.AsyncClient(timeout=30.0) as client:
      return await resolve_uri_to_path(uri, storage=storage, httpx_client=client)
  except ValueError as e:
    raise _bad_request(str(e)) from e
  except httpx.HTTPError as e:
    raise _bad_request(f"Failed to fetch URL: {e}") from e


@router.post("/text-to-video")
async def text_to_video(req: TextToVideoRequest, request: Request) -> FileResponse:
  inf = request.app.state.inference
  out = inf.text_to_video(
    prompt=req.prompt,
    model=req.model,
    duration=req.duration,
    resolution=req.resolution,
    fps=req.fps,
    generate_audio=req.generate_audio,
    camera_motion=req.camera_motion,
    seed=0,
  )
  rid = str(uuid.uuid4())
  return FileResponse(
    out,
    media_type="application/octet-stream",
    filename="video.mp4",
    headers={"x-request-id": rid},
  )


@router.post("/image-to-video")
async def image_to_video(req: ImageToVideoRequest, request: Request) -> FileResponse:
  storage = request.app.state.storage
  image_path = await _resolve(storage, req.image_uri)
  last_frame_path = None
  if req.last_frame_uri:
    last_frame_path = await _resolve(storage, req.last_frame_uri)
  inf = request.app.state.inference
  out = inf.image_to_video(
    image_path=image_path,
    prompt=req.prompt,
    model=req.model,
    duration=req.duration,
    resolution=req.resolution,
    fps=req.fps,
    generate_audio=req.generate_audio,
    last_frame_path=last_frame_path,
    camera_motion=req.camera_motion,
    seed=0,
  )
  rid = str(uuid.uuid4())
  return FileResponse(
    out,
    media_type="application/octet-stream",
    filename="video.mp4",
    headers={"x-request-id": rid},
  )


@router.post("/audio-to-video")
async def audio_to_video(req: AudioToVideoRequest, request: Request) -> FileResponse:
  storage = request.app.state.storage
  audio_path = await _resolve(storage, req.audio_uri)
  image_path = None
  if req.image_uri:
    image_path = await _resolve(storage, req.image_uri)
  inf = request.app.state.inference
  out = inf.audio_to_video(
    audio_path=audio_path,
    image_path=image_path,
    prompt=req.prompt,
    resolution=req.resolution,
    guidance_scale=req.guidance_scale,
    model=req.model,
    seed=0,
  )
  rid = str(uuid.uuid4())
  return FileResponse(
    out,
    media_type="application/octet-stream",
    filename="video.mp4",
    headers={"x-request-id": rid},
  )


@router.post("/retake")
async def retake(req: RetakeRequest, request: Request) -> FileResponse:
  storage = request.app.state.storage
  video_path = await _resolve(storage, req.video_uri)
  inf = request.app.state.inference
  out = inf.retake(
    video_path=video_path,
    start_time=req.start_time,
    duration=req.duration,
    prompt=req.prompt,
    mode=req.mode,
    resolution=req.resolution,
    model=req.model,
    seed=0,
  )
  rid = str(uuid.uuid4())
  return FileResponse(
    out,
    media_type="application/octet-stream",
    filename="video.mp4",
    headers={"x-request-id": rid},
  )


@router.post("/extend")
async def extend(req: ExtendVideoRequest, request: Request) -> FileResponse:
  storage = request.app.state.storage
  video_path = await _resolve(storage, req.video_uri)
  inf = request.app.state.inference
  out = inf.extend(
    video_path=video_path,
    duration=req.duration,
    prompt=req.prompt,
    mode=req.mode,
    model=req.model,
    context=req.context,
    seed=0,
  )
  rid = str(uuid.uuid4())
  return FileResponse(
    out,
    media_type="application/octet-stream",
    filename="video.mp4",
    headers={"x-request-id": rid},
  )


@router.post("/prompt-embedding")
async def prompt_embedding(req: PromptEmbeddingRequest, request: Request) -> Response:
  inf = request.app.state.inference
  data = inf.prompt_embedding(prompt=req.prompt)
  rid = str(uuid.uuid4())
  return Response(
    content=data,
    media_type="application/octet-stream",
    headers={"x-request-id": rid},
  )

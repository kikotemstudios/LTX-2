"""Minimal FastAPI worker: POST /infer, GET /health. Requires ltx-api[real] + CUDA."""

# ruff: noqa: PLC0415, B008, PLR0912, PLR0915, ANN401 — lazy imports / FastAPI File defaults / dispatcher size

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

logger = logging.getLogger(__name__)

_TASKS = frozenset({
  "text_to_video",
  "image_to_video",
  "audio_to_video",
  "retake",
  "extend",
  "prompt_embedding",
})


def create_app() -> FastAPI:
  from ltx_api.config import Settings
  from ltx_api.services.real_inference import RealInferenceBackend

  settings = Settings()
  work_dir = settings.storage_dir / "worker"
  work_dir.mkdir(parents=True, exist_ok=True)
  backend = RealInferenceBackend(settings=settings, work_dir=work_dir)

  _pre = os.environ.get("LTX_WORKER_PREWARM", "").strip().lower()
  if _pre in ("1", "true", "yes", "on"):
    def _warm() -> None:
      try:
        backend.prewarm_pipeline()
        logger.info("LTX_WORKER_PREWARM: pipeline loaded")
      except Exception:
        logger.exception("LTX_WORKER_PREWARM: failed")

    threading.Thread(target=_warm, name="ltx-worker-prewarm", daemon=True).start()

  app = FastAPI(title="LTX GPU Worker", version="0.1.0")

  @app.get("/health")
  def health() -> dict[str, str]:
    return {"status": "ok"}

  @app.get("/ready")
  def ready() -> dict[str, str | bool]:
    return backend.readiness()

  @app.post("/infer")
  async def infer(
    task: Annotated[str, Form()],
    meta: Annotated[str, Form(description="JSON object with task-specific fields")],
    image: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
    video: UploadFile | None = File(None),
  ) -> Response:
    if task not in _TASKS:
      raise HTTPException(status_code=400, detail=f"unknown task {task}")
    try:
      fields: dict[str, Any] = json.loads(meta)
    except json.JSONDecodeError as e:
      raise HTTPException(status_code=400, detail=f"invalid meta json: {e}") from e

    try:
      return await _dispatch_infer(backend, work_dir, task, fields, image, audio, video)
    except NotImplementedError as e:
      raise HTTPException(status_code=501, detail=str(e) or "not implemented") from e

  return app


async def _dispatch_infer(
  backend: Any,
  work_dir: Any,
  task: str,
  fields: dict[str, Any],
  image: UploadFile | None,
  audio: UploadFile | None,
  video: UploadFile | None,
) -> Response:
  if task == "text_to_video":
    out = backend.text_to_video(
      prompt=str(fields["prompt"]),
      model=str(fields["model"]),
      duration=int(fields["duration"]),
      resolution=str(fields["resolution"]),
      fps=int(fields["fps"]),
      generate_audio=bool(fields.get("generate_audio", False)),
      camera_motion=fields.get("camera_motion"),
      seed=int(fields.get("seed", 0)),
    )
    data = out.read_bytes()
    return Response(content=data, media_type="application/octet-stream")

  if task == "image_to_video":
    if image is None:
      raise HTTPException(status_code=400, detail="image file required")
    img_path = work_dir / f"in_{os.urandom(4).hex()}.bin"
    img_path.write_bytes(await image.read())
    try:
      out = backend.image_to_video(
        image_path=img_path,
        prompt=str(fields["prompt"]),
        model=str(fields["model"]),
        duration=int(fields["duration"]),
        resolution=str(fields["resolution"]),
        fps=int(fields["fps"]),
        generate_audio=bool(fields.get("generate_audio", False)),
        last_frame_path=None,
        camera_motion=fields.get("camera_motion"),
        seed=int(fields.get("seed", 0)),
      )
      data = out.read_bytes()
    finally:
      img_path.unlink(missing_ok=True)
    return Response(content=data, media_type="application/octet-stream")

  if task == "audio_to_video":
    if audio is None:
      raise HTTPException(status_code=400, detail="audio file required")
    audio_path = work_dir / f"in_{os.urandom(4).hex()}.bin"
    audio_path.write_bytes(await audio.read())
    image_path: Path | None = None
    try:
      if image is not None:
        ip = work_dir / f"img_{os.urandom(4).hex()}.bin"
        ip.write_bytes(await image.read())
        image_path = ip
      out = backend.audio_to_video(
        audio_path=audio_path,
        image_path=image_path,
        prompt=fields.get("prompt"),
        resolution=fields.get("resolution"),
        guidance_scale=fields.get("guidance_scale"),
        model=str(fields["model"]),
        seed=int(fields.get("seed", 0)),
      )
      data = out.read_bytes()
    finally:
      audio_path.unlink(missing_ok=True)
      if image_path is not None:
        image_path.unlink(missing_ok=True)
    return Response(content=data, media_type="application/octet-stream")

  if task == "retake":
    if video is None:
      raise HTTPException(status_code=400, detail="video file required")
    video_path = work_dir / f"in_{os.urandom(4).hex()}.mp4"
    video_path.write_bytes(await video.read())
    try:
      out = backend.retake(
        video_path=video_path,
        start_time=float(fields["start_time"]),
        duration=float(fields["duration"]),
        prompt=fields.get("prompt"),
        mode=str(fields["mode"]),
        resolution=fields.get("resolution"),
        model=str(fields["model"]),
        seed=int(fields.get("seed", 0)),
      )
      data = out.read_bytes()
    finally:
      video_path.unlink(missing_ok=True)
    return Response(content=data, media_type="application/octet-stream")

  if task == "extend":
    if video is None:
      raise HTTPException(status_code=400, detail="video file required")
    video_path = work_dir / f"in_{os.urandom(4).hex()}.mp4"
    video_path.write_bytes(await video.read())
    try:
      out = backend.extend(
        video_path=video_path,
        duration=float(fields["duration"]),
        prompt=fields.get("prompt"),
        mode=str(fields["mode"]),
        model=str(fields["model"]),
        context=fields.get("context"),
        seed=int(fields.get("seed", 0)),
      )
      data = out.read_bytes()
    finally:
      video_path.unlink(missing_ok=True)
    return Response(content=data, media_type="application/octet-stream")

  if task == "prompt_embedding":
    blob = backend.prompt_embedding(prompt=str(fields["prompt"]))
    return Response(content=blob, media_type="application/octet-stream")

  raise HTTPException(status_code=400, detail=f"unknown task {task}")


def run() -> None:
  host = os.environ.get("LTX_WORKER_HOST", "0.0.0.0")
  port = int(os.environ.get("LTX_WORKER_PORT", "8765"))
  logging.basicConfig(level=logging.INFO)
  uvicorn.run(
    "ltx_api.worker.server:create_app",
    factory=True,
    host=host,
    port=port,
    log_level="info",
  )

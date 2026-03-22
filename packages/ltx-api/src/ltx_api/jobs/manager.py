"""In-memory async job queue."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ltx_api.models.text_to_video import TextToVideoRequest
from ltx_api.services.inference import InferenceBackend


@dataclass
class JobRecord:
  status: str
  created_at: str
  result_path: Path | None = None
  error: str | None = None


class JobManager:
  def __init__(self, inference: InferenceBackend) -> None:
    self._inference = inference
    self._jobs: dict[str, JobRecord] = {}
    self._lock = threading.Lock()

  def get(self, job_id: str) -> JobRecord | None:
    with self._lock:
      return self._jobs.get(job_id)

  def enqueue_text_to_video(self, req: TextToVideoRequest) -> str:
    job_id = str(uuid.uuid4())
    created = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    with self._lock:
      self._jobs[job_id] = JobRecord(status="pending", created_at=created)
    return job_id

  def run_text_to_video_job(self, job_id: str, req: TextToVideoRequest) -> None:
    try:
      path = self._inference.text_to_video(
        prompt=req.prompt,
        model=req.model,
        duration=req.duration,
        resolution=req.resolution,
        fps=req.fps,
        generate_audio=req.generate_audio,
        camera_motion=req.camera_motion,
        seed=0,
      )
      with self._lock:
        rec = self._jobs.get(job_id)
        if rec:
          rec.status = "completed"
          rec.result_path = path
    except Exception as e:
      with self._lock:
        rec = self._jobs.get(job_id)
        if rec:
          rec.status = "failed"
          rec.error = str(e)

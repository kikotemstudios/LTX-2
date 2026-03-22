"""Mock inference: returns canned fixture media."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from ltx_api.services.inference import InferenceBackend


def _default_fixture_video() -> Path:
  # packages/ltx-api/src/ltx_api/services/mock_inference.py -> parents[3] = package root
  root = Path(__file__).resolve().parents[3]
  return root / "tests" / "fixtures" / "test_video.mp4"


class MockInferenceBackend:
  def __init__(self, *, fixture_video: Path | None = None, work_dir: Path) -> None:
    self._fixture_video = fixture_video or _default_fixture_video()
    self._work_dir = work_dir
    self._work_dir.mkdir(parents=True, exist_ok=True)

  def _copy_fixture(self) -> Path:
    out = self._work_dir / f"mock_{uuid.uuid4().hex}.mp4"
    shutil.copyfile(self._fixture_video, out)
    return out

  def text_to_video(
    self,
    *,
    prompt: str,
    model: str,
    duration: int,
    resolution: str,
    fps: int,
    generate_audio: bool,
    camera_motion: str | None,
    seed: int,
  ) -> Path:
    _ = (prompt, model, duration, resolution, fps, generate_audio, camera_motion, seed)
    return self._copy_fixture()

  def image_to_video(
    self,
    *,
    image_path: Path,
    prompt: str,
    model: str,
    duration: int,
    resolution: str,
    fps: int,
    generate_audio: bool,
    last_frame_path: Path | None,
    camera_motion: str | None,
    seed: int,
  ) -> Path:
    _ = (
      image_path,
      prompt,
      model,
      duration,
      resolution,
      fps,
      generate_audio,
      last_frame_path,
      camera_motion,
      seed,
    )
    return self._copy_fixture()

  def audio_to_video(
    self,
    *,
    audio_path: Path,
    image_path: Path | None,
    prompt: str | None,
    resolution: str | None,
    guidance_scale: float | None,
    model: str,
    seed: int,
  ) -> Path:
    _ = (audio_path, image_path, prompt, resolution, guidance_scale, model, seed)
    return self._copy_fixture()

  def retake(
    self,
    *,
    video_path: Path,
    start_time: float,
    duration: float,
    prompt: str | None,
    mode: str,
    resolution: str | None,
    model: str,
    seed: int,
  ) -> Path:
    _ = (video_path, start_time, duration, prompt, mode, resolution, model, seed)
    return self._copy_fixture()

  def extend(
    self,
    *,
    video_path: Path,
    duration: float,
    prompt: str | None,
    mode: str,
    model: str,
    context: float | None,
    seed: int,
  ) -> Path:
    _ = (video_path, duration, prompt, mode, model, context, seed)
    return self._copy_fixture()

  def prompt_embedding(self, *, prompt: str) -> bytes:
    return f"mock-embedding:{prompt}".encode()

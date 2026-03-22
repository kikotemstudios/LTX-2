"""Inference backend protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class InferenceBackend(Protocol):
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
    """Write MP4 to disk and return path."""

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
  ) -> Path: ...

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
  ) -> Path: ...

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
  ) -> Path: ...

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
  ) -> Path: ...

  def prompt_embedding(self, *, prompt: str) -> bytes: ...

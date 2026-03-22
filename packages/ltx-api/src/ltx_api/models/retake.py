"""Retake (edit) request."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RetakeRequest(BaseModel):
  video_uri: str
  start_time: float
  duration: float
  prompt: str | None = None
  mode: Literal["replace_audio", "replace_video", "replace_audio_and_video"] = "replace_audio_and_video"
  resolution: Literal["1920x1080", "1080x1920"] | None = None
  model: Literal["ltx-2-pro", "ltx-2-3-pro"] = "ltx-2-3-pro"

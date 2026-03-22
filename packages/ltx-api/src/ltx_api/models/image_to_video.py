"""Image-to-video request."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ImageToVideoRequest(BaseModel):
  image_uri: str
  prompt: str
  model: Literal["ltx-2-fast", "ltx-2-pro", "ltx-2-3-fast", "ltx-2-3-pro"]
  duration: int
  resolution: str
  fps: int = Field(default=24)
  generate_audio: bool = Field(default=True)
  last_frame_uri: str | None = None
  camera_motion: (
    Literal[
      "dolly_in",
      "dolly_out",
      "dolly_left",
      "dolly_right",
      "jib_up",
      "jib_down",
      "static",
      "focus_shift",
    ]
    | None
  ) = None

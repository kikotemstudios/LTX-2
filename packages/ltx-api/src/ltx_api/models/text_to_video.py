"""Text-to-video request (commercial API)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TextToVideoRequest(BaseModel):
  prompt: str = Field(..., description="Text prompt")
  model: Literal["ltx-2-fast", "ltx-2-pro", "ltx-2-3-fast", "ltx-2-3-pro"] = Field(...)
  duration: int = Field(..., description="Duration in seconds")
  resolution: str = Field(...)
  fps: int = Field(default=24)
  generate_audio: bool = Field(default=True)
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
  ) = Field(default=None)

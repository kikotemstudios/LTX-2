"""Audio-to-video request."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AudioToVideoRequest(BaseModel):
  audio_uri: str
  image_uri: str | None = None
  prompt: str | None = None
  resolution: Literal["1920x1080", "1080x1920"] | None = None
  guidance_scale: float | None = None
  model: Literal["ltx-2-pro", "ltx-2-3-pro"] = "ltx-2-3-pro"

  @model_validator(mode="after")
  def prompt_or_image(self) -> AudioToVideoRequest:
    if not self.prompt and not self.image_uri:
      msg = "Either prompt or image_uri must be provided"
      raise ValueError(msg)
    return self

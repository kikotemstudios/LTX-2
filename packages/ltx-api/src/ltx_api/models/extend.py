"""Extend video request."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExtendVideoRequest(BaseModel):
  video_uri: str
  duration: float
  prompt: str | None = None
  mode: Literal["start", "end"] = "end"
  model: Literal["ltx-2-pro", "ltx-2-3-pro"] = "ltx-2-3-pro"
  context: float | None = None

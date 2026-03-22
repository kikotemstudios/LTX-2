"""Prompt embedding request."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PromptEmbeddingRequest(BaseModel):
  prompt: str = Field(..., min_length=1)

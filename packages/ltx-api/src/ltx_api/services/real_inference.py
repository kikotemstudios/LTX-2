"""Real GPU inference via ltx-pipelines (distilled / fast path)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from ltx_api.config import Settings
from ltx_core.model.video_vae import TilingConfig, get_video_chunks_number
from ltx_pipelines.distilled import DistilledPipeline
from ltx_pipelines.ti2vid_one_stage import TI2VidOneStagePipeline
from ltx_pipelines.utils.constants import DEFAULT_NEGATIVE_PROMPT, detect_params
from ltx_pipelines.utils.media_io import encode_video

logger = logging.getLogger(__name__)

_FAST_MODELS = frozenset({"ltx-2-fast", "ltx-2-3-fast"})
_PRO_MODELS = frozenset({"ltx-2-pro", "ltx-2-3-pro"})


def _parse_resolution(resolution: str) -> tuple[int, int]:
  if "x" in resolution.lower():
    w, _, h = resolution.lower().partition("x")
    return int(w), int(h)
  msg = f"Unsupported resolution: {resolution}"
  raise ValueError(msg)


class RealInferenceBackend:
  """Runs DistilledPipeline for fast models; TI2VidOneStagePipeline for pro models."""

  def __init__(self, settings: Settings, work_dir: Path) -> None:
    self._settings = settings
    self._work_dir = work_dir
    self._work_dir.mkdir(parents=True, exist_ok=True)
    mode = self._worker_mode()
    if mode not in ("distilled", "full", "both"):
      msg = (
        "LTX_API_WORKER_PIPELINE must be 'distilled', 'full', or 'both'; "
        f"got {settings.worker_pipeline!r}"
      )
      raise RuntimeError(msg)
    if not settings.gemma_root:
      msg = "Real backend requires LTX_API_GEMMA_ROOT"
      raise RuntimeError(msg)
    if mode == "distilled":
      if not settings.checkpoint_path or not settings.spatial_upsampler_path:
        msg = (
          "Distilled worker requires LTX_API_CHECKPOINT_PATH, LTX_API_SPATIAL_UPSAMPLER_PATH, "
          "and LTX_API_GEMMA_ROOT"
        )
        raise RuntimeError(msg)
    elif mode == "full":
      if not self._full_checkpoint_resolved():
        msg = (
          "Full worker requires LTX_API_GEMMA_ROOT and a dev checkpoint: "
          "LTX_API_FULL_CHECKPOINT_PATH or LTX_API_CHECKPOINT_PATH"
        )
        raise RuntimeError(msg)
    else:
      if (
        not settings.checkpoint_path
        or not settings.spatial_upsampler_path
        or not settings.full_checkpoint_path
        or not settings.gemma_root
      ):
        msg = (
          "'both' worker requires LTX_API_CHECKPOINT_PATH (distilled), "
          "LTX_API_FULL_CHECKPOINT_PATH (dev), LTX_API_SPATIAL_UPSAMPLER_PATH, "
          "and LTX_API_GEMMA_ROOT"
        )
        raise RuntimeError(msg)
    self._distilled_pipeline: DistilledPipeline | None = None
    self._full_pipeline: TI2VidOneStagePipeline | None = None

  def _worker_mode(self) -> str:
    return (self._settings.worker_pipeline or "distilled").strip().lower()

  def _full_checkpoint_resolved(self) -> str | None:
    if self._worker_mode() == "both":
      return self._settings.full_checkpoint_path
    return self._settings.full_checkpoint_path or self._settings.checkpoint_path

  def readiness(self) -> dict[str, Any]:
    """Expose pipeline load state for GET /ready on the GPU worker."""
    mode = self._worker_mode()
    if mode == "both":
      loaded = (
        self._distilled_pipeline is not None and self._full_pipeline is not None
      )
    elif mode == "full":
      loaded = self._full_pipeline is not None
    else:
      loaded = self._distilled_pipeline is not None
    return {
      "status": "ok",
      "ready": loaded,
      "detail": "pipeline loaded" if loaded else "lazy init until first inference",
    }

  def prewarm_pipeline(self) -> None:
    """Load pipeline at startup (optional; enables /ready before first request)."""
    mode = self._worker_mode()
    if mode == "both":
      self._get_distilled_pipeline()
      self._get_full_pipeline()
    elif mode == "full":
      self._get_full_pipeline()
    else:
      self._get_distilled_pipeline()

  def _get_distilled_pipeline(self) -> DistilledPipeline:
    if self._distilled_pipeline is None:
      self._distilled_pipeline = DistilledPipeline(
        distilled_checkpoint_path=self._settings.checkpoint_path or "",
        gemma_root=self._settings.gemma_root or "",
        spatial_upsampler_path=self._settings.spatial_upsampler_path or "",
        loras=(),
        quantization=None,
      )
    return self._distilled_pipeline

  def _get_full_pipeline(self) -> TI2VidOneStagePipeline:
    if self._full_pipeline is None:
      ckpt = self._full_checkpoint_resolved() or ""
      self._full_pipeline = TI2VidOneStagePipeline(
        checkpoint_path=ckpt,
        gemma_root=self._settings.gemma_root or "",
        loras=(),
        quantization=None,
      )
    return self._full_pipeline

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
    _ = (generate_audio, camera_motion)
    mode = self._worker_mode()

    if model in _PRO_MODELS:
      if mode == "distilled":
        msg = (
          f"Model {model} requires LTX_API_WORKER_PIPELINE=full or both "
          f"(got worker_pipeline={mode!r})"
        )
        raise NotImplementedError(msg)
      width, height = _parse_resolution(resolution)
      num_frames = max(1, int(duration * fps))
      out = self._work_dir / f"real_{uuid.uuid4().hex}.mp4"
      ckpt = self._full_checkpoint_resolved() or ""
      params = detect_params(ckpt)
      pipeline = self._get_full_pipeline()
      video_iter, audio = pipeline(
        prompt=prompt,
        negative_prompt=DEFAULT_NEGATIVE_PROMPT,
        seed=seed,
        height=height,
        width=width,
        num_frames=num_frames,
        frame_rate=float(fps),
        num_inference_steps=params.num_inference_steps,
        video_guider_params=params.video_guider_params,
        audio_guider_params=params.audio_guider_params,
        images=[],
        enhance_prompt=False,
      )
      tiling_config: TilingConfig = TilingConfig.default()
      video_chunks_number = get_video_chunks_number(num_frames, tiling_config)
      encode_video(
        video=video_iter,
        fps=float(fps),
        audio=audio,
        output_path=str(out),
        video_chunks_number=video_chunks_number,
      )
      return out

    if model in _FAST_MODELS:
      if mode == "full":
        msg = (
          f"Model {model} requires LTX_API_WORKER_PIPELINE=distilled or both "
          f"(got worker_pipeline={mode!r})"
        )
        raise NotImplementedError(msg)
      width, height = _parse_resolution(resolution)
      num_frames = max(1, int(duration * fps))
      out = self._work_dir / f"real_{uuid.uuid4().hex}.mp4"
      pipeline = self._get_distilled_pipeline()
      tiling_config: TilingConfig = TilingConfig.default()
      video_chunks_number = get_video_chunks_number(num_frames, tiling_config)
      video_iter, audio = pipeline(
        prompt=prompt,
        seed=seed,
        height=height,
        width=width,
        num_frames=num_frames,
        frame_rate=float(fps),
        images=[],
        tiling_config=tiling_config,
        enhance_prompt=False,
      )
      encode_video(
        video=video_iter,
        fps=float(fps),
        audio=audio,
        output_path=str(out),
        video_chunks_number=video_chunks_number,
      )
      return out

    msg = f"Real backend: unsupported model {model!r} (expected fast or pro id)"
    raise NotImplementedError(msg)

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
    raise NotImplementedError("Real image-to-video not wired yet")

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
    raise NotImplementedError("Real audio-to-video not wired yet")

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
    raise NotImplementedError("Real retake not wired yet")

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
    raise NotImplementedError("Real extend not wired yet")

  def prompt_embedding(self, *, prompt: str) -> bytes:
    _ = prompt
    raise NotImplementedError("Real prompt embedding not wired yet; use mock backend")

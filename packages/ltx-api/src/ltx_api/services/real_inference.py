"""Real GPU inference via ltx-pipelines (distilled / fast path)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from ltx_api.config import Settings
from ltx_core.model.video_vae import TilingConfig, get_video_chunks_number
from ltx_pipelines.distilled import DistilledPipeline
from ltx_pipelines.utils.media_io import encode_video

logger = logging.getLogger(__name__)

_FAST_MODELS = frozenset({"ltx-2-fast", "ltx-2-3-fast"})


def _parse_resolution(resolution: str) -> tuple[int, int]:
  if "x" in resolution.lower():
    w, _, h = resolution.lower().partition("x")
    return int(w), int(h)
  msg = f"Unsupported resolution: {resolution}"
  raise ValueError(msg)


class RealInferenceBackend:
  """Runs DistilledPipeline for fast models; other modes fall back to explicit errors or mock for dev."""

  def __init__(self, settings: Settings, work_dir: Path) -> None:
    self._settings = settings
    self._work_dir = work_dir
    self._work_dir.mkdir(parents=True, exist_ok=True)
    if not settings.checkpoint_path or not settings.gemma_root or not settings.spatial_upsampler_path:
      msg = (
        "Real backend requires LTX_API_CHECKPOINT_PATH, LTX_API_GEMMA_ROOT, "
        "LTX_API_SPATIAL_UPSAMPLER_PATH"
      )
      raise RuntimeError(msg)
    self._pipeline: DistilledPipeline | None = None

  def _get_pipeline(self) -> DistilledPipeline:
    if self._pipeline is None:
      self._pipeline = DistilledPipeline(
        distilled_checkpoint_path=self._settings.checkpoint_path or "",
        gemma_root=self._settings.gemma_root or "",
        spatial_upsampler_path=self._settings.spatial_upsampler_path or "",
        loras=(),
        quantization=None,
      )
    return self._pipeline

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
    if model not in _FAST_MODELS:
      msg = f"Real backend currently supports fast models only; got {model}"
      raise NotImplementedError(msg)
    width, height = _parse_resolution(resolution)
    num_frames = max(1, int(duration * fps))
    out = self._work_dir / f"real_{uuid.uuid4().hex}.mp4"
    pipeline = self._get_pipeline()
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

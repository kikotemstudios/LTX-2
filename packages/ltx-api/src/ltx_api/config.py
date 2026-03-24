"""Application settings (env: LTX_API_*)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(env_prefix="LTX_API_", env_file=".env", extra="ignore")

  host: str = Field(default="0.0.0.0", description="Bind address")
  port: int = Field(default=8080, description="Bind port")
  debug: bool = Field(default=False, description="Enable verbose debug logging across ltx-api and HTTP clients")
  auth_token: str = Field(default="", description="Bearer token; empty disables auth")
  inference_backend: str = Field(
    default="mock",
    description="mock, real, or vastai (API forwards to on-demand GPU worker)",
  )
  storage_dir: Path = Field(default=Path.home() / ".ltx-api" / "storage")
  public_base_url: str = Field(
    default="http://127.0.0.1:8080",
    description="Base URL advertised in upload_url (no trailing slash)",
  )
  max_concurrent_jobs: int = Field(default=1)
  job_ttl_seconds: int = Field(default=3600)
  checkpoint_path: str | None = Field(
    default=None,
    description="Distilled checkpoint (fast / ltx-2-3-fast); also sole checkpoint when worker_pipeline=full (dev .safetensors)",
  )
  full_checkpoint_path: str | None = Field(
    default=None,
    description="Non-distilled dev checkpoint for pro / ltx-2-3-pro; required when worker_pipeline=both",
  )
  gemma_root: str | None = Field(default=None)
  spatial_upsampler_path: str | None = Field(default=None)
  worker_pipeline: str = Field(
    default="distilled",
    description=(
      "distilled = DistilledPipeline only (fast); full = TI2VidOneStagePipeline only (pro); "
      "both = load both checkpoints and pick pipeline by model id (Desktop fast vs pro)"
    ),
  )

  # --- Vast.ai / GPU worker (inference_backend=vastai) ---
  # If set, skip Vast provisioning and forward inference here (manual or fixed worker).
  vast_worker_base_url: str = Field(default="", description="e.g. http://1.2.3.4:8765 — empty = auto-provision")
  vast_api_base: str = Field(default="https://console.vast.ai", description="Vast REST API origin")
  vast_api_key: str = Field(default="", description="Bearer for Vast API (required for auto-provision)")
  vast_ssh_key_path: Path = Field(
    default=Path.home() / ".ssh" / "id_ed25519",
    description="For worker SSH setup on GPU host; not used by ltx-api HTTP forwarding",
  )
  vast_gpu_ram_mb: int = Field(default=80000, description="Min GPU VRAM for bundle search")
  vast_gpu_name: str = Field(default="A100_SXM4", description="Primary GPU filter for bundle search")
  vast_disk_gb: int = Field(default=200, description="Allocated disk when creating instance")
  vast_disk_search_gb: int = Field(default=100, description="Min host disk in bundle search")
  vast_template_send_disk: bool = Field(
    default=False,
    description="If true, include disk in PUT body when using template_hash_id; false avoids invalid_args when disk exceeds offer max (template defaults apply)",
  )
  vast_debug_log_payload: bool = Field(
    default=False,
    description="If true, log full Vast create-instance request payloads and responses for debugging",
  )
  vast_template_hash_id: str = Field(
    default="aa3bf4890de6b073eec0a2b89f1a82f2",
    description="Vast template hash (PyTorch image); empty uses vast_image instead",
  )
  vast_image: str = Field(
    default="vastai/base-image:@vastai-automatic-tag",
    description="Docker image when vast_template_hash_id is empty",
  )
  vast_label: str = Field(default="ltx-api-gpu-worker", description="Instance label for lookup")
  vast_geolocation_preferred: str = Field(
    default="US",
    description="Comma-separated country codes tried first in bundle search",
  )
  vast_worker_internal_port: int = Field(
    default=8765,
    description="Container port for GPU worker; mapped to public HostPort on Vast",
  )
  vast_idle_timeout_seconds: int = Field(
    default=900,
    description="Destroy Vast instance after this many seconds without inference",
  )
  vast_poll_interval_seconds: float = Field(default=15.0, description="Poll interval when waiting for instance/worker")
  vast_http_timeout_seconds: float = Field(default=1200.0, description="HTTP timeout for worker inference calls")
  vast_worker_poll_ready: bool = Field(
    default=True,
    description="After GET /health succeeds, poll GET /ready on the worker and log readiness changes in ltx-api logs",
  )
  vast_worker_wait_for_pipeline_ready: bool = Field(
    default=False,
    description="If True, block until /ready reports ready=true or vast_worker_ready_timeout_seconds (use with worker prewarm)",
  )
  vast_worker_ready_timeout_seconds: float = Field(
    default=300.0,
    description="Max seconds to poll /ready after /health (when vast_worker_poll_ready)",
  )

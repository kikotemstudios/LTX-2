"""Forward inference to an HTTP GPU worker; optionally provision/destroy Vast.ai instances."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from ltx_api.config import Settings
from ltx_api.services import vastai_client as vast

logger = logging.getLogger(__name__)

_RELAXED_GPUS = [
  "A100_SXM4",
  "A100-SXM4",
  "A100 SXM4",
  "A100_80GB_PCIe",
  "H100",
  "H100_80GB_HBM3",
  "H200",
  "H200_NVL",
]


class VastaiInferenceBackend:
  def __init__(self, settings: Settings, work_dir: Path) -> None:
    self._settings = settings
    self._work_dir = work_dir
    self._work_dir.mkdir(parents=True, exist_ok=True)
    self._lock = threading.RLock()
    self._provision_lock = threading.Lock()
    self._worker_base: str | None = None
    self._instance_id: int | None = None
    self._managed_instance: bool = False
    self._last_activity: float = time.monotonic()
    self._stop_watcher = threading.Event()
    self._watcher = threading.Thread(target=self._idle_loop, name="vastai-idle", daemon=True)
    self._watcher.start()
    base = settings.vast_worker_base_url.strip()
    if base:
      self._worker_base = base.rstrip("/")
      self._managed_instance = False
      logger.info("Vastai backend using fixed worker URL %s", self._worker_base)

  def _touch(self) -> None:
    self._last_activity = time.monotonic()

  def _idle_loop(self) -> None:
    interval = max(5.0, min(60.0, self._settings.vast_poll_interval_seconds))
    while not self._stop_watcher.wait(timeout=interval):
      with self._lock:
        if not self._managed_instance or self._instance_id is None:
          continue
        idle = time.monotonic() - self._last_activity
        if idle < self._settings.vast_idle_timeout_seconds:
          continue
        iid = self._instance_id
      logger.info("Vast idle timeout (%ss) — destroying instance %s", self._settings.vast_idle_timeout_seconds, iid)
      try:
        self._destroy_instance(iid)
      except Exception:
        logger.exception("Failed to destroy Vast instance %s", iid)

  def _destroy_instance(self, instance_id: int) -> None:
    with httpx.Client(timeout=60.0) as client:
      vast.destroy_instance(
        client=client,
        api_base=self._settings.vast_api_base,
        api_key=self._settings.vast_api_key,
        instance_id=instance_id,
      )
    with self._lock:
      if self._instance_id == instance_id:
        self._instance_id = None
        self._worker_base = None
        self._managed_instance = False

  def _wait_worker_http(self, base: str) -> None:
    url = f"{base.rstrip('/')}/health"
    deadline = time.monotonic() + self._settings.vast_http_timeout_seconds
    pause = max(3.0, self._settings.vast_poll_interval_seconds)
    while time.monotonic() < deadline:
      try:
        with httpx.Client(timeout=10.0) as client:
          r = client.get(url)
          if r.status_code == 200:
            return
      except httpx.HTTPError:
        pass
      time.sleep(pause)
    msg = f"GPU worker did not become healthy at {url}"
    raise RuntimeError(msg)

  def _poll_instance_ready(
    self,
    client: httpx.Client,
    contract_id: int,
  ) -> vast.VastInstanceInfo:
    deadline = time.monotonic() + self._settings.vast_http_timeout_seconds
    pause = max(3.0, self._settings.vast_poll_interval_seconds)
    internal = self._settings.vast_worker_internal_port
    while time.monotonic() < deadline:
      instances = vast.list_instances(
        client=client,
        api_base=self._settings.vast_api_base,
        api_key=self._settings.vast_api_key,
      )
      inst = vast.pick_running_instance(
        instances,
        contract_id=contract_id,
        label=self._settings.vast_label,
      )
      if inst is None:
        time.sleep(pause)
        continue
      iid = int(inst.get("id") or 0)
      detail = vast.get_instance_detail(
        client=client,
        api_base=self._settings.vast_api_base,
        api_key=self._settings.vast_api_key,
        instance_id=iid,
      )
      resolved = vast.resolve_worker_endpoint(inst, internal_port=internal, detail=detail)
      if resolved:
        public_ip, host_port = resolved
        return vast.VastInstanceInfo(instance_id=iid, public_ip=public_ip, worker_host_port=host_port)
      time.sleep(pause)
    msg = "Timed out waiting for Vast instance and worker port mapping"
    raise RuntimeError(msg)

  def _search_offer(self, client: httpx.Client, *, exclude_offer_ids: set[int] | None = None) -> int:
    try:
      return vast.search_cheapest_offer(
        client=client,
        api_base=self._settings.vast_api_base,
        api_key=self._settings.vast_api_key,
        gpu_ram_mb=self._settings.vast_gpu_ram_mb,
        gpu_name=self._settings.vast_gpu_name,
        disk_search_gb=self._settings.vast_disk_search_gb,
        geolocation_preferred=self._settings.vast_geolocation_preferred,
        exclude_offer_ids=exclude_offer_ids,
      )
    except vast.VastAPIError:
      logger.info("Primary Vast GPU search failed; trying relaxed GPU list")
    for g in _RELAXED_GPUS:
      try:
        return vast.search_cheapest_offer(
          client=client,
          api_base=self._settings.vast_api_base,
          api_key=self._settings.vast_api_key,
          gpu_ram_mb=self._settings.vast_gpu_ram_mb,
          gpu_name=g,
          disk_search_gb=self._settings.vast_disk_search_gb,
          geolocation_preferred=self._settings.vast_geolocation_preferred,
          exclude_offer_ids=exclude_offer_ids,
        )
      except vast.VastAPIError:
        continue
    raise vast.VastAPIError("No Vast offers found after relaxed GPU search")

  def _provision(self) -> str:
    """Provision a Vast instance; retries search+create on stale-offer / 400 from Vast."""
    max_create_attempts = 3
    with httpx.Client(timeout=60.0) as client:
      contract_id: int | None = None
      excluded_offer_ids: set[int] = set()
      for attempt in range(max_create_attempts):
        offer_id = self._search_offer(client, exclude_offer_ids=excluded_offer_ids)
        excluded_offer_ids.add(offer_id)
        try:
          template_hash = self._settings.vast_template_hash_id
          contract_id = vast.create_instance(
            client=client,
            api_base=self._settings.vast_api_base,
            api_key=self._settings.vast_api_key,
            offer_id=offer_id,
            disk_gb=self._settings.vast_disk_gb,
            label=self._settings.vast_label,
            template_hash_id=template_hash,
            image=self._settings.vast_image,
            template_send_disk=self._settings.vast_template_send_disk,
            debug_log_payload=self._settings.vast_debug_log_payload,
          )
          break
        except vast.VastAPIError as exc:
          # Billing failure is authoritative on this account — do not retry other offers or
          # template→image fallback (the image path uses the same credit).
          if vast.is_insufficient_credit_error(exc):
            logger.warning(
              "Vast create_instance failed (insufficient credit, offer_id=%s): %s",
              offer_id,
              exc,
            )
            raise exc
          # Some offers reject the template payload; fallback to raw image create.
          fallback_exc: vast.VastAPIError | None = None
          if template_hash.strip() and "invalid_args" in str(exc).lower():
            logger.warning(
              "Vast template create rejected for offer_id=%s; retrying same offer with image payload",
              offer_id,
            )
            try:
              contract_id = vast.create_instance(
                client=client,
                api_base=self._settings.vast_api_base,
                api_key=self._settings.vast_api_key,
                offer_id=offer_id,
                disk_gb=self._settings.vast_disk_gb,
                label=self._settings.vast_label,
                template_hash_id="",
                image=self._settings.vast_image,
                template_send_disk=self._settings.vast_template_send_disk,
                debug_log_payload=self._settings.vast_debug_log_payload,
              )
              break
            except vast.VastAPIError as img_exc:
              fallback_exc = img_exc
          reported = fallback_exc or exc
          logger.warning(
            "Vast create_instance failed (attempt %s/%s, offer_id=%s): %s",
            attempt + 1,
            max_create_attempts,
            offer_id,
            reported,
          )
          if vast.is_insufficient_credit_error(reported):
            raise reported
          if attempt + 1 < max_create_attempts:
            time.sleep(1.0 + float(attempt))
            continue
          raise reported
      if contract_id is None:
        raise RuntimeError("Vast provision failed without contract_id")
      info = self._poll_instance_ready(client, contract_id)
    base = f"http://{info.public_ip}:{info.worker_host_port}"
    logger.info("Vast worker endpoint %s (instance_id=%s)", base, info.instance_id)
    self._wait_worker_http(base)
    with self._lock:
      self._worker_base = base
      self._instance_id = info.instance_id
      self._managed_instance = True
    return base

  def _ensure_worker_base(self) -> str:
    with self._lock:
      if self._worker_base:
        return self._worker_base
    with self._provision_lock:
      with self._lock:
        if self._worker_base:
          return self._worker_base
      if self._settings.vast_worker_base_url.strip():
        base = self._settings.vast_worker_base_url.strip().rstrip("/")
        self._wait_worker_http(base)
        with self._lock:
          self._worker_base = base
          self._managed_instance = False
        return base
      if not self._settings.vast_api_key.strip():
        msg = "vastai backend requires LTX_API_VAST_WORKER_BASE_URL or LTX_API_VAST_API_KEY"
        raise RuntimeError(msg)
      return self._provision()

  def _post_infer(
    self,
    task: str,
    meta: dict[str, Any],
    files: dict[str, tuple[str, bytes, str]] | None = None,
  ) -> bytes:
    self._touch()
    base = self._ensure_worker_base()
    url = f"{base}/infer"
    data = {"task": task, "meta": json.dumps(meta)}
    timeout = self._settings.vast_http_timeout_seconds
    with httpx.Client(timeout=timeout) as client:
      r = client.post(url, data=data, files=files) if files else client.post(url, data=data)
    if r.status_code == 501:
      msg = r.text or "Worker returned not implemented"
      raise NotImplementedError(msg)
    r.raise_for_status()
    return r.content

  def _write_result(self, content: bytes) -> Path:
    out = self._work_dir / f"vast_{uuid.uuid4().hex}.mp4"
    out.write_bytes(content)
    return out

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
    meta = {
      "prompt": prompt,
      "model": model,
      "duration": duration,
      "resolution": resolution,
      "fps": fps,
      "generate_audio": generate_audio,
      "camera_motion": camera_motion,
      "seed": seed,
    }
    raw = self._post_infer("text_to_video", meta)
    return self._write_result(raw)

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
    _ = last_frame_path
    meta = {
      "prompt": prompt,
      "model": model,
      "duration": duration,
      "resolution": resolution,
      "fps": fps,
      "generate_audio": generate_audio,
      "camera_motion": camera_motion,
      "seed": seed,
    }
    img_bytes = image_path.read_bytes()
    files = {"image": ("image.bin", img_bytes, "application/octet-stream")}
    raw = self._post_infer("image_to_video", meta, files=files)
    return self._write_result(raw)

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
    meta = {
      "prompt": prompt,
      "resolution": resolution,
      "guidance_scale": guidance_scale,
      "model": model,
      "seed": seed,
    }
    audio_bytes = audio_path.read_bytes()
    files: dict[str, tuple[str, bytes, str]] = {
      "audio": ("audio.bin", audio_bytes, "application/octet-stream"),
    }
    if image_path is not None:
      files["image"] = ("image.bin", image_path.read_bytes(), "application/octet-stream")
    raw = self._post_infer("audio_to_video", meta, files=files)
    return self._write_result(raw)

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
    meta = {
      "start_time": start_time,
      "duration": duration,
      "prompt": prompt,
      "mode": mode,
      "resolution": resolution,
      "model": model,
      "seed": seed,
    }
    vid = video_path.read_bytes()
    files = {"video": ("video.mp4", vid, "application/octet-stream")}
    raw = self._post_infer("retake", meta, files=files)
    return self._write_result(raw)

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
    meta = {
      "duration": duration,
      "prompt": prompt,
      "mode": mode,
      "model": model,
      "context": context,
      "seed": seed,
    }
    vid = video_path.read_bytes()
    files = {"video": ("video.mp4", vid, "application/octet-stream")}
    raw = self._post_infer("extend", meta, files=files)
    return self._write_result(raw)

  def prompt_embedding(self, *, prompt: str) -> bytes:
    meta = {"prompt": prompt}
    return self._post_infer("prompt_embedding", meta)

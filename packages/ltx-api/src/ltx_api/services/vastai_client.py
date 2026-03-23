"""Vast.ai REST API client (bundles search, rent, instances, destroy)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)


@dataclass
class VastInstanceInfo:
  """Running instance with enough data to reach the GPU worker over HTTP."""

  instance_id: int
  public_ip: str
  worker_host_port: int


class VastAPIError(RuntimeError):
  pass


def _auth_header(api_key: str) -> dict[str, str]:
  if not api_key.strip():
    msg = "VAST_API_KEY / LTX_API_VAST_API_KEY is required for Vast.ai provisioning"
    raise VastAPIError(msg)
  return {"Authorization": f"Bearer {api_key.strip()}"}


def _gpu_name_variants(gpu_name: str) -> list[str]:
  if gpu_name == "A100_SXM4":
    return ["A100_SXM4", "A100-SXM4", "A100 SXM4"]
  return [gpu_name]


def search_cheapest_offer(
  *,
  client: httpx.Client,
  api_base: str,
  api_key: str,
  gpu_ram_mb: int,
  gpu_name: str,
  disk_search_gb: int,
  geolocation_preferred: str,
  exclude_offer_ids: set[int] | None = None,
) -> int:
  """Return offer id to rent, or raise VastAPIError."""
  headers = {**_auth_header(api_key), "Content-Type": "application/json"}
  gpu_names = _gpu_name_variants(gpu_name)
  geo_list = [c.strip() for c in geolocation_preferred.split(",") if c.strip()]

  def body(ondemand_type: str, with_geo: bool) -> dict[str, Any]:
    base: dict[str, Any] = {
      "limit": 50,
      "verified": {"eq": True},
      "rentable": {"eq": True},
      "rented": {"eq": False},
      "gpu_ram": {"gte": gpu_ram_mb},
      "gpu_name": {"in": gpu_names},
      "disk_space": {"gte": disk_search_gb},
      "allocated_storage": disk_search_gb,
      "order": [["dph_total", "asc"]],
      "type": ondemand_type,
    }
    if with_geo and geo_list:
      base["geolocation"] = {"in": geo_list}
    return base

  urls_tried: list[str] = []
  for ondemand_type in ("ondemand", "bid"):
    for with_geo in (True, False):
      if with_geo and not geo_list:
        continue
      payload = body(ondemand_type, with_geo)
      url = f"{api_base.rstrip('/')}/api/v0/bundles/"
      urls_tried.append(url)
      r = client.post(url, headers=headers, json=payload, timeout=60.0)
      r.raise_for_status()
      data = r.json()
      if not data.get("success", True):
        err = data.get("error") or data.get("msg") or str(data)
        if "auth" in str(err).lower():
          raise VastAPIError(f"Vast.ai auth failed: {err}")
        continue
      offers = data.get("offers") or []
      if offers:
        for offer in offers:
          oid = offer.get("id")
          if oid is None:
            continue
          oid_int = int(oid)
          if exclude_offer_ids and oid_int in exclude_offer_ids:
            continue
          logger.info("Selected Vast offer id=%s type=%s geo=%s", oid_int, ondemand_type, with_geo)
          return oid_int

  raise VastAPIError(f"No Vast offers matched search (tried {len(urls_tried)} requests)")


def create_instance(
  *,
  client: httpx.Client,
  api_base: str,
  api_key: str,
  offer_id: int,
  disk_gb: int,
  label: str,
  template_hash_id: str,
  image: str,
  template_send_disk: bool = False,
  debug_log_payload: bool = False,
) -> int:
  """Start rental; returns new contract / instance id from API."""
  headers = {**_auth_header(api_key), "Content-Type": "application/json"}
  # Template-based create: Vast docs use template_hash_id + optional overrides only.
  # Do not send runtype (conflicts with template). Omit disk unless explicitly requested —
  # LTX_API_VAST_DISK_GB (e.g. 200) often exceeds a cheap offer's max → HTTP 400 invalid_args.
  if template_hash_id.strip():
    body: dict[str, Any] = {"template_hash_id": template_hash_id.strip()}
    if label.strip():
      body["label"] = label.strip()
    if template_send_disk and disk_gb > 0:
      body["disk"] = disk_gb
  else:
    body = {
      "image": image,
      "disk": disk_gb,
      "runtype": "ssh_direct",
      "label": label,
    }
  if debug_log_payload:
    logger.warning("Vast create_instance request offer_id=%s body=%s", offer_id, body)
  url = f"{api_base.rstrip('/')}/api/v0/asks/{offer_id}/"
  r = client.put(url, headers=headers, json=body, timeout=60.0)
  if debug_log_payload:
    preview = (r.text or "")[:2000]
    logger.warning("Vast create_instance response offer_id=%s status=%s body=%s", offer_id, r.status_code, preview)
  if not r.is_success:
    detail: str
    raw_preview: str
    try:
      parsed = r.json()
      err_code = parsed.get("error")
      err_msg = parsed.get("msg")
      if err_code is not None and err_msg is not None:
        detail = f"{err_code}: {err_msg}"
      elif err_msg is not None:
        detail = str(err_msg)
      else:
        detail = str(err_code or parsed)
      raw_preview = str(parsed)[:2000]
    except Exception:
      raw_preview = (r.text or "")[:2000]
      detail = raw_preview or r.reason_phrase
    logger.error(
      "Vast create_instance failed offer_id=%s status=%s body_keys=%s raw=%s",
      offer_id,
      r.status_code,
      list(body.keys()),
      raw_preview,
    )
    raise VastAPIError(
      f"Vast create_instance HTTP {r.status_code} for offer_id={offer_id} "
      f"(template_hash_id set={bool(template_hash_id.strip())}): {detail}"
    )
  data = r.json()
  if not data.get("success"):
    raise VastAPIError(f"Vast create failed: {data}")
  new_id = data.get("new_contract")
  if new_id is None:
    raise VastAPIError(f"Vast create missing new_contract: {data}")
  return int(new_id)


def list_instances(*, client: httpx.Client, api_base: str, api_key: str) -> list[dict[str, Any]]:
  headers = _auth_header(api_key)
  url = f"{api_base.rstrip('/')}/api/v0/instances/"
  r = client.get(url, headers=headers, timeout=60.0)
  r.raise_for_status()
  data = r.json()
  raw = data.get("instances")
  if raw is None:
    return []
  if isinstance(raw, dict):
    return [raw]
  if isinstance(raw, list):
    return raw
  return []


def get_instance_detail(
  *, client: httpx.Client, api_base: str, api_key: str, instance_id: int
) -> dict[str, Any] | None:
  headers = _auth_header(api_key)
  url = f"{api_base.rstrip('/')}/api/v0/instances/{instance_id}/"
  r = client.get(url, headers=headers, timeout=60.0)
  if r.status_code == 404:
    return None
  r.raise_for_status()
  data = r.json()
  inst = data.get("instances")
  if isinstance(inst, list) and inst:
    return inst[0]  # type: ignore[return-value]
  if isinstance(inst, dict):
    return inst
  return None


def _unwrap_instance(obj: dict[str, Any]) -> dict[str, Any]:
  return obj


def host_port_from_ports_mapping(ports: object, internal_port: int) -> int | None:
  if not isinstance(ports, dict):
    return None
  ports_dict = cast(dict[Any, Any], ports)
  for key, val in ports_dict.items():
    if not isinstance(key, str):
      continue
    if not key.startswith(str(internal_port)):
      continue
    if isinstance(val, list) and val and isinstance(val[0], dict):
      hp = val[0].get("HostPort")
      if hp is not None and str(hp) not in ("", "null", "-1"):
        try:
          return int(hp)
        except (TypeError, ValueError):
          continue
  return None


def pick_running_instance(
  instances: list[dict[str, Any]],
  *,
  contract_id: int | None,
  label: str,
) -> dict[str, Any] | None:
  running = [i for i in instances if str(i.get("cur_state") or i.get("actual_status") or "") == "running"]
  if not running:
    return None
  if contract_id is not None:
    for i in running:
      if int(i.get("id") or -1) == contract_id:
        return i
  for i in running:
    if i.get("label") == label:
      return i
  running.sort(key=lambda x: x.get("start_date") or 0, reverse=True)
  return running[0]


def resolve_worker_endpoint(
  inst: dict[str, Any],
  *,
  internal_port: int,
  detail: dict[str, Any] | None,
) -> tuple[str, int] | None:
  """Return (public_ip, host_port) for HTTP to worker, or None if not ready."""
  src = detail if detail else inst
  src = _unwrap_instance(src)
  public_ip = str(src.get("public_ipaddr") or "").strip()
  ports = src.get("ports")
  host_port = host_port_from_ports_mapping(ports, internal_port)
  if public_ip and host_port:
    return public_ip, host_port
  return None


def destroy_instance(*, client: httpx.Client, api_base: str, api_key: str, instance_id: int) -> None:
  headers = _auth_header(api_key)
  url = f"{api_base.rstrip('/')}/api/v0/instances/{instance_id}/"
  r = client.delete(url, headers=headers, timeout=60.0)
  if r.status_code not in (200, 204):
    r.raise_for_status()

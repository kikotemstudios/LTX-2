# Deployment: **ltx-api** (GCP) + GPU worker (Vast.ai)

The HTTP service is **`ltx-api`** (same name as the Python package). In `vastai` mode it coordinates GPU lifecycle and forwards inference to **`ltx-gpu-worker`** on the GPU host.

## Architecture

```mermaid
graph LR
  Desktop[LTX_Desktop] -->|HTTPS_v1| Api[LTX_API]
  Api -->|bundles_rent_instances| VastAPI[Vast.ai_API]
  Api -->|HTTP_POST_infer| Worker[GPU_worker]
  Worker -->|MP4_bytes| Api
  Api -->|idle_timeout_DELETE| VastAPI
```

- **ltx-api** (`LTX_API_INFERENCE_BACKEND=vastai`): no PyTorch in this image ([`deploy/Dockerfile.ltx-api`](../../../deploy/Dockerfile.ltx-api)). Forwards jobs to the worker over HTTP.
- **GPU worker**: `ltx-api[real]` + `ltx-gpu-worker` ([`worker/server.py`](../src/ltx_api/worker/server.py)). Default port **8765**; Vast must map **8765/tcp** → public **HostPort**.

**GCP + Cloud Build:** step-by-step runbook → [`deploy/GCP-DEPLOY.md`](../../../deploy/GCP-DEPLOY.md).

## GCP VM + Docker Compose

**Production (typical):** Cloud Build produces the image; the VM **pulls** only — [`deploy/docker-compose.gcp.yml`](../../../deploy/docker-compose.gcp.yml) + `.env` with **`LTX_DOCKER_IMAGE`** → [`deploy/GCP-DEPLOY.md`](../../../deploy/GCP-DEPLOY.md) §5.

**Dev: local `docker compose build`** (full repo clone on your laptop or a scratch VM — **not** the Cloud Build prod path):

```bash
cp deploy/.env.example deploy/.env
# edit deploy/.env — Vast, auth, public URL; optional LTX_DOCKER_IMAGE (defaults to ltx-api:local when building)

docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

Health: `GET http://<vm>:8080/health`

## Vast.ai modes

### A) Fixed worker URL (no auto-provision)

Set:

```bash
LTX_API_VAST_WORKER_BASE_URL=http://<public_ip>:<mapped_8765>
```

**ltx-api** skips Vast create/destroy. Idle destroy is disabled for this mode.

### B) Auto-provision + idle destroy

Leave `LTX_API_VAST_WORKER_BASE_URL` empty. Set `LTX_API_VAST_API_KEY` and tune search knobs (`LTX_API_VAST_GPU_*`, `LTX_API_VAST_LABEL`, …).

On first `/v1/*` inference request **ltx-api**:

1. Searches bundles and creates an instance (same idea as `kt-ltx-2/scripts/launch_vastai.sh`).
2. Polls until the instance is `running` and `ports` exposes `8765/tcp` → `HostPort`.
3. Polls `GET http://<public_ip>:<host_port>/health` until OK.
4. `POST /infer` on the worker for each pipeline call.

After `LTX_API_VAST_IDLE_TIMEOUT_SECONDS` without inference, it `DELETE`s the instance.

**Important:** The rented image must **start the GPU worker** and **publish port 8765**. Prefer the **Docker image** below; alternatively use [`deploy/worker_setup.sh`](../../../deploy/worker_setup.sh) on the instance (SSH) or a custom Vast template.

## GPU worker Docker image (Vast.ai)

Build from the **monorepo root** (use `linux/amd64` for Vast):

```bash
docker build --platform linux/amd64 -f deploy/Dockerfile.ltx-gpu-worker -t YOUR_REGISTRY/ltx-gpu-worker:latest .
docker push YOUR_REGISTRY/ltx-gpu-worker:latest
```

Point **ltx-api** at the image (template hash empty):

```bash
LTX_API_VAST_TEMPLATE_HASH_ID=
LTX_API_VAST_IMAGE=YOUR_REGISTRY/ltx-gpu-worker:latest
```

Or create a **Vast template** from this image in the Vast console and set `LTX_API_VAST_TEMPLATE_HASH_ID` to that template’s hash.

**First boot:** The entrypoint [`deploy/docker-entrypoint-gpu-worker.sh`](../../../deploy/docker-entrypoint-gpu-worker.sh) downloads the distilled checkpoint and spatial upsampler (public URLs). **Gemma 3** is downloaded with `huggingface_hub` when **`HF_TOKEN`** is set (accept the Gemma license on Hugging Face first). To skip the download, mount pre-downloaded weights at `/models` or set `LTX_API_GEMMA_ROOT` / `LTX_API_CHECKPOINT_PATH` / `LTX_API_SPATIAL_UPSAMPLER_PATH` to existing paths.

**Camera motion LoRAs:** The entrypoint also pulls the seven **Lightricks LTX-2 19b** camera-control adapters (dolly/jib/static) into `LTX_CAMERA_LORA_DIR` (default `/models/ltx-2-19b-lora-camera-control`). They are ~4GB+ total (the static LoRA is ~2.2GB). Set **`LTX_SKIP_CAMERA_LORAS=1`** to skip. `ltx-gpu-worker` does not load them automatically yet; wiring uses `DistilledPipeline(..., loras=...)` when you map `camera_motion` → file path.

**Runtime env (optional):** `LTX_WORKER_PREWARM=1` (default in the image), `HF_TOKEN`, `MODELS_DIR` (default `/models`).

**Non-distilled (full / “pro”) checkpoint:** set `LTX_API_WORKER_PIPELINE=full` (or `LTX_WORKER_WEIGHT_PROFILE=full`). The entrypoint downloads `ltx-2.3-22b-dev.safetensors` and clears `LTX_API_SPATIAL_UPSAMPLER_PATH`. The worker runs `TI2VidOneStagePipeline` for model ids `ltx-2-3-pro` / `ltx-2-pro`.

**Desktop fast + pro on one worker:** set `LTX_API_WORKER_PIPELINE=both`. The entrypoint downloads distilled + spatial upsampler + dev checkpoint and sets `LTX_API_CHECKPOINT_PATH` (distilled), `LTX_API_FULL_CHECKPOINT_PATH` (dev), and `LTX_API_SPATIAL_UPSAMPLER_PATH`. Inference routes by request `model`: `ltx-2-3-fast` → `DistilledPipeline`, `ltx-2-3-pro` → `TI2VidOneStagePipeline` (see [`real_inference.py`](../src/ltx_api/services/real_inference.py)).

## GPU worker setup

1. Sync or clone this repo on the instance (e.g. `/workspace/LTX-2`).
2. Run `bash deploy/worker_setup.sh` (installs `uv`, `ltx-api[real]`, downloads distilled checkpoint + upscaler; you still need **Gemma** at `LTX_API_GEMMA_ROOT` per main README).
3. Export model paths and start:

```bash
export LTX_API_CHECKPOINT_PATH=...
export LTX_API_SPATIAL_UPSAMPLER_PATH=...
export LTX_API_GEMMA_ROOT=...
export LTX_WORKER_HOST=0.0.0.0
export LTX_WORKER_PORT=8765
cd /workspace/LTX-2
uv run ltx-gpu-worker
```

## LTX Desktop: cold GPU UX

When using “API generation” against **ltx-api**, the Desktop shows phase **`warming_gpu`** (“Starting GPU instance…”) while the blocking HTTP request is in flight (after uploads, before the video returns). See `LTX-Desktop` `video_generation_handler.py` + `use-generation.ts`.

## Environment reference

All settings use prefix `LTX_API_` (see `Settings` in [`config.py`](../src/ltx_api/config.py)). [`deploy/.env.example`](../../../deploy/.env.example) lists the Vast-related entries.

## Local Python package layout

The **ltx-api** image installs **only** `packages/ltx-api` without `[real]`. For a dev venv with GPU + pipelines:

```bash
uv pip install -e './packages/ltx-api[real,dev]'
```

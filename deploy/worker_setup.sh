#!/usr/bin/env bash
# =============================================================================
# GPU worker bootstrap on Vast.ai / RunPod-style hosts (no ComfyUI).
# Prefer baking a worker image: deploy/Dockerfile.ltx-gpu-worker + docker-entrypoint-gpu-worker.sh
# (see packages/ltx-api/docs/deployment.md). This script is for manual SSH/bootstrap.
# Run once on the instance (e.g. via SSH after rsync or cloud-init).
#
# Expects:
#   - CUDA-capable machine, repo at LTX2_DIR (default /workspace/LTX-2)
#   - Optional HF_TOKEN for gated downloads
#
# Installs uv, syncs Python deps with ltx-api[real], downloads core LTX-2.3
# distilled assets, starts ltx-gpu-worker on LTX_WORKER_PORT (default 8765).
# =============================================================================
set -euo pipefail

WORKSPACE="${WORKSPACE:-/workspace}"
LTX2_DIR="${LTX2_DIR:-${WORKSPACE}/LTX-2}"
MODELS_DIR="${MODELS_DIR:-${WORKSPACE}/models}"
export PATH="${HOME}/.local/bin:${PATH}"

echo "==> [1/6] Installing uv..."
if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv --version

echo "==> [2/6] Resolving LTX-2 repo at ${LTX2_DIR}..."
if [ ! -d "${LTX2_DIR}/packages/ltx-api" ]; then
  echo "    Clone or rsync the LTX-2 monorepo to ${LTX2_DIR} first."
  exit 1
fi

echo "==> [3/6] Installing ltx-api[real] (GPU + pipelines)..."
cd "${LTX2_DIR}"
uv sync --frozen --package ltx-api --extra real || uv sync --package ltx-api --extra real

echo "==> [4/6] Hugging Face auth (optional)..."
if [ -n "${HF_TOKEN:-}" ]; then
  uv run hf auth login --token "${HF_TOKEN}" 2>/dev/null || true
fi

echo "==> [5/6] Model weights (LTX-2.3 on Hugging Face)..."
mkdir -p "${MODELS_DIR}"
HF_BASE="https://huggingface.co/Lightricks/LTX-2.3/resolve/main"
CKPT="${MODELS_DIR}/ltx-2.3-22b-distilled.safetensors"
UP="${MODELS_DIR}/ltx-2.3-spatial-upscaler-x2-1.0.safetensors"
DEV_CKPT="${MODELS_DIR}/ltx-2.3-22b-dev.safetensors"
PROFILE="${LTX_WORKER_DOWNLOAD_PROFILE:-distilled}"

if [ ! -f "${CKPT}" ]; then
  echo "    Downloading distilled checkpoint..."
  curl -L --progress-bar -o "${CKPT}" \
    "${HF_BASE}/ltx-2.3-22b-distilled.safetensors"
fi
if [ ! -f "${UP}" ]; then
  echo "    Downloading spatial upscaler..."
  curl -L --progress-bar -o "${UP}" \
    "${HF_BASE}/ltx-2.3-spatial-upscaler-x2-1.0.safetensors"
fi
if [ "${PROFILE}" = "both" ] && [ ! -f "${DEV_CKPT}" ]; then
  echo "    Downloading dev checkpoint (pro / one-stage)..."
  curl -L --progress-bar -o "${DEV_CKPT}" \
    "${HF_BASE}/ltx-2.3-22b-dev.safetensors"
fi

if [ "${LTX_SKIP_CAMERA_LORAS:-}" != "1" ]; then
  echo "    Camera control LoRAs (Lightricks LTX-2 19b; ~4GB+ total, static ~2.2GB)..."
  CAMERA_DIR="${LTX_CAMERA_LORA_DIR:-${MODELS_DIR}/ltx-2-19b-lora-camera-control}"
  mkdir -p "${CAMERA_DIR}"
  HF_HUB="https://huggingface.co"
  _cam_download() {
    local url="$1" dest="$2"
    if [ -f "${dest}" ]; then
      return 0
    fi
    curl -fL --retry 3 --progress-bar -o "${dest}" "${url}"
  }
  for pair in \
    "LTX-2-19b-LoRA-Camera-Control-Dolly-In|ltx-2-19b-lora-camera-control-dolly-in.safetensors" \
    "LTX-2-19b-LoRA-Camera-Control-Dolly-Left|ltx-2-19b-lora-camera-control-dolly-left.safetensors" \
    "LTX-2-19b-LoRA-Camera-Control-Dolly-Out|ltx-2-19b-lora-camera-control-dolly-out.safetensors" \
    "LTX-2-19b-LoRA-Camera-Control-Dolly-Right|ltx-2-19b-lora-camera-control-dolly-right.safetensors" \
    "LTX-2-19b-LoRA-Camera-Control-Jib-Down|ltx-2-19b-lora-camera-control-jib-down.safetensors" \
    "LTX-2-19b-LoRA-Camera-Control-Jib-Up|ltx-2-19b-lora-camera-control-jib-up.safetensors" \
    "LTX-2-19b-LoRA-Camera-Control-Static|ltx-2-19b-lora-camera-control-static.safetensors"
  do
    IFS='|' read -r _repo _fname <<<"${pair}"
    _cam_download "${HF_HUB}/Lightricks/${_repo}/resolve/main/${_fname}" "${CAMERA_DIR}/${_fname}"
  done
  echo "    Camera LoRAs at ${CAMERA_DIR} (export LTX_CAMERA_LORA_DIR=${CAMERA_DIR})"
else
  echo "    Skipping camera LoRAs (LTX_SKIP_CAMERA_LORAS=1)"
fi

echo "    Set LTX_API_GEMMA_ROOT to your local Gemma 3 checkout (see repo README)."

echo "==> [6/6] Worker systemd-less start hint..."
cat <<EOF

Export paths then start the worker (expose ${LTX_WORKER_PORT:-8765} in Vast port map):

  export LTX_API_CHECKPOINT_PATH='${CKPT}'
  export LTX_API_SPATIAL_UPSAMPLER_PATH='${UP}'
  export LTX_API_GEMMA_ROOT='/path/to/gemma-3-12b-it-qat-q4_0-unquantized'
  # LTX Desktop fast + pro on one GPU: LTX_WORKER_DOWNLOAD_PROFILE=both re-runs [5/6], then:
  # export LTX_API_FULL_CHECKPOINT_PATH='${DEV_CKPT}'
  # export LTX_API_WORKER_PIPELINE=both
  # export LTX_CAMERA_LORA_DIR='${MODELS_DIR}/ltx-2-19b-lora-camera-control'
  export LTX_WORKER_HOST=0.0.0.0
  export LTX_WORKER_PORT=${LTX_WORKER_PORT:-8765}
  cd ${LTX2_DIR}
  uv run ltx-gpu-worker

Or nohup:
  nohup uv run ltx-gpu-worker >> /tmp/ltx-worker.log 2>&1 &

EOF

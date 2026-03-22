#!/usr/bin/env bash
# =============================================================================
# GPU worker bootstrap on Vast.ai / RunPod-style hosts (no ComfyUI).
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

echo "==> [5/6] Model weights (distilled fast path — adjust URLs if you use LTX-2.2 paths)..."
mkdir -p "${MODELS_DIR}"
CKPT="${MODELS_DIR}/ltx-2.3-22b-distilled.safetensors"
UP="${MODELS_DIR}/ltx-2.3-spatial-upscaler-x2-1.0.safetensors"
if [ ! -f "${CKPT}" ]; then
  echo "    Downloading distilled checkpoint..."
  curl -L --progress-bar -o "${CKPT}" \
    "https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-22b-distilled.safetensors"
fi
if [ ! -f "${UP}" ]; then
  echo "    Downloading spatial upscaler..."
  curl -L --progress-bar -o "${UP}" \
    "https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.0.safetensors"
fi
echo "    Set LTX_API_GEMMA_ROOT to your local Gemma 3 checkout (see repo README)."

echo "==> [6/6] Worker systemd-less start hint..."
cat <<EOF

Export paths then start the worker (expose ${LTX_WORKER_PORT:-8765} in Vast port map):

  export LTX_API_CHECKPOINT_PATH='${CKPT}'
  export LTX_API_SPATIAL_UPSAMPLER_PATH='${UP}'
  export LTX_API_GEMMA_ROOT='/path/to/gemma-3-12b-it-qat-q4_0-unquantized'
  export LTX_WORKER_HOST=0.0.0.0
  export LTX_WORKER_PORT=${LTX_WORKER_PORT:-8765}
  cd ${LTX2_DIR}
  uv run ltx-gpu-worker

Or nohup:
  nohup uv run ltx-gpu-worker >> /tmp/ltx-worker.log 2>&1 &

EOF

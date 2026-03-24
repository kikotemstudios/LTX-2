#!/usr/bin/env bash
# =============================================================================
# GPU worker entrypoint for Vast.ai / any CUDA host.
#
# Weight profile (LTX_API_WORKER_PIPELINE or LTX_WORKER_WEIGHT_PROFILE):
#   distilled — DistilledPipeline only (Desktop "fast" / ltx-2-3-fast):
#     ltx-2.3-22b-distilled.safetensors + spatial upscaler x2.
#   full — TI2VidOneStagePipeline only (Desktop "pro" / ltx-2-3-pro):
#     ltx-2.3-22b-dev.safetensors; no spatial upsampler.
#   both — downloads dev + distilled + upsampler; routes by model id (use with LTX Desktop).
#
# Gemma 3: LTX_API_GEMMA_ROOT or /models/gemma-3-12b-it-qat-q4_0-unquantized;
#   downloads via huggingface_hub when HF_TOKEN is set and weights missing.
#
# Camera motion LoRAs: Lightricks publishes these as LTX-2 *19b* adapters (HF repos
#   LTX-2-19b-LoRA-Camera-Control-*). Stored under LTX_CAMERA_LORA_DIR (default
#   $MODELS_DIR/ltx-2-19b-lora-camera-control). Skip with LTX_SKIP_CAMERA_LORAS=1.
#
# Starts ltx-gpu-worker on LTX_WORKER_HOST:LTX_WORKER_PORT (default 8765).
# =============================================================================
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/workspace/LTX-2}"
MODELS_DIR="${MODELS_DIR:-/models}"
mkdir -p "$MODELS_DIR"

# Resolve pipeline mode: prefer LTX_API_WORKER_PIPELINE, else LTX_WORKER_WEIGHT_PROFILE, else distilled
RAW_MODE="${LTX_API_WORKER_PIPELINE:-${LTX_WORKER_WEIGHT_PROFILE:-distilled}}"
WORKER_PIPELINE="$(echo "$RAW_MODE" | tr '[:upper:]' '[:lower:]')"
case "$WORKER_PIPELINE" in
  distilled|full|both) ;;
  *)
    echo "ERROR: LTX_API_WORKER_PIPELINE must be 'distilled', 'full', or 'both' (got: $RAW_MODE)"
    exit 1
    ;;
esac

GEMMA="${LTX_API_GEMMA_ROOT:-${MODELS_DIR}/gemma-3-12b-it-qat-q4_0-unquantized}"
export LTX_API_GEMMA_ROOT="$GEMMA"
export LTX_API_STORAGE_DIR="${LTX_API_STORAGE_DIR:-/data/ltx-api-storage}"
mkdir -p "$LTX_API_GEMMA_ROOT"
mkdir -p "$LTX_API_STORAGE_DIR"

download_if_missing() {
  local url="$1"
  local dest="$2"
  local name="$3"
  if [[ -f "$dest" ]]; then
    echo "==> Found $name at $dest"
    return 0
  fi
  echo "==> Downloading $name..."
  mkdir -p "$(dirname "$dest")"
  curl -fL --retry 3 --retry-delay 5 -o "$dest" "$url"
}

HF_BASE="https://huggingface.co/Lightricks/LTX-2.3/resolve/main"
HF_HUB="https://huggingface.co"

download_camera_loras() {
  if [[ "${LTX_SKIP_CAMERA_LORAS:-}" == "1" ]]; then
    echo "==> Skipping camera LoRA downloads (LTX_SKIP_CAMERA_LORAS=1)"
    return 0
  fi
  local dir="${LTX_CAMERA_LORA_DIR:-${MODELS_DIR}/ltx-2-19b-lora-camera-control}"
  mkdir -p "$dir"
  export LTX_CAMERA_LORA_DIR="$dir"
  echo "==> Camera control LoRAs (Lightricks LTX-2 19b) → $dir"
  local pairs=(
    "LTX-2-19b-LoRA-Camera-Control-Dolly-In|ltx-2-19b-lora-camera-control-dolly-in.safetensors"
    "LTX-2-19b-LoRA-Camera-Control-Dolly-Left|ltx-2-19b-lora-camera-control-dolly-left.safetensors"
    "LTX-2-19b-LoRA-Camera-Control-Dolly-Out|ltx-2-19b-lora-camera-control-dolly-out.safetensors"
    "LTX-2-19b-LoRA-Camera-Control-Dolly-Right|ltx-2-19b-lora-camera-control-dolly-right.safetensors"
    "LTX-2-19b-LoRA-Camera-Control-Jib-Down|ltx-2-19b-lora-camera-control-jib-down.safetensors"
    "LTX-2-19b-LoRA-Camera-Control-Jib-Up|ltx-2-19b-lora-camera-control-jib-up.safetensors"
    "LTX-2-19b-LoRA-Camera-Control-Static|ltx-2-19b-lora-camera-control-static.safetensors"
  )
  local p repo fname url
  for p in "${pairs[@]}"; do
    IFS='|' read -r repo fname <<<"$p"
    url="${HF_HUB}/Lightricks/${repo}/resolve/main/${fname}"
    download_if_missing "$url" "${dir}/${fname}" "$fname"
  done
}

if [[ "$WORKER_PIPELINE" == "full" ]]; then
  echo "==> Worker pipeline: full (non-distilled / one-stage; no spatial upsampler)"
  unset LTX_API_FULL_CHECKPOINT_PATH 2>/dev/null || true
  CKPT="${LTX_API_CHECKPOINT_PATH:-${MODELS_DIR}/ltx-2.3-22b-dev.safetensors}"
  export LTX_API_CHECKPOINT_PATH="$CKPT"
  export LTX_API_WORKER_PIPELINE=full
  # DistilledPipeline expects an upsampler path; full / one-stage does not.
  export LTX_API_SPATIAL_UPSAMPLER_PATH=""

  download_if_missing \
    "${HF_BASE}/ltx-2.3-22b-dev.safetensors" \
    "$CKPT" \
    "LTX-2.3 dev checkpoint (non-distilled)"

elif [[ "$WORKER_PIPELINE" == "both" ]]; then
  echo "==> Worker pipeline: both (dev + distilled + upsampler; routes by model id)"
  DIST_CKPT="${LTX_API_CHECKPOINT_PATH:-${MODELS_DIR}/ltx-2.3-22b-distilled.safetensors}"
  DEV_CKPT="${LTX_API_FULL_CHECKPOINT_PATH:-${MODELS_DIR}/ltx-2.3-22b-dev.safetensors}"
  UP="${LTX_API_SPATIAL_UPSAMPLER_PATH:-${MODELS_DIR}/ltx-2.3-spatial-upscaler-x2-1.0.safetensors}"
  export LTX_API_CHECKPOINT_PATH="$DIST_CKPT"
  export LTX_API_FULL_CHECKPOINT_PATH="$DEV_CKPT"
  export LTX_API_SPATIAL_UPSAMPLER_PATH="$UP"
  export LTX_API_WORKER_PIPELINE=both

  download_if_missing \
    "${HF_BASE}/ltx-2.3-22b-distilled.safetensors" \
    "$DIST_CKPT" \
    "distilled checkpoint"

  download_if_missing \
    "${HF_BASE}/ltx-2.3-spatial-upscaler-x2-1.0.safetensors" \
    "$UP" \
    "spatial upsampler"

  download_if_missing \
    "${HF_BASE}/ltx-2.3-22b-dev.safetensors" \
    "$DEV_CKPT" \
    "LTX-2.3 dev checkpoint (non-distilled)"

else
  echo "==> Worker pipeline: distilled (two-stage)"
  unset LTX_API_FULL_CHECKPOINT_PATH 2>/dev/null || true
  CKPT="${LTX_API_CHECKPOINT_PATH:-${MODELS_DIR}/ltx-2.3-22b-distilled.safetensors}"
  UP="${LTX_API_SPATIAL_UPSAMPLER_PATH:-${MODELS_DIR}/ltx-2.3-spatial-upscaler-x2-1.0.safetensors}"
  export LTX_API_CHECKPOINT_PATH="$CKPT"
  export LTX_API_WORKER_PIPELINE=distilled
  export LTX_API_SPATIAL_UPSAMPLER_PATH="$UP"

  download_if_missing \
    "${HF_BASE}/ltx-2.3-22b-distilled.safetensors" \
    "$CKPT" \
    "distilled checkpoint"

  download_if_missing \
    "${HF_BASE}/ltx-2.3-spatial-upscaler-x2-1.0.safetensors" \
    "$UP" \
    "spatial upsampler"
fi

download_camera_loras

_has_gemma_config() {
  find "$GEMMA" -maxdepth 6 -name 'config.json' -print -quit 2>/dev/null | grep -q .
}

if ! _has_gemma_config; then
  if [[ -z "${HF_TOKEN:-}" ]]; then
    echo "ERROR: Gemma weights not found under $GEMMA and HF_TOKEN is unset."
    echo "  Accept the Gemma license on Hugging Face, then pass HF_TOKEN at runtime, or mount pre-downloaded weights."
    exit 1
  fi
  echo "==> Downloading Gemma 3 (may take a long time)..."
  cd "$REPO_ROOT"
  uv run python -c "
import os
from huggingface_hub import snapshot_download
root = os.environ['LTX_API_GEMMA_ROOT']
snapshot_download(
  repo_id='google/gemma-3-12b-it-qat-q4_0-unquantized',
  local_dir=root,
  token=os.environ.get('HF_TOKEN'),
)
"
fi

export LTX_WORKER_HOST="${LTX_WORKER_HOST:-0.0.0.0}"
export LTX_WORKER_PORT="${LTX_WORKER_PORT:-8765}"
export LTX_WORKER_PREWARM="${LTX_WORKER_PREWARM:-1}"

cd "$REPO_ROOT"
exec uv run ltx-gpu-worker

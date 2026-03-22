# Development

## Setup

From repo root (with `uv`):

```bash
uv sync --package ltx-api
cd packages/ltx-api
PYTHONPATH=src uv run pytest
```

GPU / `RealInferenceBackend` tests need optional pipelines: `uv pip install -e '.[real,dev]'` from `packages/ltx-api`.

Or use a venv and `pip install -e ".[dev]"` from `packages/ltx-api`.

## TDD

- Default `LTX_API_INFERENCE_BACKEND=mock` uses canned `tests/fixtures/test_video.mp4`.
- Real GPU tests: `pytest -m gpu` (requires weights and CUDA; most tests are skipped by default).

## Run server

```bash
export LTX_API_INFERENCE_BACKEND=mock
export LTX_API_AUTH_TOKEN=  # empty = no auth
uv run python -c "from ltx_api.main import run; run()"
```

Or:

```bash
uvicorn ltx_api.main:create_app_instance --factory --host 0.0.0.0 --port 8080
```

## Environment

See `ltx_api.config.Settings` — all variables use prefix `LTX_API_`.

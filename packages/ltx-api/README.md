# ltx-api

Self-hosted REST API mirroring the [LTX commercial API](https://docs.ltx.video/welcome), for use with **LTX Desktop** or any client that speaks the same HTTP contract.

## Quick start

```bash
# From repo root (uv) or pip install -e packages/ltx-api[dev]
export LTX_API_INFERENCE_BACKEND=mock
python -m uvicorn ltx_api.main:create_app_instance --factory --host 127.0.0.1 --port 8080
```

- **Mock backend** (default in dev): returns `tests/fixtures/test_video.mp4` for all generations — fast TDD, no GPU.
- **Real backend**: `LTX_API_INFERENCE_BACKEND=real` plus `pip install -e '.[real]'` / `uv sync --extra real` and `LTX_API_CHECKPOINT_PATH`, `LTX_API_GEMMA_ROOT`, `LTX_API_SPATIAL_UPSAMPLER_PATH` — distilled/fast T2V only for now.
- **Vast.ai / remote worker**: `LTX_API_INFERENCE_BACKEND=vastai` — **ltx-api** forwards to `ltx-gpu-worker` (HTTP). See [docs/deployment.md](docs/deployment.md) and [deploy/GCP-DEPLOY.md](../../deploy/GCP-DEPLOY.md).

## Docs

| Doc | Purpose |
|-----|---------|
| [docs/api-reference.md](docs/api-reference.md) | Endpoints overview |
| [docs/development.md](docs/development.md) | Tests, env vars |
| [docs/desktop-integration.md](docs/desktop-integration.md) | LTX Desktop env + settings |
| [docs/deployment.md](docs/deployment.md) | **ltx-api** on GCP + Vast.ai GPU worker |
| [deploy/GCP-DEPLOY.md](../../deploy/GCP-DEPLOY.md) | gcloud, Cloud Build, VM runbook |

## Tests

```bash
pytest packages/ltx-api/tests
pytest packages/ltx-api/tests -m gpu   # optional GPU / weights
```

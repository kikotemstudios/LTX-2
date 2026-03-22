# Deploy **ltx-api**

| File | Purpose |
|------|---------|
| [`Dockerfile.ltx-api`](Dockerfile.ltx-api) | Container image: HTTP API only (no GPU / no `[real]` extra). |
| [`docker-compose.yml`](docker-compose.yml) | Dev: build from repo — **keep under `deploy/` in the clone**; don’t copy alone to `/opt/ltx`. |
| [`docker-compose.gcp.yml`](docker-compose.gcp.yml) | **Prod VM:** pull-only; image from Cloud Build → Artifact Registry (`LTX_DOCKER_IMAGE`). |
| [`cloudbuild.yaml`](cloudbuild.yaml) | Cloud Build: build + push `ltx-api` to Artifact Registry. |
| [`GCP-DEPLOY.md`](GCP-DEPLOY.md) | **gcloud**, Cloud Build, VM **`docker compose`** steps. |
| [`.env.example`](.env.example) | Env template for `vastai` / auth / Vast. |
| [`worker_setup.sh`](worker_setup.sh) | GPU host bootstrap for `ltx-gpu-worker`. |

Architecture and Vast behavior: [`packages/ltx-api/docs/deployment.md`](../packages/ltx-api/docs/deployment.md).

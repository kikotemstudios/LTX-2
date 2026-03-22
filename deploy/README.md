# Deploy **ltx-api**

| File | Purpose |
|------|---------|
| [`Dockerfile.ltx-api`](Dockerfile.ltx-api) | Container image: HTTP API only (no GPU / no `[real]` extra). |
| [`docker-compose.yml`](docker-compose.yml) | Local/VM compose; service name **`ltx-api`**. |
| [`cloudbuild.yaml`](cloudbuild.yaml) | Cloud Build: build + push `ltx-api` to Artifact Registry. |
| [`GCP-DEPLOY.md`](GCP-DEPLOY.md) | **gcloud**, Cloud Build, VM `docker run` steps. |
| [`.env.example`](.env.example) | Env template for `vastai` / auth / Vast. |
| [`worker_setup.sh`](worker_setup.sh) | GPU host bootstrap for `ltx-gpu-worker`. |

Architecture and Vast behavior: [`packages/ltx-api/docs/deployment.md`](../packages/ltx-api/docs/deployment.md).

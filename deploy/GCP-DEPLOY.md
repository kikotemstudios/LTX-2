# Deploy **ltx-api** to a GCP VM (gcloud + Cloud Build)

Naming: the container image and service are **`ltx-api`**. The GPU side is **`ltx-gpu-worker`** (Vast / RunPod).

## Prerequisites

- `gcloud` CLI authenticated (`gcloud auth login`)
- A GCP project and a VM with **Docker** installed
- Firewall allows **TCP 8080** (or your `LTX_PUBLISH_PORT`) to the VM

## 1) One-time: Artifact Registry

```bash
export PROJECT_ID=your-project-id
export REGION=us-central1
export AR_REPO=ltx-docker

gcloud config set project "$PROJECT_ID"

gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="LTX images" 2>/dev/null || true
```

## 2) One-time: let Cloud Build push images

```bash
PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" \
  --location="$REGION" \
  --member="serviceAccount:${PROJECT_NUM}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

## 3) Build and push (Cloud Build)

From the **monorepo root** (parent of `deploy/`):

```bash
gcloud builds submit --config=deploy/cloudbuild.yaml .
```

Image tags:

- `${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/ltx-api:latest`
- same with `$SHORT_SHA`

Override region/repo/name:

```bash
gcloud builds submit --config=deploy/cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_AR_REPO=ltx-docker,_IMAGE_NAME=ltx-api .
```

## 4) One-time: VM can pull from Artifact Registry

**Option A — you SSH as your user**

On the VM:

```bash
gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

**Option B — VM service account**

Attach a service account to the VM with **`roles/artifactregistry.reader`**, then on the VM use metadata-based auth or `gcloud auth configure-docker` as that identity.

## 5) Run **ltx-api** on the VM

Create env file (copy from [`deploy/.env.example`](.env.example)):

```bash
sudo mkdir -p /opt/ltx
sudo cp deploy/.env.example /opt/ltx/.env   # if you copied repo; else create manually
sudo nano /opt/ltx/.env
```

Pull and run:

```bash
export REGION=us-central1
export PROJECT_ID=your-project-id
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/ltx-docker/ltx-api:latest"

docker pull "$IMAGE"

docker rm -f ltx-api 2>/dev/null || true
docker run -d --name ltx-api --restart unless-stopped \
  -p 8080:8080 \
  --env-file /opt/ltx/.env \
  -e LTX_API_STORAGE_DIR=/data/ltx-api-storage \
  -v ltx-api-data:/data/ltx-api-storage \
  "$IMAGE"
```

Check:

```bash
curl -sS http://127.0.0.1:8080/health
```

## 6) Firewall (if needed)

```bash
gcloud compute firewall-rules create allow-ltx-api-8080 \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp:8080 \
  --target-tags=ltx-api \
  --source-ranges=0.0.0.0/0 \
  --description="ltx-api HTTP" 2>/dev/null || true

gcloud compute instances add-tags YOUR_VM_NAME --zone=YOUR_ZONE --tags=ltx-api
```

Tighten `--source-ranges` for production.

## 7) Optional: redeploy from Cloud Build via SSH

Add a second Cloud Build step (after the image push) using `gcr.io/google.com/cloudsdktool/cloud-sdk` and:

```bash
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE --command='
  docker pull REGION-docker.pkg.dev/PROJECT_ID/ltx-docker/ltx-api:latest && \
  docker rm -f ltx-api 2>/dev/null; \
  docker run -d --name ltx-api --restart unless-stopped -p 8080:8080 \
    --env-file /opt/ltx/.env -e LTX_API_STORAGE_DIR=/data/ltx-api-storage \
    -v ltx-api-data:/data/ltx-api-storage \
    REGION-docker.pkg.dev/PROJECT_ID/ltx-docker/ltx-api:latest
'
```

Wire OS Login / SSH keys the same way your existing pipeline does.

## Compose on the VM

If the **full repo** is on the VM:

```bash
cp deploy/.env.example deploy/.env
# edit deploy/.env
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

Service name is **`ltx-api`**.

# Deploy **ltx-api** to a GCP VM (gcloud + Cloud Build)

Naming: the container image and service are **`ltx-api`**. The GPU side is **`ltx-gpu-worker`** (Vast / RunPod).

**Where the image is built:** **`ltx-api` is built in Cloud Build** (§3) and pushed to Artifact Registry. The **GCP VM never runs `docker compose build`** for the API — only **`docker compose pull`** + **`up`**.

## Prerequisites

- `gcloud` CLI authenticated (`gcloud auth login`)
- A GCP project and a VM with **Docker** + **Compose V2** (`docker compose version`) — **pull/run only**, not build
- Firewall allows **TCP 8080** (or your `LTX_PUBLISH_PORT`) to the VM

## Git / repo on the VM?

**You do not need to clone this repo on the GCP VM** for the usual flow: Cloud Build produces the **`ltx-api`** image, the VM only **pulls** that image from Artifact Registry and runs it with an env file.

| Where | Need git? |
|-------|-----------|
| **Your laptop / CI** (step 3) | Yes — `gcloud builds submit` uploads the directory you run it from (monorepo root). Or connect Cloud Build to Cloud Source Repositories / GitHub so triggers build from git without a local clone. |
| **GCP VM** (steps 4–5) | **No** — install Docker + Compose plugin, configure `docker` auth for Artifact Registry, drop [`docker-compose.gcp.yml`](docker-compose.gcp.yml) + `.env` under `/opt/ltx`, `docker compose pull && docker compose up -d`. |
| **GCP VM** | **Do not** use [`docker-compose.yml`](docker-compose.yml) (`build:`) for production — that’s for **laptop / dev** with a full repo clone. Prod VM = **pull-only** [`docker-compose.gcp.yml`](docker-compose.gcp.yml). |

**`.env` on the VM without the repo:** copy variable names and values from [`.env.example`](.env.example) in GitHub (raw or browser), or from your laptop after `git clone`, or:

```bash
sudo mkdir -p /opt/ltx
sudo curl -fsSL -o /opt/ltx/.env.example 'https://raw.githubusercontent.com/YOUR_ORG/LTX-2/main/deploy/.env.example'
sudo cp /opt/ltx/.env.example /opt/ltx/.env
sudo chown -R "$USER:$USER" /opt/ltx
chmod 600 /opt/ltx/.env
nano /opt/ltx/.env
# Set LTX_DOCKER_IMAGE to your Artifact Registry URL (see §5 for compose).
```

(Replace `YOUR_ORG/LTX-2` and branch if needed. **Several SSH users on one VM:** don’t `chown` to yourself — after you have the full `/opt/ltx` tree (§5), apply **Shared VM** there: group `ltx`, `chmod 2775`, `usermod` loop, `chmod 640` on `.env`.)


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

Cloud Build pushes with **one** service account. It is often **`PROJECT_NUMBER@cloudbuild.gserviceaccount.com`**, but many projects are set up so builds run as the **default Compute Engine** SA instead: **`PROJECT_NUMBER-compute@developer.gserviceaccount.com`**. If push fails with `uploadArtifacts` denied, check the build log line *“The service account running this build …”* and grant **that** identity `roles/artifactregistry.writer` on the repo.

```bash
PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

# Typical Cloud Build service account
gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" \
  --location="$REGION" \
  --member="serviceAccount:${PROJECT_NUM}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Default Compute Engine SA (often the actual build runner — fixes push denied)
gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" \
  --location="$REGION" \
  --member="serviceAccount:${PROJECT_NUM}-compute@developer.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

Optional — if the log warns the build SA cannot write to Cloud Logging:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUM}-compute@developer.gserviceaccount.com" \
  --role="roles/logging.logWriter"
```

## 3) Build and push (Cloud Build)

From the **monorepo root** (parent of `deploy/`):

```bash
gcloud builds submit --config=deploy/cloudbuild.yaml .
```

Image tags:

- `${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/ltx-api:latest`
- same with `$SHORT_SHA`

**Manual `gcloud builds submit`:** `SHORT_SHA` defaults to **empty** (only set for repo-triggered builds). Set the **default** substitution `SHORT_SHA` — not `_SHORT_SHA` (underscore keys are *custom* and must appear as `${_FOO}` in `cloudbuild.yaml`; this file uses built-in `$SHORT_SHA`).

```bash
gcloud builds submit --config=deploy/cloudbuild.yaml \
  --substitutions=_REGION=northamerica-south1,SHORT_SHA=$(git rev-parse --short HEAD) .
```

Override region/repo/name only:

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

## 5) Run **ltx-api** on the VM (Docker Compose)

No git required. **No image build on the VM** — use the image from §3. Docker **Compose V2** (`docker compose`, not deprecated `docker-compose`), two files under `/opt/ltx`: save [`docker-compose.gcp.yml`](docker-compose.gcp.yml) as `docker-compose.yml` + `.env`.

```bash
sudo mkdir -p /opt/ltx

# Compose file (replace YOUR_ORG / branch if needed)
sudo curl -fsSL -o /opt/ltx/docker-compose.yml \
  'https://raw.githubusercontent.com/YOUR_ORG/LTX-2/main/deploy/docker-compose.gcp.yml'

sudo curl -fsSL -o /opt/ltx/.env.example \
  'https://raw.githubusercontent.com/YOUR_ORG/LTX-2/main/deploy/.env.example'
```

### `/opt/ltx` permissions (SSH users, not only root)

`sudo` above leaves files owned by **root**. Everyone who should run `docker compose` here needs the **`docker`** group (or use `sudo docker …`). **`docker compose` must be able to read `.env`** — so either your user owns `.env`, or `.env` is **group-readable** for a shared group (never world-readable).

**Shared VM — any normal login should use `/opt/ltx` (recommended)**

Use a dedicated group **`ltx`**, **setgid** on the directory (`2775` = group `rwx`, others `r-x` so anyone can `cd` and read non-secret files), and put every human account in **`ltx`** + **`docker`**.

```bash
sudo groupadd -f ltx
sudo chgrp ltx /opt/ltx
sudo chmod 2775 /opt/ltx
sudo chgrp ltx /opt/ltx/docker-compose.yml /opt/ltx/.env.example
sudo chmod 640 /opt/ltx/docker-compose.yml /opt/ltx/.env.example

# Everyone with a “normal” UID (typical Debian/Ubuntu login users):
for u in $(getent passwd | awk -F: '$3 >= 1000 && $1 != "nobody" {print $1}'); do
  sudo usermod -aG ltx,docker "$u"
done
# …or only specific people:
#   sudo usermod -aG ltx,docker alice
#   sudo usermod -aG ltx,docker bob
```

Affected users must **log out and SSH back in** (or `newgrp ltx` / `newgrp docker`) so the new groups apply.

Then as any of those users:

```bash
cd /opt/ltx
cp .env.example .env && nano .env    # new file inherits group ltx (setgid)
chmod 640 .env                        # group-readable; still not world-readable
```

**`.env` holds secrets** — everyone in `ltx` can read it. If that’s too broad, don’t use the loop: keep **`600`** on `.env` and only one ops user in `ltx`, or use a secrets manager / root-only file + `sudo docker compose`.

**Single operator only** — one user owns the tree:

```bash
sudo chown -R "$USER:$USER" /opt/ltx
sudo chmod 750 /opt/ltx
cd /opt/ltx
cp .env.example .env && chmod 600 .env && nano .env
sudo usermod -aG docker "$USER"   # re-login afterward
```

In `.env`, set at least:

- **`LTX_DOCKER_IMAGE`** — full Artifact Registry reference, e.g.  
  `northamerica-south1-docker.pkg.dev/kikotem-dev/ltx-docker/ltx-api:latest`
- **`LTX_API_PUBLIC_BASE_URL`**, **`LTX_API_AUTH_TOKEN`**, Vast vars as needed.

The GCP compose file is **`/opt/ltx/docker-compose.yml`** so plain `docker compose` works from that directory. Pull and start:

```bash
cd /opt/ltx
docker compose pull
docker compose up -d
```

Redeploy after a new image push:

```bash
cd /opt/ltx
docker compose pull && docker compose up -d
```

Check:

```bash
curl -sS http://127.0.0.1:8080/health
```

**`resolve: lstat /opt/deploy: no such file or directory`** — you opened the **dev** [`docker-compose.yml`](docker-compose.yml) (`build:`) on the VM. With Cloud Build you should **never** build the API on the VM. Replace the file with the **pull-only** GCP compose: re-run the §5 `curl` that downloads [`docker-compose.gcp.yml`](docker-compose.gcp.yml) as `docker-compose.yml`, then `docker compose pull && docker compose up -d`.

**If you already cloned the repo on the VM**, you can instead: `cd /path/to/LTX-2/deploy && cp .env.example .env && nano .env` (set `LTX_DOCKER_IMAGE`), then  
`docker compose -f docker-compose.gcp.yml --env-file .env up -d` (after `pull`).

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
  cd /opt/ltx && docker compose pull && docker compose up -d
'
```

Wire OS Login / SSH keys the same way your existing pipeline does.

## Dev: compose + local build (laptop — **not** the GCP prod VM)

Use [`docker-compose.yml`](docker-compose.yml) when you want to **`docker compose build`** on your **machine** with a full repo clone — **not** when using Cloud Build + Artifact Registry for prod.

```bash
git clone https://github.com/YOUR_ORG/LTX-2.git && cd LTX-2
cp deploy/.env.example deploy/.env
# edit deploy/.env — omit or override LTX_DOCKER_IMAGE; default image tag is ltx-api:local
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

For **production on GCP**, use **§5** + [`docker-compose.gcp.yml`](docker-compose.gcp.yml) (pull from Artifact Registry).

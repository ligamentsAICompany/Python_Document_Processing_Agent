# Document Processing Agent

Stateless **FastAPI** service: index documents with [PageIndex](https://github.com/VectifyAI/PageIndex), store artifacts in **GCS**, and answer questions via the v1 platform API. There is **no custom web UI** — use [Swagger `/docs`](#access-urls) or call the API from your orchestrator.

Supported uploads: PDF, MD, DOCX, Excel, CSV (converted to Markdown/PDF before indexing).

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| Python 3.11+ | Local runs; Docker image uses 3.12 |
| [Gemini API key](https://aistudio.google.com/apikey) or OpenAI key | Default provider is Gemini |
| PageIndex repo | Cloned locally for dev; baked into Docker image for deploy |
| GCP (optional locally, required for GCS dedup) | Project `ligaments-portal`, bucket `rocket_uploaded_files` |

**PageIndex (local only):**

```bash
git clone https://github.com/VectifyAI/PageIndex.git PageIndex
pip install -r requirements-pageindex.txt
```

Do **not** run `pip install -r PageIndex/requirements.txt` — it pins `python-dotenv==1.2.2`, which conflicts with `litellm`. Use `requirements-pageindex.txt` instead.

**GCP CLI (Cloud Run / GCR deploys):**

```bash
gcloud auth login
gcloud config set project ligaments-portal
gcloud auth application-default login
gcloud auth application-default set-quota-project ligaments-portal
gcloud auth configure-docker
```

---

## Configuration

Copy `.env.example` to `.env` for local development, or set the same variables on Cloud Run.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | No | `gemini` | `gemini` or `openai` |
| `GEMINI_API_KEY` | Yes (if Gemini) | — | [AI Studio](https://aistudio.google.com/apikey) key |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Chat + PageIndex (LiteLLM) model |
| `OPENAI_API_KEY` | Yes (if OpenAI) | — | When `LLM_PROVIDER=openai` |
| `OPENAI_MODEL` | No | `gpt-4o` | When using OpenAI |
| `GOOGLE_APPLICATION_CREDENTIALS` | Local GCS | — | Path to service account JSON (see below) |
| `GCP_PROJECT_ID` | No | `ligaments-portal` | GCP project for GCS client |
| `GCS_BUCKET` | No | `rocket_uploaded_files` | Upload + index storage |
| `GCS_LOCATION` | No | auto | Bucket region if creating bucket |
| `PAGEINDEX_REPO` | No | `./PageIndex` | Path to PageIndex clone |
| `DATA_DIR` | No | `./data` | Local temp uploads/indexes |
| `MAX_UPLOAD_MB` | No | `50` | Attachment size limit |
| `SERVICE_API_KEY` | No | empty | If set, v1 routes require `Authorization: Bearer …` |

**GCS service account (local):** place `ligaments-portal-9eaf283845e0.json` in the project root (gitignored). It maps to `bucket-access@ligaments-portal.iam.gserviceaccount.com`. Set in `.env`:

```env
GOOGLE_APPLICATION_CREDENTIALS=./ligaments-portal-9eaf283845e0.json
```

**Never** commit or `COPY` this JSON into a Docker image. Cloud Run uses the same identity via [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) and the runtime service account (see [Cloud Run](#3-gcp-cloud-run-recommended)).

---

## Deployment options

### 1. Local — Python (development)

Best for day-to-day development with hot reload.

```bash
cd Python_Document_Processing_Agent
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # edit GEMINI_API_KEY and GCS paths
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **URL:** http://127.0.0.1:8000  
- **API docs:** http://127.0.0.1:8000/docs  
- **Health:** http://127.0.0.1:8000/api/health  

Without GCS credentials the service still starts; GCS-dependent features stay degraded until credentials are configured.

---

### 2. Local — Docker

Run the same container image as production on your machine (no Cloud Run).

**Build:**

```bash
docker build -t docs-processing-agent:local -f Dockerfile .
```

**Run (GCS via mounted key file):**

```bash
docker run --rm -p 8080:8080 \
  -e GEMINI_API_KEY="your-key" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/sa.json \
  -e GCP_PROJECT_ID=ligaments-portal \
  -e GCS_BUCKET=rocket_uploaded_files \
  -v "$(pwd)/ligaments-portal-9eaf283845e0.json:/secrets/sa.json:ro" \
  docs-processing-agent:local
```

**Run (no GCS — LLM/index only, GCS warnings in logs):**

```bash
docker run --rm -p 8080:8080 \
  -e GEMINI_API_KEY="your-key" \
  docs-processing-agent:local
```

- **URL:** http://127.0.0.1:8080  
- **Health:** http://127.0.0.1:8080/api/health  

PageIndex is cloned inside the image at `/app/PageIndex`; no volume mount needed.

---

### 3. GCP Cloud Run (recommended)

Production deployment: image in **GCR**, service on **Cloud Run** (`us-central1`), GCS via service account **without** embedding keys in the image.

| Setting | Value |
|---------|--------|
| Project | `ligaments-portal` |
| Region | `us-central1` |
| Service | `docs-processing-agent-01` |
| Image | `gcr.io/ligaments-portal/docs-processing-agent-01:latest` |
| Runtime SA | `bucket-access@ligaments-portal.iam.gserviceaccount.com` |
| Public URL | https://docs-processing-agent-01-489651394276.us-central1.run.app |

#### Option A — One command (build + push + deploy)

```bash
export GEMINI_API_KEY="your-key"
chmod +x scripts/deploy_cloud_run.sh
./scripts/deploy_cloud_run.sh
```

Optional overrides: `GCP_PROJECT_ID`, `CLOUD_RUN_REGION`.

#### Option B — Manual steps

**Step 1 — Build and push (linux/amd64 for Cloud Run):**

```bash
docker buildx build --platform linux/amd64 \
  -t gcr.io/ligaments-portal/docs-processing-agent-01:latest \
  -f Dockerfile --push .
```

**Step 2 — Deploy:**

```bash
export GEMINI_API_KEY="your-key"

gcloud run deploy docs-processing-agent-01 \
  --image=gcr.io/ligaments-portal/docs-processing-agent-01:latest \
  --platform=managed \
  --region=us-central1 \
  --project=ligaments-portal \
  --service-account=bucket-access@ligaments-portal.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=ligaments-portal,GCS_BUCKET=rocket_uploaded_files,PAGEINDEX_REPO=/app/PageIndex,DATA_DIR=/tmp/data,LLM_PROVIDER=gemini,GEMINI_API_KEY=${GEMINI_API_KEY}"
```

#### Option C — Deploy new image only (skip rebuild)

After an image is already in GCR:

```bash
gcloud run deploy docs-processing-agent-01 \
  --image=gcr.io/ligaments-portal/docs-processing-agent-01:latest \
  --region=us-central1 \
  --project=ligaments-portal
```

#### Option D — Update env vars / secrets without rebuilding

```bash
# Add or change Gemini key
gcloud run services update docs-processing-agent-01 \
  --region=us-central1 \
  --project=ligaments-portal \
  --update-env-vars="GEMINI_API_KEY=your-key"

# Or mount from Secret Manager (create secret first)
gcloud run services update docs-processing-agent-01 \
  --region=us-central1 \
  --project=ligaments-portal \
  --set-secrets="GEMINI_API_KEY=your-secret-name:latest"
```

#### Verify deployment

```bash
curl -s "https://docs-processing-agent-01-489651394276.us-central1.run.app/api/health" | python3 -m json.tool
```

Expect `"gcs_ready": true` when the runtime service account can access `rocket_uploaded_files`.

---

### 4. GCS bucket setup (one-time)

Creates `rocket_uploaded_files` if it does not exist (uses the same credentials as the app).

**Local (with service account JSON):**

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/ligaments-portal-9eaf283845e0.json"
python scripts/ensure_gcs_bucket.py
```

**Cloud Run:** bucket check/create runs automatically on service startup (`lifespan` in `app/main.py`).

---

### 5. Other GCP targets (not scripted)

The repo ships a `Dockerfile` only; no Terraform or GKE manifests. You can reuse the same image elsewhere:

| Target | Approach |
|--------|----------|
| **GKE** | Push image to GCR/Artifact Registry; deploy Deployment with env vars above; attach `bucket-access@ligaments-portal.iam.gserviceaccount.com` via Workload Identity |
| **Compute Engine / VM** | `docker run` as in [§2](#2-local--docker); mount SA JSON or use VM service account |
| **Cloud Build** | Trigger `docker buildx build --push` from your pipeline, then `gcloud run deploy` |

Use the same environment variables and service account permissions as Cloud Run.

---

## Access URLs

| Environment | Base URL | Swagger | Health |
|-------------|----------|---------|--------|
| Local (uvicorn) | http://127.0.0.1:8000 | `/docs` | `/api/health` |
| Local (Docker) | http://127.0.0.1:8080 | `/docs` | `/api/health` |
| Cloud Run | https://docs-processing-agent-01-489651394276.us-central1.run.app | `/docs` | `/api/health` |

Root `/` returns JSON service metadata (not a UI).

---

## API (v1)

All v1 routes are under `/api/v1`. Send header **`X-Project-Id`** on every v1 request. If `SERVICE_API_KEY` is set, also send **`Authorization: Bearer <key>`**.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Legacy health (PageIndex + GCS readiness) |
| GET | `/api/v1/health` | v1 health (LLM + PageIndex + bucket name) |
| GET | `/api/v1/capabilities` | Supported formats and endpoints |
| POST | `/api/v1/documents/index` | Index document (GCS / URL / inline sources) |
| POST | `/api/v1/documents/process` | Q&A over an existing index |

OpenAPI examples: `/docs` on any running instance.

Platform contract details: `document-processing-agent.txt`.

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| Docker build `COPY static` failed | Removed — there is no `static/` UI in this repo |
| GCS `403` / `gcs_ready: false` on Cloud Run | Service must use `bucket-access@ligaments-portal.iam.gserviceaccount.com`, not the default compute SA |
| `GEMINI_API_KEY is not set` | Set in `.env` locally or Cloud Run env / Secret Manager |
| PageIndex not found locally | `git clone` into `./PageIndex` and set `PAGEINDEX_REPO=./PageIndex` |
| Slow indexing | Normal; PageIndex + summaries can take several minutes per document |

---

## Notes

- **DOCX / Excel / CSV** are converted to Markdown, then indexed.
- **PDF / MD** are indexed directly.
- Service account JSON files (`ligaments-portal*.json`) are gitignored and excluded from Docker context via `.dockerignore`.
- Indexing is LLM-heavy (PageIndex build + retrieval); plan Cloud Run **memory** and **timeout** if you hit limits on large documents.

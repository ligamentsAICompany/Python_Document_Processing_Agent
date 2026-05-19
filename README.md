# Document Processing Agent

Upload a document (PDF, MD, DOCX, Excel, CSV), build a **PageIndex** tree (self-hosted OSS), then chat with grounded answers via tree search + retrieval.

## Prerequisites

- Python 3.11+
- [OpenAI API key](https://platform.openai.com/) (`gpt-4o`)
- Clone [PageIndex](https://github.com/VectifyAI/PageIndex) into `./PageIndex`

```bash
git clone https://github.com/VectifyAI/PageIndex.git PageIndex
pip install -r requirements-pageindex.txt
```

Do **not** run `pip install -r PageIndex/requirements.txt` — it pins `python-dotenv==1.2.2`, which conflicts with `litellm` (needs `1.0.1`). Use `requirements-pageindex.txt` instead.

## Setup

```bash
cd Python_Document_Processing_Agent
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
# (includes litellm for PageIndex — same Python env as uvicorn)
copy .env.example .env   # set GEMINI_API_KEY (https://aistudio.google.com/apikey)
```

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health + PageIndex presence |
| POST | `/api/session` | Create session (one document per session) |
| POST | `/api/session/{id}/upload` | Upload file (max 50 MB) |
| GET | `/api/session/{id}` | Indexing status |
| POST | `/api/session/{id}/chat` | SSE chat (only when `ready`) |

## GCS (local)

Place `ligaments-portal-9eaf283845e0.json` in the project root (gitignored). It uses service account `bucket-access@ligaments-portal.iam.gserviceaccount.com`.

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/ligaments-portal-9eaf283845e0.json"
export GCP_PROJECT_ID=ligaments-portal
export GCS_BUCKET=rocket_uploaded_files
export GEMINI_API_KEY=your-key
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Deploy (Cloud Run)

Do **not** bake the JSON key into the Docker image. Cloud Run uses the same `bucket-access` service account via metadata (ADC).

```bash
export GEMINI_API_KEY=your-key   # required for LLM
chmod +x scripts/deploy_cloud_run.sh
./scripts/deploy_cloud_run.sh
```

Or manually:

```bash
docker buildx build --platform linux/amd64 -t gcr.io/ligaments-portal/docs-processing-agent-01:latest -f Dockerfile --push .

gcloud run deploy docs-processing-agent-01 \
  --image=gcr.io/ligaments-portal/docs-processing-agent-01:latest \
  --platform=managed --region=us-central1 --project=ligaments-portal \
  --service-account=bucket-access@ligaments-portal.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=ligaments-portal,GCS_BUCKET=rocket_uploaded_files,PAGEINDEX_REPO=/app/PageIndex,DATA_DIR=/tmp/data,LLM_PROVIDER=gemini,GEMINI_API_KEY=${GEMINI_API_KEY}"
```

## Notes

- **DOCX / Excel / CSV** are converted to Markdown, then indexed by PageIndex.
- **PDF / MD** are indexed directly.
- Indexing can take several minutes and uses many OpenAI calls (PageIndex build + summaries).

#!/usr/bin/env bash
# Build, push, and deploy docs-processing-agent-01 to Cloud Run with GCS (bucket-access SA).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROJECT="${GCP_PROJECT_ID:-ligaments-portal}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.1-flash-lite}"
SERVICE="docs-processing-agent-01"
IMAGE="gcr.io/${PROJECT}/${SERVICE}:latest"
# Same SA as ligaments-portal-*.json used for local GCS access
GCS_SA="bucket-access@${PROJECT}.iam.gserviceaccount.com"

ENV_VARS="GCP_PROJECT_ID=${PROJECT},GCS_BUCKET=rocket_uploaded_files,PAGEINDEX_REPO=/app/PageIndex,DATA_DIR=/tmp/data,LLM_PROVIDER=gemini,GEMINI_MODEL=${GEMINI_MODEL}"
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  ENV_VARS="${ENV_VARS},GEMINI_API_KEY=${GEMINI_API_KEY}"
fi
if [[ -n "${SERVICE_API_KEY:-}" ]]; then
  ENV_VARS="${ENV_VARS},SERVICE_API_KEY=${SERVICE_API_KEY}"
fi

echo "==> Building and pushing ${IMAGE}"
docker buildx build --platform linux/amd64 -t "${IMAGE}" -f Dockerfile --push .

echo "==> Deploying ${SERVICE} (${REGION}) with service account ${GCS_SA}"
DEPLOY_ARGS=(
  run deploy "${SERVICE}"
  --image="${IMAGE}"
  --platform=managed
  --region="${REGION}"
  --project="${PROJECT}"
  --service-account="${GCS_SA}"
  --allow-unauthenticated
  --set-env-vars="${ENV_VARS}"
)

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "WARN: GEMINI_API_KEY is not set; indexing/Q&A will fail until you set it on the service."
fi

gcloud "${DEPLOY_ARGS[@]}"

URL="$(gcloud run services describe "${SERVICE}" --region="${REGION}" --project="${PROJECT}" --format='value(status.url)')"
echo "Deployed: ${URL}"
echo "Health: ${URL}/api/v1/health"

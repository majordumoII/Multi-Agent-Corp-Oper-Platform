#!/usr/bin/env bash
set -euo pipefail

# Script: deploy-orchestrator.sh
# Purpose: Deploy the orchestrator service to Cloud Run and grant Project 2's
#          RAG service invoker access for this service's identity to call.
# Usage:   ./infra/scripts/deploy-orchestrator.sh
#
# Prerequisites:
#   - gcloud CLI authenticated with appropriate permissions
#   - Project 2 (Enterprise-RAG-Security-Guardrails) already deployed to Cloud Run
#   - .env file populated (RAG_SERVICE_URL should point at Project 2's Cloud Run URL)

PROJECT_ID=$(gcloud config get project)
SERVICE_NAME="orchestrator"
LOCATION="${LOCATION:-us-east1}"
RAG_SERVICE_NAME="${RAG_SERVICE_NAME:-rag-security-guardrails}"

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example and fill it in."
    exit 1
fi
# shellcheck disable=SC1091
source .env

echo "Project:  $PROJECT_ID"
echo "Service:  $SERVICE_NAME"
echo "Region:   $LOCATION"
echo ""

echo "=== Enabling required APIs ==="
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

echo "=== Deploying $SERVICE_NAME ==="
gcloud run deploy "$SERVICE_NAME" \
    --source=. \
    --dockerfile=docker/orchestrator.Dockerfile \
    --region="$LOCATION" \
    --no-allow-unauthenticated \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},LOCAL_DEV=false,RAG_SERVICE_URL=${RAG_SERVICE_URL},RAG_SERVICE_AUDIENCE=${RAG_SERVICE_AUDIENCE:-$RAG_SERVICE_URL},VERTEX_PROJECT_ID=${VERTEX_PROJECT_ID:-$PROJECT_ID},VERTEX_LOCATION=${VERTEX_LOCATION:-us-east1},GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.0-flash}" \
    --memory=512Mi \
    --min-instances=0 \
    --max-instances=10

ORCHESTRATOR_SA=$(gcloud run services describe "$SERVICE_NAME" --region="$LOCATION" --format='value(spec.template.spec.serviceAccountName)')
echo ""
echo "=== Granting $SERVICE_NAME's service account ($ORCHESTRATOR_SA) invoker on $RAG_SERVICE_NAME ==="
gcloud run services add-iam-policy-binding "$RAG_SERVICE_NAME" \
    --region="$LOCATION" \
    --member="serviceAccount:${ORCHESTRATOR_SA}" \
    --role="roles/run.invoker"

echo ""
echo "=== Done ==="
echo "Orchestrator URL: $(gcloud run services describe "$SERVICE_NAME" --region="$LOCATION" --format='value(status.url)')"
echo "Next: run deploy-api-gateway.sh, which grants ITS service account invoker on this service."

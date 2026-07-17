#!/usr/bin/env bash
set -euo pipefail

# Script: deploy-api-gateway.sh
# Purpose: Deploy the api_gateway service to Cloud Run and grant it invoker
#          access on the orchestrator service (service-to-service OIDC auth).
# Usage:   ./infra/scripts/deploy-api-gateway.sh
#
# Prerequisites:
#   - gcloud CLI authenticated with appropriate permissions
#   - orchestrator already deployed (run deploy-orchestrator.sh first)
#   - .env file populated

PROJECT_ID=$(gcloud config get project)
SERVICE_NAME="api-gateway"
LOCATION="${LOCATION:-us-east1}"
ORCHESTRATOR_SERVICE_NAME="${ORCHESTRATOR_SERVICE_NAME:-orchestrator}"

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example and fill it in."
    exit 1
fi

echo "Project:  $PROJECT_ID"
echo "Service:  $SERVICE_NAME"
echo "Region:   $LOCATION"
echo ""

ORCHESTRATOR_URL=$(gcloud run services describe "$ORCHESTRATOR_SERVICE_NAME" --region="$LOCATION" --format='value(status.url)')
if [ -z "$ORCHESTRATOR_URL" ]; then
    echo "ERROR: could not resolve orchestrator URL. Deploy it first with deploy-orchestrator.sh."
    exit 1
fi
echo "Orchestrator URL: $ORCHESTRATOR_URL"

echo "=== Enabling required APIs ==="
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

echo "=== Deploying $SERVICE_NAME ==="
gcloud run deploy "$SERVICE_NAME" \
    --source=. \
    --dockerfile=docker/api_gateway.Dockerfile \
    --region="$LOCATION" \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},LOCAL_DEV=false,ORCHESTRATOR_URL=${ORCHESTRATOR_URL},ORCHESTRATOR_AUDIENCE=${ORCHESTRATOR_URL}" \
    --memory=512Mi \
    --min-instances=0 \
    --max-instances=10

GATEWAY_SA=$(gcloud run services describe "$SERVICE_NAME" --region="$LOCATION" --format='value(spec.template.spec.serviceAccountName)')
echo ""
echo "=== Granting $SERVICE_NAME's service account ($GATEWAY_SA) invoker on $ORCHESTRATOR_SERVICE_NAME ==="
gcloud run services add-iam-policy-binding "$ORCHESTRATOR_SERVICE_NAME" \
    --region="$LOCATION" \
    --member="serviceAccount:${GATEWAY_SA}" \
    --role="roles/run.invoker"

echo ""
echo "=== Done ==="
echo "API Gateway URL: $(gcloud run services describe "$SERVICE_NAME" --region="$LOCATION" --format='value(status.url)')"
echo ""
echo "NOTE: --allow-unauthenticated is used here for demo reachability only."
echo "Before any production exposure, front this with real auth (see README Phase 5)."

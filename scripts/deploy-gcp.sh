#!/bin/bash
# AKILI Google Cloud Deployment Script
#
# Deploys backend and frontend to Google Cloud Run.
# Requires: gcloud CLI authenticated with appropriate permissions.
#
# Usage:
#   ./scripts/deploy-gcp.sh                    # Deploy both
#   ./scripts/deploy-gcp.sh --api-only         # Deploy backend only
#   ./scripts/deploy-gcp.sh --frontend-only    # Deploy frontend only
#   ./scripts/deploy-gcp.sh --setup            # Initial setup

set -euo pipefail

# Configuration (override with environment variables)
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"
API_SERVICE="${API_SERVICE:-akili-api}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-akili-frontend}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi

    if [ -z "$PROJECT_ID" ]; then
        PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
        if [ -z "$PROJECT_ID" ]; then
            log_error "No project ID set. Run: gcloud config set project YOUR_PROJECT_ID"
            exit 1
        fi
    fi

    log_info "Using project: $PROJECT_ID"
    log_info "Using region: $REGION"
}

# Initial setup
setup() {
    log_info "Setting up Google Cloud resources..."

    # Enable required APIs
    log_info "Enabling Cloud Run, Cloud Build, and Secret Manager APIs..."
    gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

    # Create secrets (user will need to set values)
    log_info "Creating secrets (you'll need to set values manually)..."

    for secret in GOOGLE_API_KEY DATABASE_URL FIREBASE_PROJECT_ID; do
        if ! gcloud secrets describe "$secret" &>/dev/null; then
            echo "placeholder" | gcloud secrets create "$secret" --data-file=-
            log_warn "Created secret '$secret' with placeholder. Update with:"
            log_warn "  echo 'YOUR_VALUE' | gcloud secrets versions add $secret --data-file=-"
        else
            log_info "Secret '$secret' already exists"
        fi
    done

    log_info "Setup complete! Next steps:"
    echo "  1. Set secret values:"
    echo "     echo 'your-gemini-key' | gcloud secrets versions add GOOGLE_API_KEY --data-file=-"
    echo "     echo 'postgresql://...' | gcloud secrets versions add DATABASE_URL --data-file=-"
    echo "     echo 'your-firebase-project' | gcloud secrets versions add FIREBASE_PROJECT_ID --data-file=-"
    echo ""
    echo "  2. Deploy: ./scripts/deploy-gcp.sh"
}

# Deploy backend API
deploy_api() {
    log_info "Deploying backend API to Cloud Run..."

    # Build and push image
    log_info "Building Docker image..."
    gcloud builds submit --tag "gcr.io/$PROJECT_ID/$API_SERVICE" .

    # Deploy to Cloud Run
    log_info "Deploying to Cloud Run..."
    gcloud run deploy "$API_SERVICE" \
        --image "gcr.io/$PROJECT_ID/$API_SERVICE" \
        --region "$REGION" \
        --platform managed \
        --allow-unauthenticated \
        --memory 1Gi \
        --cpu 1 \
        --timeout 300 \
        --concurrency 80 \
        --min-instances 0 \
        --max-instances 10 \
        --set-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest,DATABASE_URL=DATABASE_URL:latest,FIREBASE_PROJECT_ID=FIREBASE_PROJECT_ID:latest" \
        --set-env-vars "AKILI_REQUIRE_AUTH=1,AKILI_RATE_LIMIT=1"

    # Get URL
    API_URL=$(gcloud run services describe "$API_SERVICE" --region "$REGION" --format='value(status.url)')
    log_info "Backend deployed at: $API_URL"
    echo "$API_URL" > .api-url
}

# Deploy frontend
deploy_frontend() {
    log_info "Deploying frontend to Cloud Run..."

    # Get API URL
    if [ -f .api-url ]; then
        API_URL=$(cat .api-url)
    else
        API_URL=$(gcloud run services describe "$API_SERVICE" --region "$REGION" --format='value(status.url)' 2>/dev/null || echo "")
    fi

    if [ -z "$API_URL" ]; then
        log_error "API URL not found. Deploy API first or set manually."
        exit 1
    fi

    log_info "Using API URL: $API_URL"

    # Build with environment variables
    log_info "Building frontend Docker image..."
    cd frontend

    # Read Firebase config from environment or .env
    if [ -f "../.env" ]; then
        source "../.env"
    fi

    gcloud builds submit \
        --tag "gcr.io/$PROJECT_ID/$FRONTEND_SERVICE" \
        --file Dockerfile.prod \
        --substitutions "_VITE_API_URL=$API_URL,_VITE_FIREBASE_API_KEY=${VITE_FIREBASE_API_KEY:-},_VITE_FIREBASE_AUTH_DOMAIN=${VITE_FIREBASE_AUTH_DOMAIN:-},_VITE_FIREBASE_PROJECT_ID=${VITE_FIREBASE_PROJECT_ID:-}"

    cd ..

    # Deploy to Cloud Run
    log_info "Deploying frontend to Cloud Run..."
    gcloud run deploy "$FRONTEND_SERVICE" \
        --image "gcr.io/$PROJECT_ID/$FRONTEND_SERVICE" \
        --region "$REGION" \
        --platform managed \
        --allow-unauthenticated \
        --memory 256Mi \
        --cpu 1 \
        --concurrency 200 \
        --min-instances 0 \
        --max-instances 5

    FRONTEND_URL=$(gcloud run services describe "$FRONTEND_SERVICE" --region "$REGION" --format='value(status.url)')
    log_info "Frontend deployed at: $FRONTEND_URL"
}

# Main
main() {
    check_prerequisites

    case "${1:-}" in
        --setup)
            setup
            ;;
        --api-only)
            deploy_api
            ;;
        --frontend-only)
            deploy_frontend
            ;;
        *)
            deploy_api
            deploy_frontend
            log_info "Deployment complete!"
            echo ""
            echo "Services:"
            echo "  API:      $(cat .api-url 2>/dev/null || gcloud run services describe $API_SERVICE --region $REGION --format='value(status.url)')"
            echo "  Frontend: $(gcloud run services describe $FRONTEND_SERVICE --region $REGION --format='value(status.url)')"
            ;;
    esac
}

main "$@"

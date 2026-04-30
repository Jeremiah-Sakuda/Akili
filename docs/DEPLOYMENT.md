# AKILI Deployment Guide

This guide covers deploying AKILI to Google Cloud Platform using Cloud Run.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Google Cloud Platform                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────────────────┐  │
│  │  Cloud Run       │         │  Cloud Run                   │  │
│  │  (Frontend)      │ ──API──▶│  (Backend API)               │  │
│  │                  │         │                              │  │
│  │  nginx + React   │         │  FastAPI + Gunicorn          │  │
│  │  Static SPA      │         │  Gemini API calls            │  │
│  └────────┬─────────┘         └──────────────┬───────────────┘  │
│           │                                   │                  │
│           │                                   ▼                  │
│           │                   ┌──────────────────────────────┐  │
│           │                   │  Secret Manager              │  │
│           │                   │  - GOOGLE_API_KEY            │  │
│           │                   │  - DATABASE_URL              │  │
│           │                   │  - FIREBASE_PROJECT_ID       │  │
│           │                   └──────────────────────────────┘  │
│           │                                   │                  │
│           ▼                                   ▼                  │
│  ┌──────────────────┐         ┌──────────────────────────────┐  │
│  │  Firebase Auth   │         │  Cloud SQL / Supabase        │  │
│  │  (Google Sign-in)│         │  (PostgreSQL)                │  │
│  └──────────────────┘         └──────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Firebase Project** for authentication
4. **PostgreSQL Database** (Cloud SQL or Supabase)
5. **Gemini API Key** from Google AI Studio

## Quick Start

### 1. Set up Google Cloud project

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Run initial setup (enables APIs, creates secrets)
./scripts/deploy-gcp.sh --setup
```

### 2. Configure secrets

```bash
# Gemini API key (from https://makersuite.google.com/app/apikey)
echo 'your-gemini-api-key' | gcloud secrets versions add GOOGLE_API_KEY --data-file=-

# PostgreSQL connection string
echo 'postgresql://user:pass@host:5432/akili' | gcloud secrets versions add DATABASE_URL --data-file=-

# Firebase project ID
echo 'your-firebase-project-id' | gcloud secrets versions add FIREBASE_PROJECT_ID --data-file=-
```

### 3. Configure Firebase environment

Create a `.env` file with your Firebase config (for frontend build):

```bash
VITE_FIREBASE_API_KEY=your-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abc123
```

### 4. Deploy

```bash
# Deploy both backend and frontend
./scripts/deploy-gcp.sh

# Or deploy individually
./scripts/deploy-gcp.sh --api-only
./scripts/deploy-gcp.sh --frontend-only
```

## Manual Deployment

### Backend (API)

```bash
# Build and push Docker image
gcloud builds submit --tag gcr.io/$PROJECT_ID/akili-api .

# Deploy to Cloud Run
gcloud run deploy akili-api \
  --image gcr.io/$PROJECT_ID/akili-api \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --timeout 300 \
  --set-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest,DATABASE_URL=DATABASE_URL:latest,FIREBASE_PROJECT_ID=FIREBASE_PROJECT_ID:latest" \
  --set-env-vars "AKILI_REQUIRE_AUTH=1"
```

### Frontend

```bash
cd frontend

# Build with API URL
gcloud builds submit \
  --tag gcr.io/$PROJECT_ID/akili-frontend \
  --file Dockerfile.prod \
  --substitutions "_VITE_API_URL=https://akili-api-xxx.run.app"

# Deploy
gcloud run deploy akili-frontend \
  --image gcr.io/$PROJECT_ID/akili-frontend \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 256Mi
```

## CI/CD with Cloud Build

The `cloudbuild.yaml` file configures automatic builds on push. To set up:

1. **Connect your repository** in Cloud Build:
   ```
   Console → Cloud Build → Triggers → Connect Repository
   ```

2. **Create a trigger**:
   ```bash
   gcloud builds triggers create github \
     --repo-name=akili \
     --repo-owner=YOUR_USERNAME \
     --branch-pattern="^main$" \
     --build-config=cloudbuild.yaml \
     --substitutions="_REGION=us-central1,_VITE_API_URL=https://akili-api-xxx.run.app"
   ```

3. **Add substitution variables** for Firebase config in the trigger settings.

## Database Setup

### Option A: Cloud SQL (Google-managed)

```bash
# Create instance
gcloud sql instances create akili-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# Create database
gcloud sql databases create akili --instance=akili-db

# Create user
gcloud sql users create akili --instance=akili-db --password=YOUR_PASSWORD

# Get connection string
# Format: postgresql://akili:PASSWORD@/akili?host=/cloudsql/PROJECT:REGION:akili-db
```

### Option B: Supabase (recommended for simplicity)

1. Create a project at [supabase.com](https://supabase.com)
2. Copy the connection string from Settings → Database
3. Add to Secret Manager as `DATABASE_URL`

## Environment Variables

### Backend

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_API_KEY` | Gemini API key | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `FIREBASE_PROJECT_ID` | Firebase project for auth | Yes |
| `AKILI_REQUIRE_AUTH` | Enable authentication (1/0) | Yes (prod) |
| `AKILI_RATE_LIMIT` | Enable rate limiting (1/0) | Yes (prod) |
| `AKILI_FREE_TIER_DOCS` | Max docs per user (default: 5) | No |
| `AKILI_FREE_TIER_QUERIES` | Max queries per user (default: 50) | No |
| `AKILI_GEMINI_MODEL` | Gemini model (default: gemini-3-flash) | No |

### Frontend (build-time)

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API URL |
| `VITE_FIREBASE_*` | Firebase configuration |

## Custom Domain

1. **Map domain in Cloud Run**:
   ```bash
   gcloud run domain-mappings create \
     --service akili-frontend \
     --domain akili.app \
     --region us-central1
   ```

2. **Add DNS records** as shown in the console output.

3. **Update CORS** in backend to allow the custom domain.

## Monitoring

### View logs

```bash
# Backend logs
gcloud run logs read akili-api --region us-central1

# Frontend logs
gcloud run logs read akili-frontend --region us-central1
```

### Set up alerts

```bash
# Create alert for high error rate
gcloud alpha monitoring policies create \
  --notification-channels=YOUR_CHANNEL \
  --condition-filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_count" AND metric.labels.response_code_class="5xx"'
```

## Cost Optimization

Cloud Run charges per-request and per-second of compute. To minimize costs:

1. **Set min-instances=0** to scale to zero when idle
2. **Use appropriate memory** (backend: 1Gi, frontend: 256Mi)
3. **Enable CPU throttling** with `--cpu-throttling`
4. **Use Artifact Registry** instead of Container Registry for lower storage costs

Estimated costs for low traffic (~1000 requests/day):
- Cloud Run: ~$5-10/month
- Cloud SQL (if used): ~$10-20/month
- Secret Manager: ~$0.10/month

## Troubleshooting

### "Service unavailable" on first request

Cloud Run instances scale to zero. First request after idle triggers cold start (~2-5 seconds).

**Fix**: Set `--min-instances=1` for critical services.

### "CORS error" in browser

Backend CORS config doesn't include frontend domain.

**Fix**: Add frontend URL to `AKILI_CORS_ORIGINS` environment variable.

### "Database connection error"

Cloud SQL requires special connection handling.

**Fix**: Use Cloud SQL Proxy or add `--add-cloudsql-instances` flag to Cloud Run.

### "Gemini API error"

API key may be invalid or quota exceeded.

**Fix**: Verify key at https://makersuite.google.com and check quotas.

# Akili Frontend

React + TypeScript + Vite UI for the Akili verification workspace. Connects to the FastAPI backend via proxy in dev.

## Setup

```bash
npm install
```

## Dev

Start the API first (from repo root: `akili-serve` or `uvicorn akili.api.app:app --port 8000`), then:

```bash
npm run dev
```

Open http://localhost:3000. The Vite dev server proxies `/api/*` to the backend.

## Build

```bash
npm run build
```

Output is in `dist/`. Serve with any static host or mount under the API.

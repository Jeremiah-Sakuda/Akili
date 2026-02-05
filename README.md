# Akili

**The Reasoning Control Plane for Mission-Critical Engineering**

Akili is a deterministic verification layer for technical documentation. While LLMs excel at fluent reasoning, they fail in high-stakes engineering environments where "mostly right" is $1M worth of wrong. Akili constrains Gemini's multimodal perception within a strict structural framework, turning dense PDFs, pinout tables, and schematics into **auditable, coordinate-grounded truth**.

---

## How It Works

| Pillar | Description |
|--------|-------------|
| **Structural Canonicalization** | Raw Gemini perception → typed objects (units, bijections, grids). Ambiguous data rejected at the source. |
| **Coordinate-Level Grounding** | Every answer mapped to precise `(x, y)` coordinates. No "citations"—only proof. |
| **Deterministic Refusal** | If a specification cannot be mathematically proven from the canonical structure, Akili refuses to answer. |

Akili doesn't just ask Gemini for an answer; it **forces Gemini to show its work** against a verifiable map of the truth.

---

## Proposed Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Runtime** | Python 3.11+ | Native fit for Gemini SDK, PDF/vision pipelines, and symbolic validation. |
| **LLM & Vision** | Google Gemini API (multimodal) | PDFs, tables, schematics as images/chunks; structured extraction. |
| **Typed Canonical Model** | Pydantic v2 | Units, bijections, grids as validated types; reject invalid shapes at ingestion. |
| **Document Processing** | PyMuPDF, pdf2image | Extract pages, layout, bounding boxes; feed regions to Gemini with coordinates. |
| **Coordinate Store** | SQLite (MVP) → PostgreSQL | Persist canonical objects with `(x, y)` and page/doc provenance. |
| **Verification / Proof** | Rule-based + optional SMT (Z3) | Check that answers follow from canonical facts; deterministic refuse. |
| **API** | FastAPI | Ingest documents, submit queries, return coordinate-grounded answers or REFUSE. |
| **Optional Viewer** | Svelte/React + PDF.js | Overlay proven answers on source PDF for judge demos. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INGESTION PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  PDF / Schematic  →  Chunk + Layout  →  Gemini Multimodal  →  Canonicalize  │
│       (raw)            (pages, bbox)      (extract facts)       (typed only) │
│                                                                              │
│  Reject: low confidence, ambiguous, or non-typed extractions                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CANONICAL TRUTH STORE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Units (with units of measure, (x,y) origin)                               │
│  • Bijections (A ↔ B with coordinate ranges)                                 │
│  • Grids (table/schematic cells with (row,col) → (x,y))                      │
│  All entries: doc_id, page, bbox, provenance                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            QUERY & VERIFICATION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  User Question  →  Retrieve relevant canonical facts  →  Proof check        │
│                         (by content + coordinates)         (derivable?)      │
│                                        │                                    │
│                    ┌───────────────────┴───────────────────┐                 │
│                    ▼                                       ▼                 │
│              [Provable]                            [Not provable]            │
│              Answer + (x,y) proof                   REFUSE (deterministic)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

1. **Ingest**: PDF → split into pages/regions with bounding boxes → send to Gemini with “extract typed facts and their coordinates” → parse into `Unit`, `Bijection`, `Grid` → validate → persist only if valid.
2. **Store**: Canonical objects live in DB with `(doc_id, page, x, y, ...)`. No free-text “beliefs”—only structural facts.
3. **Query**: User asks a question → system retrieves candidate canonical facts (by semantic + spatial relevance) → verification layer checks if the answer is **derivable** from those facts → return answer + coordinate proof, or **REFUSE**.

---

## Project Structure

```
akili/
├── .github/
│   └── workflows/
│       ├── ci.yml      # Lint, typecheck, test (backend + frontend)
│       └── deploy.yml  # Deploy frontend to Firebase Hosting
├── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── UX-DESIGN-BRIEF.md
│   └── UI-SPEC.md
├── frontend/                 # React + TypeScript + Vite UI
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── api.ts
│   │   └── types.ts
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── src/
│   └── akili/
│       ├── canonical/        # Unit, Bijection, Grid
│       ├── ingest/           # PDF → Gemini → canonicalize
│       ├── store/            # SQLite persistence
│       ├── verify/           # Proof + REFUSE
│       └── api/              # FastAPI app
├── tests/
├── pyproject.toml
└── requirements.txt
```

---

## Running with Docker

One-command run for API + frontend with a persistent SQLite store.

1. **Create `.env`** from the example and set your Gemini key:
   ```bash
   cp .env.example .env
   # Edit .env and set GOOGLE_API_KEY=your_key
   ```
2. **Build and start** (from repo root):
   ```bash
   docker compose up --build
   ```
3. Open **http://localhost:3001** for the UI (port 3001 to avoid conflict with other apps on 3000). API docs: **http://localhost:8000/docs**; the UI proxies `/api` to the API inside Docker.

**Notes:**
- The SQLite DB is stored in a Docker volume `akili-data` (path `/data/akili.db` in the API container).
- To stop: `Ctrl+C` then `docker compose down`. Add `-v` to remove the volume and reset the DB.

---

## Getting Started

### Backend (API)

1. **Environment**: From repo root, create and activate a venv, then set `GOOGLE_API_KEY` for Gemini.
   - **Windows (PowerShell):** `python -m venv .venv` then `.\.venv\Scripts\Activate.ps1`
   - **Windows (cmd):** `python -m venv .venv` then `.venv\Scripts\activate.bat`
   - **macOS/Linux:** `python3 -m venv .venv` then `source .venv/bin/activate`
2. **Install**: `pip install -e .`
3. **Run API** (from repo root, with venv active):
   ```bash
   python -m uvicorn akili.api.app:app --reload --host 0.0.0.0 --port 8000
   ```
   Or, if the package is installed: `akili-serve`
4. **Ingest a doc**: `POST /ingest` with PDF (multipart form `file`) → canonical store populated; returns `doc_id`.
5. **Query**: `POST /query` with body `{"doc_id": "<from ingest>", "question": "What is pin 5?"}` → coordinate-grounded answer + proof or REFUSE.
6. **List docs**: `GET /documents`. **Inspect canonical**: `GET /documents/{doc_id}/canonical`.

### UI (frontend)

The React + TypeScript UI lives in `frontend/` and is wired to the API via a Vite proxy.

1. **Install Node.js** if you don’t have it: [nodejs.org](https://nodejs.org/) (LTS). Then `node` and `npm` should be in your PATH.
2. **Start the API** (from repo root, in a first terminal, with venv active):
   ```bash
   python -m uvicorn akili.api.app:app --reload --port 8000
   ```
3. **Start the UI** (in a second terminal, from repo root):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. Open **http://localhost:3000** (or **http://localhost:3001** if using Docker). Upload a PDF, then select a document and ask a question; the right panel shows VERIFIED (answer + proof) or REFUSED.

### Firebase hosting & sign-in

The app can be hosted on Firebase with Google sign-in.

1. **Create a Firebase project** at [console.firebase.google.com](https://console.firebase.google.com). Note your project ID.
2. **Enable Authentication → Sign-in method → Google** in the Firebase Console.
3. **Configure the project**: replace `your-firebase-project-id` in `.firebaserc` with your project ID.
4. **Env**: copy `.env.example` to `.env` in the repo root and fill in `GOOGLE_API_KEY` and the Firebase vars (Project settings → General → Your apps → Web app). Vite loads from the repo root, so one `.env` covers both API and frontend.
5. **Build and deploy** (from repo root):
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   npx firebase deploy
   ```
   The hosted app will be at `https://<project-id>.web.app` (or your custom domain). Unauthenticated users see the login page; after signing in with Google they get the verification workspace.

**If you get "command not found":**
- **API:** Use `python -m uvicorn akili.api.app:app --reload --port 8000` (or `py -m uvicorn ...` on Windows). Run this from the **project root** after activating the venv and running `pip install -e .`.
- **UI:** Run `npm install` and `npm run dev` from inside the `frontend/` folder. If `npm` is not found, install Node.js and ensure it’s on your PATH.

---

## CI/CD

GitHub Actions workflows in `.github/workflows/` provide CI and CD.

### CI (`.github/workflows/ci.yml`)

Runs on every **push** and **pull_request** to `main`, `master`, and `develop`.

| Job | What it does |
|-----|----------------|
| **Backend (Python)** | Matrix: Python 3.11 and 3.12. Installs `.[dev]`, runs **Ruff** (lint + format check), **pytest** with coverage. Optional: uploads coverage to Codecov (Python 3.11 only). |
| **Frontend (Node)** | Node 20. `npm ci` → **ESLint** → **TypeScript** (`tsc --noEmit`) → **Vite build**. Build uses empty Firebase env vars so it works without secrets. |

**Local equivalents:**

- Backend: `pip install -e ".[dev]"` then `ruff check src tests`, `ruff format --check src tests`, `pytest tests -v`
- Frontend: `cd frontend && npm ci && npm run lint && npm run typecheck && npm run build`

### CD (`.github/workflows/deploy.yml`)

Runs on **push to `main`/`master`** and on **workflow_dispatch** (manual run).

1. **Build**: Installs frontend deps, builds with Vite using Firebase env from **secrets**.
2. **Deploy**: Installs Firebase CLI, runs `firebase deploy --only hosting` using `FIREBASE_TOKEN`.

**Required repository secrets** (Settings → Secrets and variables → Actions):

| Secret | Purpose |
|--------|--------|
| `FIREBASE_TOKEN` | CI deploy token from `firebase login:ci`. |
| `VITE_FIREBASE_API_KEY` | Firebase Web app config (same as in `.env` for local). |
| `VITE_FIREBASE_AUTH_DOMAIN` | e.g. `your-project.firebaseapp.com`. |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID (must match `.firebaserc`). |
| `VITE_FIREBASE_STORAGE_BUCKET` | e.g. `your-project.appspot.com`. |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | From Firebase Console. |
| `VITE_FIREBASE_APP_ID` | From Firebase Console. |

Optional: add an **environment** (e.g. `production`) in the repo and protect it; the deploy job uses `environment: production` so you can add approval rules.

### Dependabot (`.github/dependabot.yml`)

Weekly PRs to update **npm** (frontend), **pip** (backend), and **GitHub Actions**. Adjust or remove if you prefer manual updates.

---

## License

TBD.

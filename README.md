# Akili

![CI](https://github.com/jeremytraini/akili/actions/workflows/ci.yml/badge.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Node 20](https://img.shields.io/badge/node-20-green)
![React 19](https://img.shields.io/badge/react-19-61dafb)
![License](https://img.shields.io/badge/license-TBD-lightgrey)

**The Reasoning Control Plane for Mission-Critical Engineering**

> No citations. Only proof.

Akili is a deterministic verification layer for technical documentation. While LLMs generate plausible answers, Akili constrains Gemini's multimodal perception within a strict structural framework — turning dense PDFs, pinout tables, and schematics into **auditable, coordinate-grounded truth**.

Every answer is tied to exact `(x, y)` coordinates on the source document, or the system refuses.

---

## Quick Start

### 1. Backend

```bash
# Clone and set up
git clone https://github.com/jeremytraini/akili.git
cd akili

# Create venv and install
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev,auth,verify]"

# Set your Gemini API key
cp .env.example .env
# Edit .env → set GOOGLE_API_KEY=your_key

# Run API
python -m uvicorn akili.api.app:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### 3. Upload → Query → Verify

1. Upload a technical PDF (datasheet, schematic, spec sheet)
2. Select the document in the sidebar
3. Ask a question: "What is the maximum voltage?"
4. Get a **VERIFIED** answer with proof coordinates — or a clear **REFUSE**

### Docker (alternative)

```bash
cp .env.example .env   # Set GOOGLE_API_KEY
docker compose up --build
# UI: http://localhost:3001  |  API docs: http://localhost:8000/docs
```

---

## How It Works

| Pillar | Description |
|--------|-------------|
| **Structural Canonicalization** | Raw Gemini perception → typed objects (units, bijections, grids). Ambiguous data rejected at the source. |
| **Coordinate-Level Grounding** | Every answer mapped to precise `(x, y)` coordinates. No "citations" — only proof. |
| **Deterministic Refusal** | If a specification cannot be derived from the canonical structure, Akili refuses to answer. |
| **Confidence Scoring** | Three-component confidence (extraction agreement, canonical validation, verification strength) classifies answers as VERIFIED, REVIEW, or REFUSED. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INGESTION PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  PDF / Schematic  →  Page Images  →  Gemini Multimodal  →  Canonicalize    │
│       (raw)          (PyMuPDF)       (extract facts)       (typed only)     │
│                                                                              │
│  Reject: ambiguous, non-typed, or coordinate-less extractions               │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CANONICAL TRUTH STORE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Units (value + unit_of_measure + context + (x,y) origin)                 │
│  • Bijections (A ↔ B with coordinate ranges)                                │
│  • Grids (table/schematic cells with (row,col) → (x,y))                    │
│  • Ranges (min/typ/max with conditions)                                     │
│  • ConditionalUnits (value + condition + derating)                          │
│  All entries: doc_id, page, bbox, provenance                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     QUERY, VERIFICATION & CONFIDENCE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  User Question  →  30-rule verification engine  →  Confidence scoring       │
│                    (priority-ordered registry)                               │
│                            │                                                │
│              ┌─────────────┼─────────────┐                                  │
│              ▼             ▼             ▼                                   │
│         [VERIFIED]    [REVIEW]     [REFUSED]                                │
│         ≥85% conf.   50-85% conf.  <50% conf.                              │
│         Answer +      Answer +      Deterministic                           │
│         proof +       proof +       refusal with                            │
│         confidence    "needs review" reason                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Ingest**: PDF → page images (PyMuPDF 150 DPI) → classify page type → optional consensus dual-pass → Gemini structured extraction → `Unit`, `Bijection`, `Grid`, `Range`, `ConditionalUnit` → detect multi-page tables → Z3 consistency checks → validate → persist.
2. **Store**: Canonical objects in SQLite (dev) or PostgreSQL (prod) with `(doc_id, page, x, y, context, ...)`. No free-text beliefs — only structural facts. Immutable audit log.
3. **Query**: 30 verification rules in priority order → derived query engine (P=V×I, thermal, voltage margin, current budget) → coordinate proof + confidence score → or REFUSE.
4. **Compare**: Cross-document parameter comparison with best-value highlighting.
5. **Review**: REVIEW-tier answers surface for human confirmation/correction.
6. **Learn**: Correction patterns analyzed to detect systematic errors; auto-correction rules built from high-confidence patterns.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, PyMuPDF |
| **LLM & Vision** | Google Gemini 3 API (multimodal) |
| **Database** | SQLite (dev) / PostgreSQL via Supabase (prod) |
| **Verification** | 30-rule engine + derived queries + Z3 constraint solver |
| **Frontend** | React 19, TypeScript 5.8, Vite 6, Tailwind CSS 4 |
| **Auth** | Firebase Authentication (Google sign-in) |
| **CI** | GitHub Actions (Python 3.11/3.12 + Node 20), Ruff + Flake8 + ESLint |
| **Deploy** | Vercel (frontend) + Cloud Run (backend) |

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ingest` | POST | Upload PDF, run ingestion pipeline, populate canonical store |
| `/ingest/stream` | POST | Same with server-sent events for progress tracking |
| `/query` | POST | Submit question → answer + proof + confidence, or REFUSE |
| `/documents` | GET | List ingested documents with canonical object counts |
| `/documents/{doc_id}/canonical` | GET | Inspect canonical objects for a document |
| `/documents/{doc_id}/file` | GET | Download the ingested PDF |
| `/documents/{doc_id}` | DELETE | Remove document and canonical objects |
| `/usage` | GET | Free-tier usage summary (docs and queries) |
| `/corrections` | POST | Submit human correction/confirmation |
| `/corrections/{doc_id}` | GET | List corrections for a document |
| `/compare` | POST | Compare parameters across 2+ documents |
| `/patterns` | GET | Analyze correction patterns |
| `/patterns/suggest` | POST | Suggest auto-correction from learned patterns |
| `/status` | GET | Environment check (API key, DB) |
| `/health` | GET | Health check |

---

## Verification Rules (30)

The rule engine in `src/akili/verify/proof.py` uses a `@rule(priority)` decorator registry. Rules are tried in priority order; the first non-None result wins.

| Priority | Category | Examples |
|----------|----------|----------|
| 100 | Pin lookup | "What is pin 5?" |
| 150–160 | Identification | Part number, description |
| 200–210 | Absolute maximums | Max voltage, max current |
| 300–320 | Operating maximums | Max voltage, current, capacity |
| 400–430 | Operating ranges | Voltage range, temperature, soldering |
| 500–530 | Electrical specs | Power, ESD, leakage, threshold |
| 600–630 | Timing | Clock, propagation delay, rise/fall, setup/hold |
| 700–750 | Physical/package | Type, dimensions, thermal resistance, pin count |
| 800–1000 | Fallback | Recommended conditions, intent matching, label/grid lookup |
| Derived | Computed | Power (P=V×I), thermal, voltage margin, current budget |

---

## Confidence Scoring

```
confidence = {
    "extraction_agreement": 0.0–1.0,   // Consensus between extractions
    "canonical_validation": 0.0–1.0,   // Schema completeness
    "verification_strength": 0.0–1.0,  // How directly proof supports answer
    "overall": weighted_average
}
```

| Tier | Score | Treatment |
|------|-------|-----------|
| **VERIFIED** | >= 0.85 | Green badge, full proof |
| **REVIEW** | 0.50 – 0.85 | Yellow badge, flagged for review |
| **REFUSED** | < 0.50 | Deterministic refusal with reason |

---

## Project Structure

```
akili/
├── frontend/                    # React + TypeScript + Vite + Tailwind
│   ├── src/
│   │   ├── components/          # Header, SidebarLeft, SidebarRight, DocumentViewer,
│   │   │                        #   FileUploader, LandingPage, Onboarding,
│   │   │                        #   IngestSummary, Toast
│   │   ├── contexts/            # AuthContext, ThemeContext, ToastContext
│   │   ├── hooks/               # useOnboarding, useReveal, useScrollReveal
│   │   ├── App.tsx, api.ts, firebase.ts, types.ts
│   │   └── test/                # Vitest setup + 23 tests
│   ├── vercel.json              # Vercel deployment config
│   └── package.json
├── src/akili/
│   ├── canonical/               # Unit, Bijection, Grid, Range, ConditionalUnit
│   ├── ingest/                  # PDF → Gemini → canonicalize pipeline
│   │   ├── gemini_extract.py, consensus.py, multipage.py
│   │   ├── page_classifier.py, canonicalize.py, pdf_loader.py
│   │   └── pipeline.py
│   ├── store/                   # SQLite + PostgreSQL persistence
│   │   ├── repository.py, postgres.py, corrections.py, usage.py
│   │   └── migrate.py
│   ├── verify/                  # 30-rule engine + derived queries + Z3
│   │   ├── proof.py, derived.py, compare.py, z3_checks.py
│   │   └── models.py, matchers.py
│   ├── learn/                   # Correction pattern analysis
│   └── api/                     # FastAPI app + auth + rate limiting
├── tests/                       # 205+ backend tests
├── Dockerfile                   # Production backend (gunicorn + uvicorn)
├── docker-compose.yml
└── pyproject.toml
```

---

## Testing

```bash
# Backend (205+ tests)
pytest tests/ -v

# Frontend (23 tests)
cd frontend && npm test
```

| Area | Tests |
|------|-------|
| Verification rules (30) | 46 |
| Derived queries | 19 |
| Consensus extraction | 12 |
| Correction patterns | 12 |
| Range/ConditionalUnit | 11 |
| Z3 constraints | 10 |
| Multi-page tables | 10 |
| Corrections | 11 |
| Confidence scoring | 11 |
| Storage CRUD | 13 |
| API endpoints | 14 |
| Cross-doc comparison | 7 |
| Extraction/pipeline | 18 |
| Canonical models | 4 |
| Frontend (Vitest) | 23 |

---

## Deployment

| Component | Platform | Config |
|-----------|----------|--------|
| **Frontend** | Vercel | `frontend/vercel.json`, env: `VITE_API_URL`, `VITE_FIREBASE_*` |
| **Backend** | Cloud Run | `Dockerfile`, env: `GOOGLE_API_KEY`, `DATABASE_URL`, `FIREBASE_PROJECT_ID` |
| **Database** | Supabase | PostgreSQL via `DATABASE_URL` |

The frontend detects `VITE_API_URL` at build time (falls back to `/api` for local dev proxy). The backend auto-detects `DATABASE_URL` to switch between SQLite and PostgreSQL.

---

## Environment Variables

See `.env.example` for all variables. Key ones:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | Gemini API key (required for ingestion) |
| `DATABASE_URL` | PostgreSQL connection string (prod) |
| `VITE_API_URL` | Backend URL for frontend (prod) |
| `AKILI_REQUIRE_AUTH` | Set to `1` to require Firebase auth |
| `FIREBASE_PROJECT_ID` | Firebase project for auth verification |
| `AKILI_FREE_TIER_DOCS` | Max documents per user (default: 5) |
| `AKILI_FREE_TIER_QUERIES` | Max queries per user (default: 50) |
| `AKILI_GEMINI_MODEL` | Gemini model (default: gemini-2.0-flash) |

---

## Roadmap

See [`docs/TECHNICAL-EXECUTION-PLAN.md`](docs/TECHNICAL-EXECUTION-PLAN.md) for the full staged plan.

| Stage | Goal | Status |
|-------|------|--------|
| **A: Make It Work** | 30 verification rules, confidence scoring, test coverage | Done |
| **B: Pilot-Ready** | Consensus extraction, Range/ConditionalUnit, Z3, PostgreSQL, review UI | Done |
| **C: Deeper Reasoning** | Derived queries, multi-page tables, cross-doc comparison, correction learning | Done |
| **Deploy** | Vercel + Cloud Run + Supabase, landing page, onboarding, free tier | Done |
| **D: Enterprise** | RBAC, audit trails, LLM abstraction, EDA/JIRA integrations | Planned |

---

## License

TBD.

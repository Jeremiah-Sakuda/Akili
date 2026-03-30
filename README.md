# Akili

**The Reasoning Control Plane for Mission-Critical Engineering**

Akili is a deterministic verification layer for technical documentation. While LLMs excel at fluent reasoning, they fail in high-stakes engineering environments where "mostly right" is $1M worth of wrong. Akili constrains Gemini's multimodal perception within a strict structural framework, turning dense PDFs, pinout tables, and schematics into **auditable, coordinate-grounded truth**.

---

## How It Works

| Pillar | Description |
|--------|-------------|
| **Structural Canonicalization** | Raw Gemini perception → typed objects (units, bijections, grids). Ambiguous data rejected at the source. |
| **Coordinate-Level Grounding** | Every answer mapped to precise `(x, y)` coordinates. No "citations"—only proof. |
| **Deterministic Refusal** | If a specification cannot be derived from the canonical structure, Akili refuses to answer. |
| **Confidence Scoring** | Three-component confidence (extraction agreement, canonical validation, verification strength) classifies answers as VERIFIED, REVIEW, or REFUSED. |

Akili doesn't just ask Gemini for an answer; it **forces Gemini to show its work** against a verifiable map of the truth.

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Runtime** | Python 3.11+ | Native fit for Gemini SDK, PDF/vision pipelines, and symbolic validation. |
| **LLM & Vision** | Google Gemini 3 API (multimodal) | PDFs, tables, schematics as images; structured extraction with coordinate grounding. |
| **Typed Canonical Model** | Pydantic v2 | Units, bijections, grids as validated types; reject invalid shapes at ingestion. |
| **Document Processing** | PyMuPDF (fitz) | Extract pages as images with bounding boxes; feed to Gemini with coordinates. |
| **Coordinate Store** | SQLite (dev) / PostgreSQL (prod) | Persist canonical objects with `(x, y)` and page/doc provenance. Multi-tenant with audit log. |
| **Verification / Proof** | Rule-based engine (30 rules) + derived queries + Z3 constraint checks | Priority-ordered rule registry derives answers from canonical facts; derived query engine computes P=V×I, thermal checks, voltage margins; Z3 validates consistency. |
| **Confidence** | Three-component scoring | Extraction agreement × canonical validation × verification strength → VERIFIED / REVIEW / REFUSED. |
| **API** | FastAPI | Ingest documents, submit queries, return coordinate-grounded answers with confidence or REFUSE. |
| **Frontend** | React + TypeScript + Vite + Tailwind | Three-pane verification workspace: document list, PDF viewer with proof overlay, chat-style query panel. |

### Why Gemini 3

- **Multimodal document understanding** — Native vision + text in one model. PDF pages sent as images; Gemini interprets layout, symbols, and structure in a single pass.
- **Structured output** — Reliably returns JSON conforming to the canonical schema (units, bijections, grids) with required `(x, y)` coordinates.
- **Technical content reasoning** — Strong at parsing datasheets, pin mappings, and grids where precise cell-level grounding matters.
- **Efficiency** — Use `AKILI_GEMINI_MODEL=gemini-3-flash-preview` for faster, lower-cost extraction; default Pro for maximum accuracy.

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
│  • Ranges (min/typ/max with conditions) [Stage B]                           │
│  • ConditionalUnits (value + condition + derating) [Stage B]                │
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
│                                                                              │
│  Optional: Shadow Formatting (Gemini rephrases answer — opt-in, labeled)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

1. **Ingest**: PDF → split into page images (PyMuPDF at 150 DPI) → classify page type → optionally run consensus dual-pass (Stage B) → send to Gemini with structured prompt → parse into `Unit`, `Bijection`, `Grid`, `Range`, `ConditionalUnit` → detect and merge multi-page tables (Stage C) → Z3 consistency checks → validate → persist only if valid.
2. **Store**: Canonical objects live in SQLite or PostgreSQL with `(doc_id, page, x, y, context, ...)`. No free-text "beliefs"—only structural facts. Immutable audit log tracks all mutations.
3. **Query**: User asks a question → 30 verification rules run in priority order → if no direct match, derived-query engine tries computed answers (P=V×I, thermal check, voltage margin, current budget) with full proof chains → first result returns it with coordinate proof and a three-component confidence score → or deterministic REFUSE.
4. **Compare** (Stage C): Cross-document comparison via `/compare` endpoint. Select multiple documents, compare parameters (max voltage, thermal resistance, etc.) side-by-side with best-value highlighting.
5. **Review** (Stage B): REVIEW-tier answers surface for human confirmation/correction. Engineers can CONFIRM or CORRECT facts via the ReviewPanel.
6. **Learn** (Stage C): Correction patterns are analyzed to detect systematic errors (unit confusion, value scaling, label misreads). Auto-correction rules are built from high-confidence patterns.
7. **Shadow Formatting** (opt-in): When explicitly requested, a separate Gemini call rephrases the verified fact into natural language. The response always labels this as `"formatting_source": "gemini_rephrase"`. Disabled by default.

---

## Verification Rules (30)

The rule engine in `src/akili/verify/proof.py` uses a `@rule(priority)` decorator registry. Rules are tried in priority order (lower = first); the first non-None result wins.

| Priority | Rule | What it answers |
|----------|------|-----------------|
| 100 | Pin lookup | "What is pin 5?" via bijection or grid |
| 150 | Part number | "What is the part number?" / ordering info |
| 160 | Description | "What does this component do?" |
| 200–210 | Absolute max voltage/current | "What is the absolute maximum voltage?" |
| 300–320 | Max voltage/current/capacity | "What is the maximum voltage?" |
| 400–430 | Operating ranges, temperatures | "Operating voltage range?", "Storage temp?", "Soldering temp?" |
| 500–530 | Power, ESD, leakage, threshold | "Max power dissipation?", "ESD ratings?", "Logic threshold levels?" |
| 600–630 | Timing & performance | "Clock frequency?", "Propagation delay?", "Rise/fall time?", "Setup/hold?" |
| 700–750 | Physical / package | "Package type?", "Dimensions?", "Thermal resistance?", "Weight?", "Pin count?", "MSL?" |
| 800 | Recommended operating conditions | Table lookup from grids |
| 900 | Unit-by-intent | Keyword-scored fallback across all unit types |
| 950 | Grid cell lookup | Header-matching fallback across grids |
| 1000 | Unit lookup by label | Fuzzy label/value matching fallback |
| — | **Derived: Power** | P = V × I with full proof chain [C1] |
| — | **Derived: Thermal** | T_j = T_a + (P × θ_JA), safety check [C1] |
| — | **Derived: Voltage Margin** | (V_max - V_op) / V_max × 100% [C1] |
| — | **Derived: Current Budget** | Supply current vs. sum of output currents [C1] |

---

## Confidence Scoring

Every verified answer includes a three-component confidence score:

```
confidence = {
    "extraction_agreement": 0.0–1.0,   // Consensus between extractions (0.5 = single-pass default)
    "canonical_validation": 0.0–1.0,   // Schema completeness (bbox, label, context, unit_of_measure)
    "verification_strength": 0.0–1.0,  // How directly the proof supports the answer
    "overall": weighted_average
}
```

| Tier | Overall Score | UI Treatment |
|------|---------------|--------------|
| **VERIFIED** | ≥ 0.85 | Green badge, full proof |
| **REVIEW** | 0.50 – 0.85 | Yellow badge, flagged for confirmation |
| **REFUSED** | < 0.50 | Red/amber, deterministic refusal with reason |

Thresholds are configurable via `AKILI_VERIFY_THRESHOLD` and `AKILI_REVIEW_THRESHOLD` environment variables.

---

## Project Structure

```
akili/
├── .github/
│   └── workflows/
│       └── ci.yml               # Lint, typecheck, test (backend + frontend)
├── README.md
├── docs/
│   ├── ARCHITECTURE.md          # Detailed design and principles
│   ├── AUDIT.md                 # Full repository audit
│   ├── INGEST-FLOW.md           # Engineer-level ingest walkthrough
│   ├── UI-SPEC.md               # Visual and component spec
│   ├── UX-DESIGN-BRIEF.md       # UX scope and direction
│   └── TECHNICAL-EXECUTION-PLAN.md  # Staged implementation roadmap
├── frontend/                    # React + TypeScript + Vite + Tailwind
│   ├── src/
│   │   ├── components/          # DocumentViewer, FileUploader, Header, LoginPage,
│   │   │                        #   SidebarLeft, SidebarRight, ReviewPanel,
│   │   │                        #   CompareView [C3]
│   │   ├── contexts/            # AuthContext (Firebase), ThemeContext (dark mode)
│   │   ├── App.tsx              # Main app component
│   │   ├── api.ts               # API client with auth
│   │   ├── types.ts             # TypeScript types (QueryResult, FormattingSource, etc.)
│   │   └── firebase.ts          # Firebase config
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
├── src/
│   └── akili/
│       ├── canonical/           # Unit, Bijection, Grid, Range, ConditionalUnit models
│       ├── ingest/              # PDF → Gemini → canonicalize pipeline
│       │   ├── gemini_extract.py   # Gemini API calls with retry/backoff
│       │   ├── gemini_format.py    # Shadow Formatting (opt-in)
│       │   ├── consensus.py        # Dual-pass consensus extraction [B1]
│       │   ├── multipage.py        # Multi-page table detection & merge [C2]
│       │   ├── page_classifier.py  # Page-type classification
│       │   ├── canonicalize.py     # Extract → canonical conversion
│       │   ├── pdf_loader.py       # PDF → page images (PyMuPDF)
│       │   └── pipeline.py         # Orchestration
│       ├── store/               # Persistence layer
│       │   ├── base.py             # Abstract BaseStore interface
│       │   ├── repository.py       # SQLite implementation
│       │   ├── postgres.py         # PostgreSQL implementation [B4]
│       │   ├── corrections.py      # Human correction tracking [B5]
│       │   └── migrate.py          # SQLite → PostgreSQL migration [B4]
│       ├── verify/              # Verification engine
│       │   ├── proof.py            # 30-rule registry with @rule decorator
│       │   ├── derived.py          # Derived query engine (P=V×I, thermal, margin) [C1]
│       │   ├── compare.py          # Cross-document comparison engine [C3]
│       │   ├── matchers.py         # Shared regex patterns and parsers
│       │   ├── z3_checks.py        # Z3 constraint verification [B3]
│       │   └── models.py          # AnswerWithProof, Refuse, ProofChain, ConfidenceScore
│       ├── learn/               # Correction learning [C4]
│       │   └── pattern_analyzer.py # Pattern detection & auto-correction rules
│       └── api/                 # FastAPI app + auth middleware
├── tests/
│   ├── conftest.py              # Shared fixtures (store, sample data)
│   ├── test_verify.py           # 46 verification rule tests
│   ├── test_derived.py          # 19 derived query tests [C1]
│   ├── test_multipage.py        # 10 multi-page table tests [C2]
│   ├── test_compare.py          # 7 cross-document comparison tests [C3]
│   ├── test_pattern_analyzer.py # 12 correction pattern tests [C4]
│   ├── test_consensus.py        # 12 consensus extraction tests [B1]
│   ├── test_canonical_extended.py # 11 Range/ConditionalUnit tests [B2]
│   ├── test_z3_checks.py        # 10 Z3 constraint tests [B3]
│   ├── test_corrections.py      # 11 corrections/audit tests [B5]
│   ├── test_store.py            # 13 storage CRUD tests
│   ├── test_confidence.py       # 11 confidence scoring tests
│   ├── test_api.py              # 14 API endpoint tests
│   ├── test_extraction.py       # 11 extraction prompt/schema tests
│   ├── test_pipeline_integration.py # 7 pipeline integration tests
│   ├── test_canonical.py        # 4 canonical model tests
│   └── benchmark/               # Extraction quality benchmark
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

---

## API Surface

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ingest` | POST | Upload PDF; run ingestion pipeline; populate canonical store. Returns `doc_id` and counts. |
| `/ingest/stream` | POST | Same as `/ingest` but with server-sent events for progress tracking. |
| `/query` | POST | Submit question for a document. Returns answer + proof + confidence, or REFUSE. Optional `include_formatted_answer` for Gemini rephrasing (labeled as `"gemini_rephrase"`). |
| `/documents` | GET | List ingested documents with canonical object counts. |
| `/documents/{doc_id}/canonical` | GET | Inspect canonical objects (units, bijections, grids) for a document. |
| `/documents/{doc_id}/file` | GET | Download the ingested PDF (for viewer). |
| `/documents/{doc_id}` | DELETE | Remove a document and all its canonical objects. |
| `/corrections` | POST | Submit human correction or confirmation for a canonical fact. |
| `/corrections/{doc_id}` | GET | List all corrections for a document. |
| `/corrections/stats/{doc_id}` | GET | Correction statistics (total, confirmation/correction rate). |
| `/compare` | POST | Compare parameters across 2+ documents. Returns side-by-side table with best-value highlighting. [C3] |
| `/patterns` | GET | Analyze correction patterns across all documents (unit confusion, scaling errors, etc.). [C4] |
| `/patterns/{doc_id}` | GET | Correction patterns for a specific document. [C4] |
| `/patterns/suggest` | POST | Suggest auto-correction based on learned patterns. [C4] |
| `/status` | GET | Environment check (API key, DB path). No auth required. |
| `/health` | GET | Health check. No auth required. |

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
3. Open **http://localhost:3001** for the UI. API docs: **http://localhost:8000/docs**.

**Notes:**
- The SQLite DB is stored in a Docker volume `akili-data` (path `/data/akili.db` in the API container).
- To stop: `Ctrl+C` then `docker compose down`. Add `-v` to remove the volume and reset the DB.

---

## Getting Started (local dev)

### Backend (API)

1. **Environment**: Create and activate a venv, then set `GOOGLE_API_KEY` for Gemini.
   - **Windows (PowerShell):** `python -m venv .venv` then `.\.venv\Scripts\Activate.ps1`
   - **macOS/Linux:** `python3 -m venv .venv` then `source .venv/bin/activate`
2. **Install**: `pip install -e ".[dev]"` (for Firebase auth: `pip install -e ".[auth]"`; for Z3 verification: `pip install -e ".[verify]"`).
3. **Run API**:
   ```bash
   python -m uvicorn akili.api.app:app --reload --host 0.0.0.0 --port 8000
   ```
4. **Run tests**:
   ```bash
   pytest tests/ -v
   ```
   Current suite: **205 tests** covering verification rules, derived queries, multi-page tables, cross-document comparison, correction pattern analysis, consensus extraction, Z3 checks, corrections, storage CRUD, confidence scoring, API endpoints, and canonical models.

### Frontend (UI)

1. **Install Node.js** (LTS) from [nodejs.org](https://nodejs.org/).
2. **Start the API** first (see above).
3. **Start the UI** (in a second terminal):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. Open **http://localhost:3000**. Upload a PDF, select a document, ask a question.

### Gemini rate limits (429)

Ingestion calls the Gemini API **once per PDF page**. Free-tier limits can be hit with multi-page PDFs. The app retries on 429 with exponential backoff and waits between pages to reduce bursts.

- **Tuning:** Override with `AKILI_GEMINI_PAGE_DELAY_SECONDS` (default 4), `AKILI_GEMINI_MAX_RETRIES` (default 6), `AKILI_GEMINI_BACKOFF_BASE` (default 8s), and `AKILI_GEMINI_429_COOLDOWN_SECONDS` (default 60s). See `.env.example`.

### Firebase hosting & sign-in

The app supports optional Google sign-in via Firebase. See `.env.example` for the required `VITE_FIREBASE_*` variables. When `AKILI_REQUIRE_AUTH=1` is set, the API requires a valid Firebase ID token on all endpoints except `/health` and `/status`.

---

## CI/CD

GitHub Actions workflow in `.github/workflows/ci.yml` runs on every push and PR to `main`, `master`, and `develop`.

| Job | What it does |
|-----|--------------|
| **Backend (Python)** | Matrix: Python 3.11 and 3.12. Installs `.[dev]`, runs Ruff (lint + format check), Flake8, pytest with coverage. |
| **Frontend (Node)** | Node 20. `npm ci` → ESLint → TypeScript (`tsc --noEmit`) → Vite build. |

**Local equivalents:**
- Backend: `pip install -e ".[dev]"` then `ruff check src tests`, `flake8 src tests`, `pytest tests -v`
- Frontend: `cd frontend && npm ci && npm run lint && npm run typecheck && npm run build`

---

## Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| `verify/proof.py` (30 rules) | 46 | 70% |
| `verify/derived.py` (4 derivations) | 19 | 95% |
| `verify/compare.py` (cross-doc) | 7 | 90% |
| `verify/models.py` (confidence) | 11 | 100% |
| `verify/z3_checks.py` | 10 | 85% |
| `ingest/consensus.py` | 12 | 90% |
| `ingest/multipage.py` (multi-page tables) | 10 | 95% |
| `store/repository.py` | 13 | 100% |
| `store/corrections.py` | 11 | 95% |
| `learn/pattern_analyzer.py` | 12 | 90% |
| `canonical/models.py` (incl. Range, ConditionalUnit) | 15 | 98% |
| `ingest/gemini_extract.py` + `page_classifier.py` | 11 | 60% |
| `ingest/pipeline.py` | 7 | 65% |
| `api/app.py` | 14 | 35% |
| `benchmark/` | 3 | N/A |
| **Total** | **205** | **~62%** |

---

## Roadmap

See [`docs/TECHNICAL-EXECUTION-PLAN.md`](docs/TECHNICAL-EXECUTION-PLAN.md) for the full staged implementation plan.

| Stage | Goal | Status |
|-------|------|--------|
| **A: Make It Work** | 30 verification rules, confidence scoring, shadow format fix, test coverage | **Done** |
| **B: Pilot-Ready** | Consensus extraction, Range/ConditionalUnit models, Z3 checks, PostgreSQL, review UI | **Done** |
| **C: Deeper Reasoning** | Derived queries (P=V×I), multi-page tables, cross-document comparison, correction learning | **Done** |
| **D: Enterprise** | RBAC, audit trails, LLM abstraction (swap Gemini/Claude/GPT-4V), EDA/JIRA integrations | Planned |

---

## License

TBD.

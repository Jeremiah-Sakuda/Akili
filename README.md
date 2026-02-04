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

## Project Structure (Scaffold)

```
akili/
├── README.md                 # This file
├── docs/
│   └── ARCHITECTURE.md       # Deeper design notes
├── src/
│   └── akili/
│       ├── __init__.py
│       ├── canonical/        # Typed models: Unit, Bijection, Grid
│       ├── ingest/           # PDF → chunks → Gemini → canonicalize
│       ├── store/            # Persistence for canonical objects
│       ├── verify/           # Proof check + deterministic refusal
│       └── api/              # FastAPI app: ingest + query
├── tests/
├── pyproject.toml
└── requirements.txt
```

---

## Getting Started

### Backend (API)

1. **Environment**: `python -m venv .venv`, activate it, set `GOOGLE_API_KEY` for Gemini.
2. **Install**: `pip install -e .`
3. **Run API**: `akili-serve` or `uvicorn akili.api.app:app --reload --host 0.0.0.0 --port 8000`
4. **Ingest a doc**: `POST /ingest` with PDF (multipart form `file`) → canonical store populated; returns `doc_id`.
5. **Query**: `POST /query` with body `{"doc_id": "<from ingest>", "question": "What is pin 5?"}` → coordinate-grounded answer + proof or REFUSE.
6. **List docs**: `GET /documents`. **Inspect canonical**: `GET /documents/{doc_id}/canonical`.

### UI (akili-workspace)

The React + TypeScript UI in `akili-workspace/` is wired to the API via a Vite proxy.

1. **Start the API** (from repo root): `akili-serve` (or `uvicorn akili.api.app:app --reload --port 8000`).
2. **Start the UI**: `cd akili-workspace && npm install && npm run dev`.
3. Open **http://localhost:3000**. Upload a PDF, then select a document and ask a question; the right panel shows VERIFIED (answer + proof) or REFUSED.

---

## License

TBD.

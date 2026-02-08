# Akili Architecture (Detailed)

## Design Principles

1. **Canonical-first**: Only typed, coordinate-grounded facts exist in the truth store. No free-form “beliefs.”
2. **Refuse by default**: If the verification layer cannot derive an answer from canonical facts, the system returns REFUSE—no hedging.
3. **Provenance is mandatory**: Every fact carries `(doc_id, page, x, y)` (and optional bbox). Answers cite these coordinates, not “page 3.”

---

## Core Types (Canonical Schema)

### Unit
- Represents a single measurable or named entity (e.g. a pin label, a voltage value with unit).
- Fields: `id`, `label`, `value`, `unit_of_measure`, `origin (x, y)`, `doc_id`, `page`, `bbox` (optional).
- Used when Gemini extracts a discrete fact with a clear location.

### Bijection
- Represents a strict 1:1 mapping between two sets (e.g. pin name ↔ pin number).
- Fields: `id`, `left_set`, `right_set`, `mapping`, `coordinate_ranges` (where in the doc this mapping holds), `doc_id`, `page`.
- Used for pinout tables, symbol–reference pairs, etc.

### Grid
- Represents a tabular or schematic region with cell-level coordinates.
- Fields: `id`, `rows`, `cols`, `cell_facts` (e.g. `(row, col) → value`), `origin (x, y)`, `cell_size` or bbox per cell, `doc_id`, `page`.
- Used for datasheet tables, pinout grids, schematic grids.

All types are **validated at ingestion**. Ambiguous or low-confidence extractions are rejected (no “best guess” in the store).

---

## Ingestion Pipeline

1. **PDF → Pages/Regions**  
   Use PyMuPDF (or pdf2image) to get per-page images and optional text/layout. Optionally detect tables/schematic regions (e.g. via layout heuristics or Gemini).

2. **Chunking with Coordinates**  
   Each chunk sent to Gemini has an explicit coordinate context: e.g. “This image is page N; region (x1,y1)–(x2,y2). Return only facts that can be tied to (x,y).”

3. **Gemini 3 Multimodal Extraction**  
   Akili uses Gemini 3 for this step because it excels at document vision, structured JSON output, and coordinate-level grounding—critical for technical PDFs and schematics. Prompt Gemini to output **structured** extractions: e.g. JSON conforming to Unit / Bijection / Grid schemas, with required `(x,y)` or bbox. Use structured output / response schema to reduce hallucination.

4. **Canonicalize**  
   Parse Gemini response into Pydantic models. Validate. Reject any object that fails validation or has missing coordinates.

5. **Persist**  
   Write only validated objects to the store (SQLite/PostgreSQL) with full provenance.

---

## Verification Layer

- **Retrieval**: Given a user question, retrieve relevant canonical facts (by semantic similarity and/or coordinate region). Use embeddings over canonical object summaries if needed; keep coordinates in the retrieved set.
- **Proof check**: Determine whether the intended answer is **derivable** from the retrieved facts:
  - For “what is pin 5?” use Bijection/Grid to get the mapping and return the value + `(x,y)`.
  - For “what is the max voltage?” use Units with the same quantity; ensure the answer is one of the stored values and cite its coordinates.
- **Refuse**: If no derivation exists (e.g. missing fact, contradictory facts, or answer not in canonical set), return REFUSE with an optional short reason (e.g. “No bijection found for pin 5 in this document”).

- **Shadow Formatting (optional)**: When the client requests it (`include_formatted_answer`), and the answer is verified, a separate step calls Gemini with a strict fact-only prompt: rephrase the verified fact (Q, F, C) into one sentence; do not add outside knowledge; if F does not answer Q, return `UNABLE TO PHRASE`. The response always includes raw `answer` and `proof`; `formatted_answer` is added only when the format call succeeds within a short timeout. On timeout or failure, the UI silently shows the raw answer. Implemented in `akili.ingest.gemini_format`.

Determinism: same question + same canonical store → same answer or same REFUSE. No sampling in the verification step. Shadow Formatting does not affect determinism of the answer itself.

---

## API Surface

| Endpoint | Purpose |
|----------|--------|
| `POST /ingest` | Upload PDF; run ingestion pipeline; populate canonical store. |
| `POST /query` | Submit question; return coordinate-grounded answer + proof or REFUSE. Request body may include `include_formatted_answer: true`; when true and the answer is verified, response may include `formatted_answer` (one-sentence natural-language phrasing from Gemini; silent fallback to raw answer on timeout/failure). |
| `GET /documents` | List ingested documents and their canonical object counts. |
| `GET /documents/{id}/canonical` | Inspect canonical objects for a document (for debugging/demos). |

---

## Optional: Judge Demo Viewer

- Load PDF in browser (e.g. PDF.js).
- For a given query, display the answer and overlay the **proven** coordinates (e.g. highlight the bbox or cell that supports the answer).
- Makes “proof” visible: the map of the truth that Akili used.

---

## Dependencies (Summary)

- **Python 3.11+**
- **google-generativeai** (Gemini API)
- **pydantic** (v2)
- **PyMuPDF** (fitz) and/or **pdf2image**
- **FastAPI**, **uvicorn**
- **SQLite** (stdlib) or **asyncpg** + **PostgreSQL** for store
- Optional: **z3-solver** for richer constraint-based verification; **sentence-transformers** or Gemini embeddings for retrieval.

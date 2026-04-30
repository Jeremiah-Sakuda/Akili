# Akili Architecture (Detailed)

## Design Principles

1. **Canonical-first**: Only typed, coordinate-grounded facts exist in the truth store. No free-form "beliefs."
2. **Refuse by default**: If the verification layer cannot derive an answer from canonical facts, the system returns REFUSE -- no hedging.
3. **Provenance is mandatory**: Every fact carries `(doc_id, page, x, y)` (and optional bbox). Answers cite these coordinates, not "page 3."
4. **Verification > extraction**: Akili's value is not a better extractor -- it's a verification layer that refuses to guess. The answer must be provably grounded or not returned at all.
5. **Confidence is multi-dimensional**: A single "correct/incorrect" binary is insufficient. Extraction agreement, canonical completeness, and proof strength each contribute independently to overall confidence.
6. **Consensus before trust**: For high-risk fact types (voltages, currents, temperatures), dual-pass extraction with agreement scoring prevents single-pass hallucinations.
7. **Formal verification where feasible**: Z3 constraint solving provides mathematical guarantees for unit normalization, contradiction detection, and range consistency.

---

## Core Types (Canonical Schema)

### Unit
- Represents a single measurable or named entity (e.g. a pin label, a voltage value, a temperature range).
- Fields: `id`, `label`, `value`, `unit_of_measure`, `context`, `origin (x, y)`, `doc_id`, `page`, `bbox` (optional).
- `context` captures the section or table the unit was extracted from (e.g., "Absolute Maximum Ratings", "Electrical Characteristics at 25C").
- Used when Gemini extracts a discrete fact with a clear location.

### Bijection
- Represents a strict 1:1 mapping between two sets (e.g. pin name <-> pin number).
- Fields: `id`, `left_set`, `right_set`, `mapping`, `coordinate_ranges`, `doc_id`, `page`.
- Used for pinout tables, symbol-reference pairs, etc.

### Grid
- Represents a tabular or schematic region with cell-level coordinates.
- Fields: `id`, `rows`, `cols`, `cell_facts` (e.g. `(row, col) -> value`), `row_headers`, `col_headers`, `origin (x, y)`, `doc_id`, `page`.
- `row_headers` and `col_headers` enable header-matching for grid cell lookup queries.
- Used for datasheet tables, pinout grids, schematic grids.

### Range (Stage B)
- Captures min/typ/max specifications with optional conditions.
- Fields: `id`, `label`, `min`, `typ`, `max`, `unit`, `conditions`, `context`, `origin`, `doc_id`, `page`, `bbox`.
- `conditions` handles qualifiers like "at 25C" or "VCC = 3.3V".
- Used for electrical characteristics tables where parameters have min/typ/max columns.

### ConditionalUnit (Stage B)
- Captures values that depend on specific conditions (derating curves, temperature-dependent specs).
- Fields: `id`, `label`, `value`, `unit`, `condition_type`, `condition_value`, `derating`, `context`, `origin`, `doc_id`, `page`, `bbox`.
- Example: "4.2V max at Ta <= 85C, derate 20mV/C above 85C"

All types are **validated at ingestion**. Ambiguous or low-confidence extractions are rejected (no "best guess" in the store).

---

## Verification Layer

### Rule Registry Pattern

The verification engine uses a `@rule(priority, name)` decorator to register functions. At query time, rules execute in priority order (lower number = higher priority). The first rule that returns a non-None `AnswerWithProof` wins.

```python
@rule(100, "pin_lookup")
def _try_pin_lookup(question, units, bijections, grids) -> AnswerWithProof | None:
    ...
```

This pattern provides:
- **Easy extensibility**: New rules are added by decorating a function; no modification to the dispatch loop.
- **Explicit prioritization**: More specific rules (pin lookup, part number) run before generic fallbacks (unit-by-intent, grid cell lookup).
- **Testability**: Each rule is independently testable by calling it directly with known canonical data.

### Shared Matchers (`verify/matchers.py`)

Centralizes all regex patterns and parsing functions used across rules:
- Voltage, current, temperature, power, frequency, time, resistance parsers
- Unit normalization helpers (e.g. "4.2V" -> `(4.2, "V")`)
- Keyword overlap scoring for intent matching
- Context-based unit filtering (e.g. "absolute maximum" vs. "operating" ranges)

### 30 Verification Rules + 4 Derived Query Types

| Category | Rules | Priority Range |
|----------|-------|----------------|
| Pin/Part/Description | Pin lookup, part number, description | 100-160 |
| Absolute Maximum Ratings | Max voltage, max current (absolute) | 200-210 |
| Maximum Ratings (general) | Max voltage, max current, max capacity | 300-320 |
| Operating Ranges | Voltage range, temperature, storage temp, soldering temp | 400-430 |
| Electrical Characteristics | Power dissipation, ESD, leakage, threshold voltage | 500-530 |
| Timing & Performance | Clock/bandwidth, propagation delay, rise/fall, setup/hold | 600-630 |
| Physical / Package | Package type, dimensions, thermal resistance, weight, pin count, MSL | 700-750 |
| Table Lookup | Recommended operating conditions from grids | 800 |
| Generic Fallbacks | Unit-by-intent, grid cell lookup, unit label matching | 900-1000 |
| **Derived Queries** (Stage C) | Power (P=V×I), Thermal (T_j=T_a+P×θ_JA), Voltage Margin, Current Budget | After all direct rules |

### Derived Query Engine (`verify/derived.py`, Stage C)

After all 30 direct-lookup rules are tried, the derived query engine attempts to compute an answer from multiple canonical facts. Each derivation returns an `AnswerWithProof` with a full `ProofChain` showing every step.

| Derivation | Formula | Inputs |
|------------|---------|--------|
| **Power Dissipation** | P = V × I | Supply voltage + supply current |
| **Thermal Check** | T_j = T_a + (P × θ_JA) | Thermal resistance + power (direct or computed) + optional max T_j for safety check |
| **Voltage Margin** | (V_max - V_op) / V_max × 100% | Operating voltage + absolute maximum voltage |
| **Current Budget** | I_supply - Σ I_outputs | Total supply current + individual output currents |

Each derivation includes a `ProofChain` with `ProofStep` objects containing the formula, source facts with `(x,y)` coordinates, and intermediate results.

### Confidence Scoring

Every `AnswerWithProof` includes a `ConfidenceScore` with three components:

1. **`extraction_agreement`** (0.0-1.0): How consistent was the extraction? Default 0.5 for single-pass; upgraded to actual agreement score with consensus extraction.
2. **`canonical_validation`** (0.0-1.0): Schema completeness score -- does the canonical object have a bounding box, label, context, unit_of_measure, and origin?
3. **`verification_strength`** (0.0-1.0): How directly the rule's proof supports the answer. Specific rules (pin lookup, absolute max) score 0.9-0.95; generic fallbacks score 0.5-0.7.

```
overall = 0.30 x extraction_agreement + 0.30 x canonical_validation + 0.40 x verification_strength
```

Thresholds (configurable via env vars):
- `overall >= 0.85` -> **VERIFIED** (green, full proof)
- `0.50 <= overall < 0.85` -> **REVIEW** (yellow, flagged for human confirmation)
- `overall < 0.50` -> **REFUSED** (deterministic refusal with reason)

### Z3 Constraint Checks (Stage B)

Three formal verification checks run on canonical data after ingestion:

1. **Unit normalization**: Asserts dimensional consistency (4.2V == 4200mV == 0.0042kV). Flags any fact that fails conversion.
2. **Contradiction detection**: For facts with the same parameter label extracted from different pages, checks for logical contradictions (e.g., max voltage = 5.5V on page 3 but 5.0V on page 7).
3. **Range consistency**: Asserts min <= typ <= max for all Range objects using Z3 satisfiability.

Degrades gracefully if z3-solver is not installed.

---

## Ingestion Pipeline

1. **PDF -> Pages/Regions**: PyMuPDF renders each page at 150 DPI as PNG. Per-page fault tolerance -- bad pages are skipped.
2. **Page Classification**: Lightweight Gemini call classifies page type (pinout, electrical specs, absolute max, etc.) to enable type-specific prompt hints.
3. **Consensus Extraction** (Stage B, opt-in for high-risk pages): Runs Gemini twice with precision-focused and recall-focused prompts. Agreement score feeds `extraction_agreement` in confidence.
4. **Gemini Extraction**: Structured prompt with few-shot examples, coordinate calibration, and page-type hints. Uses simplified JSON schema for structured output.
5. **Normalization**: Fill missing IDs, drop units without valid origins or values, namespace IDs by page (`p0_u0`, `p1_b0`).
6. **Canonicalize**: Parse into Pydantic models (`Unit`, `Bijection`, `Grid`, `Range`, `ConditionalUnit`). Validate. Reject any object that fails validation.
7. **Z3 Checks** (Stage B): Run unit normalization, contradiction, and range consistency checks on extracted data.
8. **Persist**: Write validated objects to SQLite or PostgreSQL with full provenance (`doc_id`, `page`, `origin`, `bbox`).

---

## Shadow Formatting

Shadow Formatting is the optional Gemini rephrasing of verified answers into natural language.

**Current design (post-A1 fix):**
- Disabled by default. The verified raw answer is the primary response.
- Enabled only when the client explicitly passes `include_formatted_answer: true`.
- The API response always includes `formatting_source`:
  - `"verified_raw"` -- the answer is the direct canonical fact.
  - `"gemini_rephrase"` -- the answer was rephrased by Gemini (unverified formatting).
- The frontend displays an "AI-rephrased" badge when `formatting_source` is `"gemini_rephrase"`.
- On timeout or Gemini failure, the raw answer is returned silently.

This prevents the previous design flaw where non-deterministic rephrasing was presented as if it carried the same guarantee as the verified fact.

---

## Storage Layer

### Abstract Interface (`store/base.py`)

All store backends implement `BaseStore` with methods for CRUD on all canonical types (Unit, Bijection, Grid, Range, ConditionalUnit) plus document management and audit logging.

### SQLite Store (`store/repository.py`)
- Default backend for development and single-user deployment.
- Flat tables per canonical type with JSON columns for complex fields (origin, bbox, cells).
- Immutable audit log table tracks all mutations.

### PostgreSQL Store (`store/postgres.py`, Stage B)
- Multi-tenant with `org_id` isolation on every table.
- Immutable `audit_log` table: who ingested what, when, with what parameters.
- Connection pooling ready for concurrent access.
- Factory function `create_store()` selects backend from `DATABASE_URL` env var.

### Migration (`store/migrate.py`)
- CLI tool to copy all data from SQLite to PostgreSQL.
- Preserves all canonical objects, document metadata, and provenance.

---

## Human-in-the-Loop Review (Stage B)

### Corrections Store (`store/corrections.py`)
When confidence is in the REVIEW band (0.50-0.85):
- **CONFIRM**: Engineer verifies the extracted fact is correct.
- **CORRECT**: Engineer provides the right value; both original extraction and correction are stored.
- All corrections logged with provenance: who corrected, when, what the original was.

### API Endpoints
- `POST /corrections` -- Submit a confirmation or correction.
- `GET /corrections/{doc_id}` -- List all corrections for a document.
- `GET /corrections/stats/{doc_id}` -- Correction statistics (total, rate).

### Frontend (`ReviewPanel.tsx`)
- Inline review form for REVIEW-tier facts: "Confirm Correct" or "Provide Correction" buttons.
- Correction history with color-coded entries (green = confirmed, blue = corrected).
- Stats summary showing confirmation/correction counts.

The correction log is the foundation for future learning mechanisms (ART or simpler calibration).

---

## Derived Query Engine (Stage C)

### Architecture (`verify/derived.py`)

After all 30 direct-lookup rules are exhausted, the derived query engine attempts to compute answers by combining multiple canonical facts. Each derivation produces an `AnswerWithProof` with a full `ProofChain` showing every step.

### Supported Derivations

| Derivation | Formula | Source Facts |
|-----------|---------|--------------|
| **Power Dissipation** | P = V × I | Supply voltage + supply current units |
| **Thermal Check** | T_j = T_a + (P × θ_JA) | Thermal resistance + power (or V×I); checks against max T_j |
| **Voltage Margin** | margin = (V_max - V_op) / V_max × 100% | Operating voltage + absolute max voltage |
| **Current Budget** | remaining = I_supply - Σ(I_outputs) | Supply current + all output currents |

### Proof Chains

Every derived answer includes a `ProofChain` with:
- Ordered `ProofStep` list: each step has a description, optional formula, source facts (with coordinates), and intermediate result.
- `final_result`: The computed answer.
- `formula_summary`: Human-readable derivation (e.g. "P = 3.3V × 0.05A = 165.0 mW").

---

## Multi-Page Table Handling (Stage C)

### Detection (`ingest/multipage.py`)

After all pages are extracted, the pipeline detects tables that span page boundaries:
- A Grid ending near the bottom of a page (y > 0.80) with another Grid starting near the top of the next page (y < 0.20).
- Same column count and similar column headers (Jaccard similarity ≥ 0.5).
- Grids must share the same `doc_id` and be on consecutive pages.

### Merge Logic
- Second grid's rows are offset by grid_a.rows.
- If column headers are identical (repeated header row), the duplicate header is skipped.
- Merged grid's ID is `{grid_a.id}_merged_{grid_b.id}`.
- Merged grids are flagged for human review when column similarity < 0.8.

---

## Cross-Document Comparison (Stage C)

### Engine (`verify/compare.py`)

Compares parameters across multiple documents using SQL JOINs (no graph database):
- Detects which parameters the user wants to compare from the query text.
- Finds the best matching Unit for each parameter in each document.
- Produces a `ComparisonResult` per parameter with rows per document and best-value highlighting.

### Predefined Parameters
- Maximum Voltage, Supply Voltage, Thermal Resistance, Maximum Current, Operating Temperature, Power Dissipation.
- Automatic direction: "lower is better" for max voltage/thermal resistance/power; "higher is better" for operating temperature.

### API Endpoint
- `POST /compare` with `{doc_ids: [...], question: "..."}` returns comparison tables.

### Frontend (`CompareView.tsx`)
- Document selector with multi-select toggle buttons.
- Query input for focused comparisons.
- Results displayed as comparison tables with best-value highlighting (green).

---

## Correction Pattern Analysis & Learning (Stage C)

### Pattern Analyzer (`learn/pattern_analyzer.py`)

Analyzes the correction log to identify systematic extraction errors:

| Pattern Type | Detection Logic | Example |
|-------------|----------------|---------|
| **Unit Confusion** | Same unit swap occurs repeatedly | mV → V extracted incorrectly 5 times |
| **Value Scaling** | Values consistently off by 10x, 100x, etc. | Current values off by 10x |
| **Label Misread** | Same label text consistently wrong | "therml" → "thermal" |
| **Type Bias** | Certain canonical types have disproportionately high correction rates | Ranges corrected 60% of the time |

### Auto-Correction Rules
- When a pattern has ≥ 5 occurrences and is flaggable as auto-correctable, an `AutoCorrectionRule` is generated.
- `suggest_correction(canonical_type, original_value)` checks all rules and returns a corrected value if any match.

### API Endpoints
- `GET /patterns` — Global pattern stats.
- `GET /patterns/{doc_id}` — Document-specific patterns.
- `POST /patterns/suggest` — Auto-correction suggestion.

---

## API Surface

| Endpoint | Purpose |
|----------|---------|
| `POST /ingest` | Upload PDF; run ingestion pipeline; populate canonical store. Returns `doc_id`, counts, pages_failed. |
| `POST /ingest/stream` | Same as `/ingest` with server-sent events for progress. |
| `POST /query` | Submit question; return `AnswerWithProof` (answer + proof + confidence + formatting_source) or `Refuse`. |
| `GET /documents` | List ingested documents with canonical object counts. |
| `GET /documents/{id}/canonical` | Inspect canonical objects for a document. |
| `GET /documents/{id}/file` | Download ingested PDF. |
| `DELETE /documents/{id}` | Delete document and all canonical data. |
| `POST /corrections` | Submit human correction or confirmation. |
| `GET /corrections/{doc_id}` | List corrections for a document. |
| `GET /corrections/stats/{doc_id}` | Correction statistics. |
| `POST /compare` | Compare parameters across 2+ documents with best-value highlighting. [C3] |
| `GET /patterns` | Global correction pattern analysis. [C4] |
| `GET /patterns/{doc_id}` | Document-specific correction patterns. [C4] |
| `POST /patterns/suggest` | Auto-correction suggestion from learned patterns. [C4] |
| `GET /status` | Environment check (API key, DB). |
| `GET /health` | Health check. |

### Query Response Shape

**Verified answer:**
```json
{
  "status": "answer",
  "answer": "4.2V",
  "proof": [{"x": 142, "y": 387, "source_id": "p3_u47", "source_type": "unit"}],
  "confidence": {
    "extraction_agreement": 0.5,
    "canonical_validation": 0.85,
    "verification_strength": 0.92,
    "overall": 0.78
  },
  "confidence_tier": "review",
  "formatting_source": "verified_raw"
}
```

**Refusal:**
```json
{
  "status": "refuse",
  "reason": "No canonical fact derives this answer for the given document.",
  "formatting_source": "verified_raw"
}
```

---

## Frontend

### Three-Pane Verification Workspace

| Pane | Content |
|------|---------|
| **Left** (`SidebarLeft`) | Document list, file uploader, canonical inspector (Units / Bijections / Grids tabs) |
| **Center** (`DocumentViewer`) | PDF viewer (pdfjs-dist) with proof overlay layer for coordinate-grounded highlights |
| **Right** (`SidebarRight`) | Chat-style query interface with VERIFIED / REVIEW / REFUSED badges, proof details, "AI-rephrased" label, confidence percentage |

### Key UI Features
- Color-coded confidence badges: green (VERIFIED), yellow (REVIEW), red (REFUSED)
- Proof overlay on PDF viewer when "Show on document" is clicked
- **ReviewPanel** (Stage B): Inline correction/confirmation forms for REVIEW-tier facts
- **CompareView** (Stage C): Cross-document parameter comparison with side-by-side tables
- Dark mode support (ThemeContext)
- Optional Firebase Google sign-in (AuthContext)
- Formatting transparency: "AI-rephrased" badge when Shadow Formatting is active

---

## Dependencies (Summary)

- **Python 3.11+**
- **google-generativeai** (Gemini API)
- **pydantic** (v2)
- **PyMuPDF** (fitz)
- **FastAPI**, **uvicorn**
- **SQLite** (stdlib, default) or **PostgreSQL** via **psycopg2** (Stage B)
- Optional: **z3-solver** for constraint verification; **firebase-admin** for auth
- **React**, **TypeScript**, **Vite**, **Tailwind CSS**, **pdfjs-dist**

---

## Test Suite

205 passing tests across 16 test files:

| File | Count | Coverage |
|------|-------|----------|
| `test_verify.py` | 46 | Verification rules, priority, edge cases |
| `test_derived.py` | 19 | Derived queries: power, thermal, margin, budget [C1] |
| `test_multipage.py` | 10 | Multi-page table detection and merge [C2] |
| `test_compare.py` | 7 | Cross-document comparison engine [C3] |
| `test_pattern_analyzer.py` | 12 | Correction pattern analysis and auto-correction [C4] |
| `test_consensus.py` | 12 | Consensus extraction, agreement scoring, merging |
| `test_canonical_extended.py` | 11 | Range, ConditionalUnit models and storage |
| `test_z3_checks.py` | 10 | Z3 unit normalization, contradictions, range consistency |
| `test_corrections.py` | 11 | Corrections store, stats, audit logging |
| `test_store.py` | 13 | Storage CRUD, duplicates, deletion |
| `test_confidence.py` | 11 | Scoring, tiering, canonical quality |
| `test_extraction.py` | 11 | Prompt, schema, page classifier |
| `test_pipeline_integration.py` | 7 | End-to-end pipeline with mocked Gemini |
| `test_api.py` | 14 | Endpoint validation, error handling |
| `test_canonical.py` | 4 | Model construction and serialization |
| `benchmark/test_benchmark.py` | 3 | Benchmark harness, pass rate, false-accept checks |
| Other | 4 | Misc test utilities |

Shared fixtures in `conftest.py` provide ~30 sample `Unit` objects, sample bijections, sample grids, and a temporary SQLite store.

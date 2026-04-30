# AKILI: Technical Execution Plan

Derived from the Revised Improvement Plan v2. Every item maps to a concrete file, function, schema change, or test. Estimated line counts and dependencies are included so work can be parallelized and progress tracked objectively.

---

## Notation

| Symbol | Meaning |
|--------|---------|
| `[NEW]` | New file to create |
| `[MOD]` | Modify existing file |
| `[DEP]` | Depends on another task completing first |
| `LOC` | Rough lines of code |
| `Fx` | File reference (used in dependency chains) |

---

## Stage A: Make It Actually Work (Weeks 1-8) — COMPLETED

### A1. Fix Shadow Formatting (Week 1)

**Goal:** Gemini-rephrased answers never appear as verified. Raw verified answer is default; formatting is opt-in and labeled.

| # | Task | File | Details |
|---|------|------|---------|
| A1.1 | Make `format_answer` opt-in only | `[MOD] src/akili/api/app.py` | The `include_formatted_answer` field already defaults to `False` on `QueryRequest` (line 141). Verify the `/query` handler only calls `format_answer` when `include_formatted_answer=True`. Currently correct (line 389). **No backend change needed.** |
| A1.2 | Stop auto-formatting refusals | `[MOD] src/akili/api/app.py` | Lines 367-385: The `/query` handler *always* calls `format_refusal()` via Gemini for every `Refuse` result, even when `include_formatted_answer=False`. This is the shadow formatting bug. **Fix:** wrap the refusal formatting block in `if req.include_formatted_answer:`. Without the flag, return the deterministic `Refuse.reason` from `proof.py` unchanged. |
| A1.3 | Add `formatting_source` to query response | `[MOD] src/akili/api/app.py` | When `formatted_answer` is returned, add `"formatting_source": "gemini_rephrase"` to the response JSON. When omitted, add `"formatting_source": "verified_raw"`. ~5 LOC. |
| A1.4 | Frontend: distinguish verified vs rephrased | `[MOD] frontend/src/components/SidebarRight.tsx` | If `formatting_source === "gemini_rephrase"`, render with a gray badge "AI-rephrased (unverified formatting)". If `"verified_raw"`, render with green badge "Verified". Update `frontend/src/types.ts` to include the new field. ~20 LOC across 2 files. |

**Tests:**
| # | Task | File | Details |
|---|------|------|---------|
| A1.T1 | Test refusal without formatting | `[MOD] tests/test_api.py` | POST `/query` with `include_formatted_answer=false` on a doc with no matching facts. Assert response `reason` is the deterministic string from `proof.py`, not a Gemini-generated string. |
| A1.T2 | Test formatting flag propagation | `[MOD] tests/test_api.py` | POST `/query` with `include_formatted_answer=true`. Assert `formatted_answer` key present and `formatting_source` is `"gemini_rephrase"`. |

---

### A2. Expand proof.py — Verification Rules (Weeks 1-4)

**Goal:** Go from 6 rules to 30. Each rule is a pure function: `(question, units, bijections, grids) -> AnswerWithProof | None`.

**Architecture change:** Refactor `proof.py` from a flat file of functions into a rule registry pattern. Each rule is a function decorated with `@rule`. `verify_and_answer` iterates the registry in order.

#### A2.0 Rule Registry Refactor

| # | Task | File | Details |
|---|------|------|---------|
| A2.0.1 | Create rule registry | `[MOD] src/akili/verify/proof.py` | Add a `_RULES: list[Callable]` registry and a `@rule(priority=N)` decorator. `verify_and_answer` becomes a loop over `_RULES` sorted by priority. Existing 6 rules get priorities 100-600. New rules slot in between. ~40 LOC refactor. |
| A2.0.2 | Extract helper module | `[NEW] src/akili/verify/matchers.py` | Move regex patterns (`_VOLTAGE_PATTERN`, `_CURRENT_PATTERN`, etc.) and parser functions (`_parse_voltage_from_text`, etc.) into a shared matchers module. Add new patterns for temperature, power, frequency, time, resistance, and dimension parsing. ~120 LOC. |

#### A2.1 Electrical Characteristics Rules (Week 1-2)

Each rule follows the pattern: detect intent from question keywords -> scan units/grids for matching facts -> return `AnswerWithProof` with proof point or `None`.

| # | Rule | Trigger Keywords | Matching Logic |
|---|------|-----------------|----------------|
| A2.1.1 | Operating voltage range | "operating voltage", "supply voltage", "vcc range", "vdd range" | Find units where `context` or `label` contains "operating"/"supply" + "voltage". Return as `"{min} to {max} V"`. If only one value, return it. |
| A2.1.2 | Operating temperature range | "operating temp", "junction temp", "temperature range" | Find units with `context`/`label` matching "operating"/"junction" + "temperature"/"temp". Also scan grids for rows with "temperature" header. |
| A2.1.3 | Power dissipation | "power dissipation", "max power", "power rating" | Match units with `unit_of_measure` in `(W, mW)` or `context` containing "power dissipation". |
| A2.1.4 | ESD ratings | "esd", "electrostatic", "esd rating" | Match units/grids with labels containing "ESD", "HBM", "CDM", or `context` matching "electrostatic". |
| A2.1.5 | Leakage current | "leakage current", "input leakage", "ileak" | Match units with `context`/`label` containing "leakage" + current unit. |
| A2.1.6 | Threshold voltage | "threshold", "vil", "vih", "logic level" | Match units with labels matching V_IL, V_IH, V_OL, V_OH or `context` containing "threshold". |

**File:** `[MOD] src/akili/verify/proof.py` — add 6 functions, ~180 LOC total.

#### A2.2 Timing & Performance Rules (Week 2-3)

| # | Rule | Trigger Keywords | Matching Logic |
|---|------|-----------------|----------------|
| A2.2.1 | Clock frequency / bandwidth | "clock", "frequency", "bandwidth", "fmax", "speed" | Match units with `unit_of_measure` in `(Hz, kHz, MHz, GHz)` or `context` containing "clock"/"frequency". |
| A2.2.2 | Propagation delay | "propagation delay", "tpd", "delay" | Match units with `unit_of_measure` in `(ns, µs, ps)` and `context`/`label` containing "propagation"/"delay"/"tpd". |
| A2.2.3 | Rise/fall time | "rise time", "fall time", "tr", "tf", "slew" | Match units with `context`/`label` containing "rise"/"fall"/"slew" + time unit. |
| A2.2.4 | Setup/hold time | "setup time", "hold time", "tsu", "th" | Match units with `context`/`label` containing "setup"/"hold" + time unit. |

**File:** `[MOD] src/akili/verify/proof.py` — add 4 functions, ~120 LOC.

#### A2.3 Physical / Package Rules (Week 3)

| # | Rule | Trigger Keywords | Matching Logic |
|---|------|-----------------|----------------|
| A2.3.1 | Package type | "package", "package type", "footprint" | Match units/bijections with `label`/`context` containing "package"/"footprint". Also search grid headers. |
| A2.3.2 | Package dimensions | "dimensions", "package size", "length", "width", "height" | Match units with `unit_of_measure` in `(mm, mil, in)` and `context` containing "dimension"/"size"/"length"/"width". |
| A2.3.3 | Thermal resistance | "thermal resistance", "θja", "theta-ja", "rθja" | Match units with `unit_of_measure` in `(°C/W, K/W)` or `context`/`label` containing "thermal resistance"/"θja". |
| A2.3.4 | Weight | "weight", "mass" | Match units with `unit_of_measure` in `(g, mg, kg, oz)`. |
| A2.3.5 | Pin count | "pin count", "how many pins", "number of pins" | Count entries in bijection `left_set`/`right_set`, or count grid rows with pin-like data. |
| A2.3.6 | Moisture sensitivity | "moisture sensitivity", "msl", "msl rating" | Match units/grids with labels containing "MSL"/"moisture sensitivity level". |

**File:** `[MOD] src/akili/verify/proof.py` — add 6 functions, ~180 LOC.

#### A2.4 Absolute Maximum & General Rules (Week 3-4)

| # | Rule | Trigger Keywords | Matching Logic |
|---|------|-----------------|----------------|
| A2.4.1 | Absolute max voltage | "absolute max voltage", "absolute maximum voltage" | Like `_try_voltage_max` but filters units whose `context`/`label` contains "absolute maximum"/"absolute max". Falls back to existing voltage max if no absolute-specific match. |
| A2.4.2 | Absolute max current | "absolute max current", "absolute maximum current" | Same pattern for current. |
| A2.4.3 | Storage temperature | "storage temp", "storage temperature" | Match units with `context`/`label` containing "storage" + "temperature". |
| A2.4.4 | Soldering temperature | "solder", "reflow", "soldering temperature" | Match units with `context`/`label` containing "solder"/"reflow" + temperature unit. |
| A2.4.5 | Part number / ordering | "part number", "ordering", "order code", "mpn" | Match units with `label`/`context` containing "part number"/"ordering"/"MPN". Also check bijections mapping ordering codes. |
| A2.4.6 | Description / function | "what does this do", "description", "function", "what is this" | Match units with `label`/`context` containing "description"/"function"/"overview". Also look for the first grid cell in a row labeled "Description". |
| A2.4.7 | Recommended operating conditions | "recommended operating", "recommended conditions" | Scan grids for header row containing "Recommended Operating Conditions". Return all rows as structured answer. |
| A2.4.8 | Improved generic label/value fallback | (fallback) | Enhance existing `_try_unit_lookup` with fuzzy matching: normalize whitespace, case, common abbreviations (temp/temperature, volt/voltage, etc.). |
| A2.4.9 | Improved keyword-intent fallback | (fallback) | Enhance existing `_try_unit_by_intent` with broader unit-type detection (resistance, inductance, capacitance) and smarter scoring (exact label match > partial > context-only). |
| A2.4.10 | Grid cell lookup by header | "what is the {row_header} {col_header}" | New rule: parse question for row/column header references, then search grid cells by matching `grid.cells[0, :]` (header row) and `grid.cells[:, 0]` (header column). Return the intersecting cell value. |

**File:** `[MOD] src/akili/verify/proof.py` — add 10 functions, ~300 LOC.

**Tests for A2 (all rules):**
| # | Task | File | Details |
|---|------|------|---------|
| A2.T1 | Unit tests per rule | `[MOD] tests/test_verify.py` | Add 2 tests per new rule (24 rules × 2 = 48 new tests): one with matching canonical data (asserts `AnswerWithProof`), one without (asserts `None` from the rule function or `Refuse` from `verify_and_answer`). ~400 LOC. |
| A2.T2 | Priority ordering tests | `[NEW] tests/test_rule_priority.py` | Verify that specific-intent rules (e.g., absolute max voltage) fire before generic-intent rules (e.g., max voltage). ~50 LOC. |

---

### A3. Improve Extraction Prompt (Weeks 2-4)

**Goal:** Better structured extraction from Gemini = more canonical facts = higher query coverage.

| # | Task | File | Details |
|---|------|------|---------|
| A3.1 | Add few-shot examples to prompt | `[MOD] src/akili/ingest/gemini_extract.py` | Append 3 annotated JSON examples to `EXTRACT_PROMPT`: (1) a pin table page → bijections + grid, (2) an electrical characteristics table → units with min/typ/max as separate units + grid, (3) an absolute maximum ratings table → units with "absolute maximum" context. ~80 LOC of prompt additions. |
| A3.2 | Structured output schema enforcement | `[MOD] src/akili/ingest/gemini_extract.py` | The current code tries `response_mime_type="application/json"` with the full Pydantic schema but silently falls back on failure (lines 350-359). Fix: build a simplified JSON schema (without `$defs`) manually from `PageExtraction` fields. This ensures Gemini uses structured output mode when available. ~40 LOC. |
| A3.3 | Page-type classification prompt | `[NEW] src/akili/ingest/page_classifier.py` | Before extraction, send a lightweight Gemini call: "Classify this page as one of: pinout_table, electrical_specs, absolute_max_ratings, block_diagram, text_description, other." Use the classification to select a type-specific extraction prompt variant (pin-focused vs. table-focused vs. general). ~80 LOC. |
| A3.4 | Wire page classifier into pipeline | `[MOD] src/akili/ingest/pipeline.py` | After `load_pdf_pages`, call `classify_page()` for each page before `extract_page()`. Pass the classification to a new `extract_page(page_index, image_bytes, doc_id, page_type=...)` parameter. ~20 LOC. |
| A3.5 | Coordinate calibration instructions | `[MOD] src/akili/ingest/gemini_extract.py` | Add explicit examples of correct vs. incorrect bounding boxes to the prompt. E.g., "Correct: bbox covers the entire table. Incorrect: bbox covers only the header row." ~20 LOC of prompt text. |
| A3.6 | Context-enriched extraction | `[MOD] src/akili/ingest/gemini_extract.py` | Add instruction: "For every unit, include `context` describing what the value represents (e.g., 'nominal supply voltage', 'absolute maximum junction temperature', 'typical propagation delay'). This context is used for question matching." ~10 LOC. |

**Tests:**
| # | Task | File | Details |
|---|------|------|---------|
| A3.T1 | Test prompt includes few-shot examples | `[NEW] tests/test_extraction.py` | Assert `EXTRACT_PROMPT` contains the example JSON snippets. Assert the prompt mentions "pinout table", "electrical characteristics", "absolute maximum". |
| A3.T2 | Test schema simplification | `[NEW] tests/test_extraction.py` | Call the schema simplifier with `PageExtraction.model_json_schema()` and assert the output has no `$defs` key. |
| A3.T3 | Test page classifier output | `[NEW] tests/test_extraction.py` | Mock Gemini response for page classifier. Assert valid classification string returned. |

---

### A4. Test Coverage (Weeks 2-6)

**Goal:** Establish the test infrastructure that all future work builds on.

| # | Task | File | Details |
|---|------|------|---------|
| A4.1 | Ingestion pipeline integration test | `[NEW] tests/test_pipeline_integration.py` | Use a small synthetic PDF (created via `reportlab` or a fixture file). Mock `gemini_extract_page` to return a known `PageExtraction`. Assert that `ingest_document()` produces the expected canonical objects and stores them in a temp SQLite DB. ~100 LOC. |
| A4.2 | Storage layer CRUD tests | `[NEW] tests/test_store.py` | Test `Store` methods: `add_document`, `store_canonical`, `get_units_by_doc`, `get_bijections_by_doc`, `get_grids_by_doc`, `get_all_canonical_by_doc`, `delete_document`, `list_documents`. Use a temp DB per test. Test duplicate handling (`INSERT OR REPLACE`). ~150 LOC. |
| A4.3 | Verification layer exhaustive tests | `[MOD] tests/test_verify.py` | Already started in A2.T1. Add edge cases: empty strings, unicode, very long values, null labels, zero coordinates. ~50 additional LOC. |
| A4.4 | API endpoint integration tests | `[MOD] tests/test_api.py` | Use FastAPI `TestClient`. Test all endpoints: `POST /ingest` (mock Gemini), `POST /query`, `GET /documents`, `DELETE /documents/{doc_id}`, `GET /documents/{doc_id}/canonical`, `GET /documents/{doc_id}/file`, `GET /status`, `GET /health`. ~200 LOC. |
| A4.5 | Extraction quality benchmark harness | `[NEW] tests/benchmark/` | Directory structure: `tests/benchmark/datasheets/` (5 PDF files), `tests/benchmark/ground_truth/` (5 JSON files with hand-labeled facts), `tests/benchmark/run_benchmark.py` (script that runs extraction on each PDF, compares to ground truth, reports precision/recall per fact type). ~200 LOC for the harness. |
| A4.6 | CI integration | `[MOD] .github/workflows/ci.yml` | Add `pytest --cov=src/akili --cov-report=term-missing` to the test step. Add coverage threshold: fail if below 60% (Stage A target). |
| A4.7 | Test fixtures module | `[NEW] tests/conftest.py` | Shared pytest fixtures: `tmp_store` (temp SQLite Store), `sample_units` / `sample_bijections` / `sample_grids` (canonical objects for testing), `mock_gemini` (monkeypatch for Gemini API calls). ~80 LOC. |

**Dependencies:** A4.1 depends on A4.7. A4.4 depends on A4.7. All other A4 tasks are independent.

---

### A5. Confidence Scoring (Weeks 4-6)

**Goal:** Replace binary VERIFIED/REFUSED with a three-component confidence score.

| # | Task | File | Details |
|---|------|------|---------|
| A5.1 | Define confidence model | `[MOD] src/akili/verify/models.py` | Add `ConfidenceScore` Pydantic model: `extraction_agreement: float` (0-1), `canonical_validation: float` (0-1), `verification_strength: float` (0-1), `overall: float` (weighted average). Add `confidence` field to `AnswerWithProof`. ~30 LOC. |
| A5.2 | Compute verification strength | `[MOD] src/akili/verify/proof.py` | Each rule returns a `verification_strength` score: exact structured match (unit_of_measure + numeric value) = 1.0, parsed from text = 0.7, keyword overlap only = 0.4. Propagate into `AnswerWithProof.confidence`. ~40 LOC. |
| A5.3 | Compute canonical validation score | `[MOD] src/akili/ingest/canonicalize.py` | During canonicalization, score each fact: has bbox = +0.2, has origin = +0.3, has unit_of_measure = +0.2, has label = +0.15, has context = +0.15. Store score on canonical objects. ~30 LOC. |
| A5.4 | Add `canonical_quality` to canonical models | `[MOD] src/akili/canonical/models.py` | Add optional `quality_score: float | None` field to `Unit`, `Bijection`, `Grid`. ~10 LOC. |
| A5.5 | Persist quality score in DB | `[MOD] src/akili/store/repository.py` | Add `quality_score REAL` column to `units`, `bijections`, `grids` tables. Migration + read/write. ~30 LOC. |
| A5.6 | Threshold-based status classification | `[MOD] src/akili/verify/proof.py` | After computing overall confidence: >= 0.85 -> VERIFIED, 0.50-0.85 -> REVIEW, < 0.50 -> REFUSED. Return a `status` field: `"verified"`, `"review"`, or `"refused"`. Thresholds read from env vars `AKILI_VERIFY_THRESHOLD` and `AKILI_REVIEW_THRESHOLD`. ~25 LOC. |
| A5.7 | API response includes confidence | `[MOD] src/akili/api/app.py` | Include `confidence` object and `status` in `/query` response JSON. ~10 LOC. |
| A5.8 | Frontend: render confidence tiers | `[MOD] frontend/src/components/SidebarRight.tsx` | Green for verified, yellow for review, red for refused. Show confidence breakdown on hover/click. ~40 LOC. |

**Tests:**
| # | Task | File | Details |
|---|------|------|---------|
| A5.T1 | Test confidence computation | `[NEW] tests/test_confidence.py` | Test that exact structured matches produce confidence >= 0.85. Test that weak keyword matches produce 0.50-0.85. Test that no-match produces overall < 0.50. ~60 LOC. |
| A5.T2 | Test threshold configurability | `[NEW] tests/test_confidence.py` | Monkeypatch env vars, assert classification changes. ~20 LOC. |

**Dependencies:** A5.1 before A5.2-A5.7. A5.3-A5.4 before A5.5. A5.2 + A5.3 before A5.6. A5.6 before A5.7-A5.8.

---

### Stage A Success Gate

**Automated benchmark test** (`tests/benchmark/run_benchmark.py`):
- 10 real datasheets with hand-labeled ground truth
- For each of the 30 query types, run against each datasheet
- Assert: >= 70% of queries return `VERIFIED` with correct answer
- Assert: 0% false-accepts (verified but wrong)
- Assert: refused queries have correct refusal (no false-refuses for facts that are present)

---

## Stage B: Harden for a Pilot (Months 3-5) — COMPLETED

### B1. Consensus Extraction (Month 3)

| # | Task | File | Details |
|---|------|------|---------|
| B1.1 | Dual-extraction caller | `[NEW] src/akili/ingest/consensus.py` | New module: `consensus_extract_page(page_index, image_bytes, doc_id) -> (PageExtraction, agreement_score)`. Calls `extract_page` twice with two prompt variants (precision-focused, recall-focused). Compares the two `PageExtraction` results. ~120 LOC. |
| B1.2 | Comparison logic | `[MOD] src/akili/ingest/consensus.py` | For each fact type: units matched by (label similarity + value equality + location proximity). Bijections matched by set overlap. Grids matched by cell-value overlap. Agreement facts accepted; disagreement facts flagged. ~100 LOC. |
| B1.3 | Third-pass tiebreaker | `[MOD] src/akili/ingest/consensus.py` | On disagreement: run a third extraction with a prompt: "Two extractions disagree on [specific fact]. The page shows [image]. Which extraction is correct?" Accept the tiebreaker result. ~50 LOC. |
| B1.4 | Selective consensus for high-risk facts | `[MOD] src/akili/ingest/pipeline.py` | Run consensus extraction only for pages classified as `electrical_specs` or `absolute_max_ratings` (from A3.3). Other page types use single extraction. Configurable via `AKILI_CONSENSUS_ENABLED=1`. ~20 LOC. |
| B1.5 | Wire `extraction_agreement` into confidence | `[MOD] src/akili/verify/proof.py` | Use the agreement score from consensus as the `extraction_agreement` component of the confidence score. Single-extraction defaults to 0.5. ~10 LOC. |

**Tests:**
| # | Task | File | Details |
|---|------|------|---------|
| B1.T1 | Test agreement detection | `[NEW] tests/test_consensus.py` | Two identical extractions -> agreement 1.0. Two completely different -> agreement 0.0. Partial overlap -> proportional. ~80 LOC. |

---

### B2. Extended Canonical Model (Month 3-4)

| # | Task | File | Details |
|---|------|------|---------|
| B2.1 | Add `Range` model | `[MOD] src/akili/canonical/models.py` | New class: `Range(BaseModel)` with fields: `id`, `label`, `min: float | None`, `typ: float | None`, `max: float | None`, `unit: str`, `conditions: str | None`, `origin`, `doc_id`, `page`, `bbox`. ~25 LOC. |
| B2.2 | Add `ConditionalUnit` model | `[MOD] src/akili/canonical/models.py` | New class: `ConditionalUnit(BaseModel)` with fields: `id`, `value: float`, `unit: str`, `condition_type: str`, `condition_value: str`, `derating: str | None`, `origin`, `doc_id`, `page`, `bbox`. ~25 LOC. |
| B2.3 | DB schema for Range + ConditionalUnit | `[MOD] src/akili/store/repository.py` | Add `ranges` table: `id, doc_id, page, range_id, label, min_val, typ_val, max_val, unit, conditions, quality_score, origin_json, bbox_json`. Add `conditional_units` table: similar. Migration logic. ~80 LOC. |
| B2.4 | CRUD for new types | `[MOD] src/akili/store/repository.py` | `store_canonical` handles Range and ConditionalUnit. Add `get_ranges_by_doc`, `get_conditional_units_by_doc`. ~80 LOC. |
| B2.5 | Extraction schema for Range | `[MOD] src/akili/ingest/extract_schema.py` | Add `RangeExtract` Pydantic model. Add `ranges` field to `PageExtraction`. ~20 LOC. |
| B2.6 | Extraction prompt for min/typ/max | `[MOD] src/akili/ingest/gemini_extract.py` | Update `EXTRACT_PROMPT` to instruct Gemini to extract min/typ/max tables as `ranges` (not just units). Add example. ~30 LOC. |
| B2.7 | Canonicalize ranges | `[MOD] src/akili/ingest/canonicalize.py` | Convert `RangeExtract` to `Range` canonical objects. ~30 LOC. |
| B2.8 | Verification rules for Range | `[MOD] src/akili/verify/proof.py` | Update rules to search `Range` objects when answering questions about min/typ/max specs. E.g., "What is the typical propagation delay?" should match `Range.typ`. ~60 LOC. |
| B2.9 | Wire into verify_and_answer | `[MOD] src/akili/verify/proof.py` | Add `ranges: list[Range]` and `conditional_units: list[ConditionalUnit]` parameters to `verify_and_answer`. Update API to pass them. ~20 LOC. |

**Dependencies:** B2.1-B2.2 before B2.3-B2.9. B2.5 before B2.6-B2.7.

---

### B3. Basic Z3 Integration (Month 4)

| # | Task | File | Details |
|---|------|------|---------|
| B3.1 | Z3 unit normalization module | `[NEW] src/akili/verify/z3_checks.py` | Functions: `check_unit_consistency(units: list[Unit]) -> list[Contradiction]`. Uses Z3 `Real` variables. Assert `4.2V == 4200mV == 0.0042kV`. Build unit conversion table for V/mV/kV, A/mA/µA, Hz/kHz/MHz/GHz, °C/K, W/mW. ~100 LOC. |
| B3.2 | Z3 contradiction detection | `[MOD] src/akili/verify/z3_checks.py` | Function: `detect_contradictions(units: list[Unit], ranges: list[Range]) -> list[Contradiction]`. For each pair of facts with the same label/context from different pages, assert they don't contradict. E.g., max voltage on page 3 = 5.5V, absolute max on page 7 = 5.0V -> contradiction. ~80 LOC. |
| B3.3 | Z3 range consistency | `[MOD] src/akili/verify/z3_checks.py` | Function: `check_range_consistency(ranges: list[Range]) -> list[Contradiction]`. Assert min <= typ <= max for every Range object. ~30 LOC. |
| B3.4 | Contradiction model | `[MOD] src/akili/verify/models.py` | New class: `Contradiction(BaseModel)` with fields: `fact_a_id`, `fact_b_id`, `description`, `severity: str` (warning/error). ~15 LOC. |
| B3.5 | Run Z3 checks post-ingestion | `[MOD] src/akili/ingest/pipeline.py` | After canonicalization, run Z3 checks. Store contradictions. Log warnings. ~20 LOC. |
| B3.6 | API endpoint for contradictions | `[MOD] src/akili/api/app.py` | `GET /documents/{doc_id}/contradictions` returns Z3-detected contradictions. ~20 LOC. |
| B3.7 | Conditional import (Z3 optional) | `[MOD] src/akili/verify/z3_checks.py` | Z3 is an optional dependency (`[verify]` extra). Import with try/except. If unavailable, checks return empty lists. ~10 LOC. |

**Tests:**
| # | Task | File | Details |
|---|------|------|---------|
| B3.T1 | Test unit normalization | `[NEW] tests/test_z3_checks.py` | 4.2V and 4200mV should not contradict. 4.2V and 5.0V with same label should contradict. ~40 LOC. |
| B3.T2 | Test range consistency | `[NEW] tests/test_z3_checks.py` | Range(min=1, typ=3, max=2) should flag inconsistency. Range(min=1, typ=2, max=3) should pass. ~30 LOC. |

---

### B4. PostgreSQL Migration (Month 4-5)

| # | Task | File | Details |
|---|------|------|---------|
| B4.1 | Abstract storage interface | `[NEW] src/akili/store/base.py` | Define `AbstractStore` (Protocol or ABC) with all methods from current `Store`. This enables SQLite and PostgreSQL backends. ~40 LOC. |
| B4.2 | Rename current Store | `[MOD] src/akili/store/repository.py` | Rename `Store` to `SQLiteStore(AbstractStore)`. Keep all logic. ~5 LOC rename. |
| B4.3 | PostgreSQL store implementation | `[NEW] src/akili/store/postgres.py` | `PostgresStore(AbstractStore)` using `asyncpg` or `psycopg2`. Multi-tenant schema with `org_id` column on all tables. Connection pooling. ~250 LOC. |
| B4.4 | Audit log table | `[MOD] src/akili/store/postgres.py` | Immutable `audit_log` table: `id, org_id, user_id, action, doc_id, timestamp, details_json`. Written on ingest, delete, query. ~40 LOC. |
| B4.5 | Migration scripts | `[NEW] scripts/migrate_sqlite_to_postgres.py` | Read all data from SQLite, write to PostgreSQL. Verify row counts match. ~80 LOC. |
| B4.6 | Store factory | `[MOD] src/akili/api/app.py` | `get_store()` reads `AKILI_DB_BACKEND` env var: `"sqlite"` (default) or `"postgres"`. Constructs appropriate store. ~15 LOC. |
| B4.7 | Add psycopg2 dependency | `[MOD] pyproject.toml` | Add `[project.optional-dependencies] postgres = ["psycopg2-binary>=2.9"]`. |
| B4.8 | Docker Compose with Postgres | `[MOD] docker-compose.yml` | Add `postgres` service. Update `api` service to connect to Postgres. Add volume for Postgres data. ~30 LOC. |

---

### B5. Human-in-the-Loop Review UI (Month 5)

| # | Task | File | Details |
|---|------|------|---------|
| B5.1 | Corrections table | `[MOD] src/akili/store/repository.py` (and `postgres.py`) | New table `corrections`: `id, doc_id, fact_id, fact_type, original_value, corrected_value, corrected_by, created_at, original_extraction_json`. ~30 LOC per store implementation. |
| B5.2 | Corrections API | `[MOD] src/akili/api/app.py` | `POST /documents/{doc_id}/corrections` — submit a correction. `GET /documents/{doc_id}/corrections` — list corrections. ~40 LOC. |
| B5.3 | Review queue API | `[MOD] src/akili/api/app.py` | `GET /documents/{doc_id}/review-queue` — returns all facts with confidence in REVIEW band (0.50-0.85), with PDF bounding box data for overlay. ~30 LOC. |
| B5.4 | Frontend: Review panel | `[NEW] frontend/src/components/ReviewPanel.tsx` | Display REVIEW-band facts alongside PDF region. Buttons: CONFIRM (promotes to VERIFIED) and CORRECT (opens inline edit). ~150 LOC. |
| B5.5 | Frontend: Correction form | `[MOD] frontend/src/components/ReviewPanel.tsx` | Inline form: show original value, input for corrected value, submit button. On submit, calls `POST /corrections`. ~50 LOC. |
| B5.6 | Apply corrections to store | `[MOD] src/akili/store/repository.py` | `apply_correction(correction_id)` — updates the canonical fact's value in the DB and marks it as `human_verified=True`. ~30 LOC. |

---

## Stage C: Deepen the Reasoning (Months 5-8) — COMPLETED

### C1. Derived Query MVP (Month 5-6)

| # | Task | File | Details |
|---|------|------|---------|
| C1.1 | Derivation engine | `[NEW] src/akili/verify/derived.py` | Module for computed answers. Each derivation is a function: `(units, ranges, grids) -> DerivedAnswer | None`. `DerivedAnswer` includes the result, formula used, and all source fact IDs for the proof chain. ~150 LOC. |
| C1.2 | Power dissipation derivation | `[MOD] src/akili/verify/derived.py` | P = V × I. Find voltage and current facts, compute product, return with full proof chain showing both source facts. Z3 verifies the arithmetic. ~40 LOC. |
| C1.3 | Thermal check derivation | `[MOD] src/akili/verify/derived.py` | T_junction = T_ambient + (P × θ_JA). Requires power dissipation (from C1.2 or direct fact) and thermal resistance. ~40 LOC. |
| C1.4 | Voltage margin derivation | `[MOD] src/akili/verify/derived.py` | margin = (V_abs_max - V_operating) / V_abs_max × 100%. ~30 LOC. |
| C1.5 | Wire derived queries into verify_and_answer | `[MOD] src/akili/verify/proof.py` | After all direct-lookup rules fail, try derived query rules before returning REFUSE. ~15 LOC. |
| C1.6 | Proof chain model | `[MOD] src/akili/verify/models.py` | Add `ProofChain(BaseModel)`: `steps: list[ProofStep]` where `ProofStep` has `description`, `formula`, `source_facts: list[ProofPoint]`, `result`. ~25 LOC. |

### C2. Multi-Page Table Handling (Month 6-7)

| # | Task | File | Details |
|---|------|------|---------|
| C2.1 | Table boundary detection | `[NEW] src/akili/ingest/table_merge.py` | Detect when a grid on page N is a continuation of a grid on page N-1: repeated header, matching column count, last row on page N-1 looks truncated. ~80 LOC. |
| C2.2 | Cross-page grid merger | `[MOD] src/akili/ingest/table_merge.py` | Merge two `Grid` objects: concatenate rows from page N+1 onto page N's grid. Update cell origins. Flag merged grid for review. ~60 LOC. |
| C2.3 | Wire into pipeline | `[MOD] src/akili/ingest/pipeline.py` | After all pages are extracted, run table merge across consecutive pages. ~15 LOC. |

### C3. Cross-Document Queries (Month 7-8)

| # | Task | File | Details |
|---|------|------|---------|
| C3.1 | Multi-doc query API | `[MOD] src/akili/api/app.py` | `POST /query/compare` — accepts `doc_ids: list[str]` and `question: str`. Runs `verify_and_answer` per document, returns comparative results. ~40 LOC. |
| C3.2 | Comparison logic | `[NEW] src/akili/verify/compare.py` | Given answers from multiple documents for the same question, produce a comparison table: `[{doc_id, answer, confidence, proof}]`. Sort by value for numeric answers. ~50 LOC. |
| C3.3 | Frontend: comparison view | `[NEW] frontend/src/components/CompareView.tsx` | Side-by-side table of answers from selected documents. ~100 LOC. |

### C4. Correction Tracking and Simple Learning (Month 7-8)

| # | Task | File | Details |
|---|------|------|---------|
| C4.1 | Correction pattern analyzer | `[NEW] src/akili/learn/patterns.py` | Analyze the corrections table for systematic errors. Group by: manufacturer (from document metadata), fact type (label pattern), page position. Identify patterns where Gemini consistently misreads. ~100 LOC. |
| C4.2 | Auto-correction rules | `[MOD] src/akili/ingest/canonicalize.py` | If a new extraction matches a known error pattern (from C4.1), either auto-correct or flag for review with the correction suggestion. ~40 LOC. |
| C4.3 | Correction dashboard API | `[MOD] src/akili/api/app.py` | `GET /analytics/corrections` — returns correction patterns, frequency, and auto-correction hit rate. ~30 LOC. |

---

## Stage D: Enterprise Readiness (Months 8-12)

### D1. Security & Compliance

| # | Task | File | Details |
|---|------|------|---------|
| D1.1 | RBAC middleware | `[NEW] src/akili/api/rbac.py` | Role-based access: `admin`, `engineer`, `viewer`. Check role on each endpoint. Roles stored in auth token claims. ~80 LOC. |
| D1.2 | Encryption at rest | `[MOD] src/akili/store/postgres.py` | Enable PostgreSQL TDE or application-level encryption for sensitive document content. ~30 LOC config. |
| D1.3 | Audit trail completeness | `[MOD] src/akili/store/postgres.py` | Ensure every state-changing API call writes to `audit_log`. Add read-audit for sensitive queries. ~40 LOC. |
| D1.4 | Key management | `[NEW] src/akili/config/secrets.py` | Use `AKILI_SECRETS_BACKEND` to select: env vars (default), AWS Secrets Manager, or HashiCorp Vault. ~60 LOC. |

### D2. LLM Abstraction Layer

| # | Task | File | Details |
|---|------|------|---------|
| D2.1 | LLM provider interface | `[NEW] src/akili/llm/base.py` | Abstract `LLMProvider` protocol: `extract(image_bytes, prompt) -> str`, `format(prompt) -> str`, `classify(image_bytes, prompt) -> str`. ~30 LOC. |
| D2.2 | Gemini provider | `[NEW] src/akili/llm/gemini.py` | Move Gemini-specific code from `gemini_extract.py` and `gemini_format.py` into `GeminiProvider(LLMProvider)`. ~100 LOC refactor. |
| D2.3 | OpenAI/Claude provider stubs | `[NEW] src/akili/llm/openai.py`, `[NEW] src/akili/llm/anthropic.py` | Implement `LLMProvider` for GPT-4V and Claude. ~80 LOC each. |
| D2.4 | Provider factory | `[NEW] src/akili/llm/__init__.py` | `get_provider(name: str) -> LLMProvider`. Read from `AKILI_LLM_PROVIDER` env var. Default: `"gemini"`. ~20 LOC. |
| D2.5 | Wire provider into pipeline | `[MOD] src/akili/ingest/gemini_extract.py`, `[MOD] src/akili/ingest/gemini_format.py` | Replace direct Gemini calls with `get_provider().extract(...)` and `get_provider().format(...)`. ~30 LOC total. |

### D3. Deployment & Integrations

| # | Task | File | Details |
|---|------|------|---------|
| D3.1 | Kubernetes manifests | `[NEW] k8s/` | Deployment, Service, Ingress, ConfigMap, Secret for API and frontend. ~200 LOC YAML. |
| D3.2 | EDA integration (Altium or KiCad) | `[NEW] src/akili/integrations/eda.py` | Plugin that queries AKILI from within EDA tool. Start with KiCad (open source). Export BOM -> query each component's specs. ~150 LOC. |
| D3.3 | Workflow integration (JIRA or Confluence) | `[NEW] src/akili/integrations/jira.py` | JIRA Cloud webhook: on component selection, auto-query AKILI for key specs and post as comment. ~100 LOC. |

---

## Parallel R&D: ART Exploration (Month 6-10)

| # | Task | File | Details |
|---|------|------|---------|
| R1 | ART vigilance prototype | `[NEW] src/akili/research/art_vigilance.py` | Implement vigilance gating as a calibrated acceptance threshold using correction data. Test offline against labeled datasets. ~200 LOC. |
| R2 | Fuzzy ART for template recognition | `[NEW] src/akili/research/fuzzy_art.py` | Prototype: cluster document pages by extraction structure. Goal: distinguish TI datasheets from Analog Devices datasheets. ~250 LOC. |
| R3 | ART evaluation harness | `[NEW] src/akili/research/evaluate_art.py` | Compare ART-based template learning vs. manufacturer-specific prompt templates (baseline). Measure refusal precision/recall improvement. ~100 LOC. |
| R4 | Go/No-Go at Month 10 | N/A | If ART shows statistically significant lift, integrate into main product via the confidence scoring system. If not, archive. |

---

## Dependency Graph (Critical Path)

```
Week 1:  A1 (Shadow Fix) ──────────────────────────────────────────────┐
Week 1:  A2.0 (Rule Registry) ─┬─ A2.1 (Electrical) ──┬─ A2.2 (Timing)─┤
Week 2:  A3 (Prompt) ──────────┤                       │                │
Week 2:  A4.7 (Fixtures) ──────┼─ A4.1-A4.4 (Tests) ──┤                │
Week 4:  A5 (Confidence) ──────┤                       │                │
         ──────────────────────────── Stage A Gate ─────┘                │
Month 3: B1 (Consensus) ──┐                                            │
Month 3: B2 (Range/Cond.) ┼── B3 (Z3) ── B4 (Postgres) ── B5 (HITL) ─┘
         ────────────────────────────── Stage B Gate ───────────────────┘
Month 5: C1 (Derived) ── C2 (Multi-page) ── C3 (Cross-doc) ── C4 (Learning)
         ────────────────────────────── Stage C Gate ───────────────────
Month 8: D1-D3 (Enterprise)
         ────────────────────────────── Stage D Gate ───────────────────
```

---

## 30-Day Sprint Breakdown (What to Build First)

### Week 1 (Days 1-7)
| Day | Task | Deliverable |
|-----|------|------------|
| 1-2 | A1.2, A1.3 | Shadow formatting fix: refusals no longer auto-reformatted. Response includes `formatting_source`. |
| 2-3 | A2.0.1, A2.0.2 | Rule registry refactor + matchers module extracted. All existing tests still pass. |
| 3-5 | A2.1.1 - A2.1.6 | 6 new electrical characteristics rules added. |
| 5-7 | A4.7, A1.T1, A1.T2 | Test fixtures module. Shadow formatting tests. |

### Week 2 (Days 8-14)
| Day | Task | Deliverable |
|-----|------|------------|
| 8-10 | A2.2.1 - A2.2.4 | 4 timing rules added. |
| 10-12 | A3.1, A3.5, A3.6 | Few-shot examples + coordinate calibration + context enrichment in extraction prompt. |
| 12-14 | A4.1, A4.2 | Pipeline integration test + store CRUD tests. |

### Week 3 (Days 15-21)
| Day | Task | Deliverable |
|-----|------|------------|
| 15-17 | A2.3.1 - A2.3.6 | 6 physical/package rules. |
| 17-19 | A2.4.1 - A2.4.6 | 6 absolute max + general rules. |
| 19-21 | A2.4.7 - A2.4.10, A2.T1 | 4 remaining rules + unit tests for all new rules. |

### Week 4 (Days 22-28)
| Day | Task | Deliverable |
|-----|------|------------|
| 22-24 | A4.5, A3.2 | Benchmark harness + structured schema enforcement. |
| 24-26 | A5.1 - A5.3 | Confidence model + verification strength + canonical validation scoring. |
| 26-28 | A5.6, A5.7, A4.6 | Threshold classification + API response + CI coverage threshold. |

### Week 4 Checkpoint
Run benchmark: `python tests/benchmark/run_benchmark.py`
- Target: >= 15/30 query types return VERIFIED on benchmark set
- If met: proceed to weeks 5-8 (remaining A5 work, then Stage B)
- If not met: continue expanding rules and improving extraction prompt

---

## New Dependencies to Add

```toml
# pyproject.toml additions
[project.optional-dependencies]
postgres = ["psycopg2-binary>=2.9"]
verify = ["z3-solver>=4.12"]
dev = ["pytest>=7", "pytest-cov", "pytest-asyncio", "ruff", "flake8", "flake8-pyproject", "httpx"]
benchmark = ["reportlab>=4.0"]
```

---

## New Files Summary

| File | Stage | Purpose |
|------|-------|---------|
| `src/akili/verify/matchers.py` | A | Shared regex patterns and parsers |
| `src/akili/ingest/page_classifier.py` | A | Page type classification |
| `src/akili/ingest/consensus.py` | B | Dual/triple extraction consensus |
| `src/akili/verify/z3_checks.py` | B | Z3 unit/contradiction/range checks |
| `src/akili/verify/derived.py` | C | Derived query engine |
| `src/akili/verify/compare.py` | C | Cross-document comparison |
| `src/akili/ingest/table_merge.py` | C | Multi-page table merging |
| `src/akili/learn/patterns.py` | C | Correction pattern analysis |
| `src/akili/store/base.py` | B | Abstract store interface |
| `src/akili/store/postgres.py` | B | PostgreSQL store implementation |
| `src/akili/llm/base.py` | D | LLM provider abstraction |
| `src/akili/llm/gemini.py` | D | Gemini provider |
| `src/akili/llm/openai.py` | D | OpenAI provider |
| `src/akili/llm/anthropic.py` | D | Anthropic provider |
| `src/akili/api/rbac.py` | D | Role-based access control |
| `src/akili/config/secrets.py` | D | Secret management |
| `src/akili/integrations/eda.py` | D | EDA tool integration |
| `src/akili/integrations/jira.py` | D | JIRA integration |
| `src/akili/research/art_vigilance.py` | R&D | ART vigilance prototype |
| `src/akili/research/fuzzy_art.py` | R&D | Fuzzy ART clustering |
| `src/akili/research/evaluate_art.py` | R&D | ART evaluation harness |
| `tests/conftest.py` | A | Shared test fixtures |
| `tests/test_store.py` | A | Store CRUD tests |
| `tests/test_rule_priority.py` | A | Rule ordering tests |
| `tests/test_extraction.py` | A | Extraction prompt tests |
| `tests/test_confidence.py` | A | Confidence scoring tests |
| `tests/test_pipeline_integration.py` | A | Pipeline integration tests |
| `tests/test_consensus.py` | B | Consensus extraction tests |
| `tests/test_z3_checks.py` | B | Z3 verification tests |
| `tests/benchmark/run_benchmark.py` | A | Benchmark harness |
| `frontend/src/components/ReviewPanel.tsx` | B | Review/correction UI |
| `frontend/src/components/CompareView.tsx` | C | Cross-doc comparison UI |
| `scripts/migrate_sqlite_to_postgres.py` | B | SQLite -> Postgres migration |

---

## Modified Files Summary

| File | Stages | Key Changes |
|------|--------|-------------|
| `src/akili/verify/proof.py` | A, B, C | Rule registry, 24 new rules, Range/ConditionalUnit support, derived queries |
| `src/akili/verify/models.py` | A, B, C | ConfidenceScore, Contradiction, ProofChain models |
| `src/akili/canonical/models.py` | A, B | quality_score field, Range, ConditionalUnit classes |
| `src/akili/ingest/gemini_extract.py` | A, B | Few-shot examples, structured schema, page_type, context enrichment |
| `src/akili/ingest/extract_schema.py` | B | RangeExtract model |
| `src/akili/ingest/canonicalize.py` | A, B, C | Quality scoring, Range canonicalization, auto-correction |
| `src/akili/ingest/pipeline.py` | A, B, C | Page classifier, consensus, Z3 post-checks, table merge |
| `src/akili/store/repository.py` | A, B | quality_score columns, Range/ConditionalUnit tables, corrections table |
| `src/akili/api/app.py` | A, B, C, D | Shadow format fix, confidence in response, corrections API, compare API, RBAC, store factory |
| `pyproject.toml` | A, B, D | New dependencies |
| `docker-compose.yml` | B | PostgreSQL service |
| `.github/workflows/ci.yml` | A | Coverage threshold |
| `tests/test_verify.py` | A | 48+ new tests |
| `tests/test_api.py` | A | API integration tests |
| `frontend/src/components/SidebarRight.tsx` | A, B | Confidence tiers, formatting labels |
| `frontend/src/types.ts` | A | New response fields |

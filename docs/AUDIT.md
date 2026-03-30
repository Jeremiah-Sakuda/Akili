# Akili — Full Repository Audit

**Date:** February 2026 (updated)  
**Scope:** README/goals alignment, architecture, security, CI/CD, docs, and gaps.

---

## 1. Goals vs. Implementation

### 1.1 Core Pillars (README)

| Pillar | Status | Notes |
|--------|--------|--------|
| **Structural canonicalization** | Done | Unit, Bijection, Grid in Pydantic; canonicalize rejects invalid/ambiguous; store persists only validated objects. |
| **Coordinate-level grounding** | Done | Every answer includes proof with `(x, y, page)`; ProofPoint has page for overlay. |
| **Deterministic refusal** | Done | `verify_and_answer` returns Refuse when no rule derives the answer; rule order is fixed via priority registry. |
| **Confidence scoring** | Done | Three-component `ConfidenceScore` (extraction_agreement, canonical_validation, verification_strength) with VERIFIED / REVIEW / REFUSED tiers. |

### 1.2 Tech Stack (README)

| Layer | README | Implementation |
|-------|--------|----------------|
| Runtime | Python 3.11+ | pyproject.toml `requires-python = ">=3.11"`; CI matrix 3.11, 3.12. |
| LLM / Vision | Google Gemini | `google-generativeai`; `gemini_extract.py` uses `gemini-3-pro-preview` (default) for ingest; `gemini_format.py` for Shadow Formatting (opt-in, labeled). |
| Canonical model | Pydantic v2 | `canonical/models.py`; extract_schema + canonicalize. |
| Document processing | PyMuPDF | `pdf_loader.py` uses PyMuPDF (fitz) at 150 DPI. |
| Store | SQLite (MVP) | `store/repository.py`; SQLite only; PostgreSQL planned for Stage B. |
| Verification | Rule-based (30 rules) | `verify/proof.py` — priority-ordered `@rule` registry with 30 rules covering electrical, timing, physical, absolute max, and general queries. `verify/matchers.py` centralizes regex patterns. |
| Confidence | Three-component | `verify/models.py` — `ConfidenceScore` with configurable VERIFIED/REVIEW/REFUSED thresholds. |
| API | FastAPI | `api/app.py`; all stated endpoints including confidence_tier and formatting_source in responses. |
| Frontend | React + TypeScript + Vite + Tailwind | Three-pane workspace; PDF viewer with proof overlay; color-coded confidence badges; "AI-rephrased" label for Shadow Formatting. |

### 1.3 API Surface

| Endpoint | README / ARCHITECTURE | Status |
|----------|------------------------|--------|
| POST /ingest | Yes | Implemented; PDF stored under `docs/`; max size via AKILI_MAX_UPLOAD_BYTES. |
| POST /ingest/stream | Yes | Implemented; SSE progress events. |
| POST /query | Yes | Implemented; returns answer + proof + confidence + formatting_source, or REFUSE. `include_formatted_answer` defaults to false. |
| GET /documents | Yes | Implemented. |
| GET /documents/{id}/canonical | Yes | Implemented; doc_id validated. |
| GET /documents/{id}/file | Yes | Implemented; serves stored PDF. |
| DELETE /documents/{id} | Yes | Implemented. |
| GET /status, /health | Yes | Implemented; public (no auth). |

### 1.4 Shadow Formatting (A1 Fix)

| Aspect | Before | After |
|--------|--------|-------|
| Default behavior | Gemini rephrase on by default | Raw verified answer by default |
| API flag | `include_formatted_answer: true` enabled rephrasing | Same flag, but defaults to `false` |
| Response metadata | No source indicator | `formatting_source: "verified_raw"` or `"gemini_rephrase"` |
| Frontend display | No distinction | "AI-rephrased" badge when Gemini-formatted |

### 1.5 Verification Layer (A2 Expansion)

| Aspect | Before | After |
|--------|--------|-------|
| Rule count | 6 hardcoded if-else matchers | 30 rules via `@rule(priority)` registry |
| Architecture | Sequential if-else in single function | Decorator-based registry; priority-sorted execution |
| Pattern library | Inline regex | Centralized in `verify/matchers.py` |
| Test coverage | 7 basic tests | 46 targeted tests across 16 test classes |

### 1.6 Test Coverage (A4 Expansion)

| Aspect | Before | After |
|--------|--------|-------|
| Total tests | ~11 | 81 |
| Verification tests | 7 | 46 |
| Storage tests | 0 | 13 |
| Confidence tests | 0 | 11 |
| API tests | 4 | 6 |
| Shared fixtures | None | `conftest.py` with ~30 sample units, bijections, grids, temp store |

---

## 2. Security

### 2.1 In Place

- **CORS:** Configurable via `AKILI_CORS_ORIGINS`; default localhost only.
- **API auth:** Optional Firebase ID token; `AKILI_REQUIRE_AUTH` + `FIREBASE_PROJECT_ID`; `firebase-admin` optional dep `.[auth]`; ImportError handled.
- **Upload limit:** `AKILI_MAX_UPLOAD_BYTES` (default 100 MB); 413 when exceeded.
- **doc_id validation:** `_validate_doc_id` allows only `[a-zA-Z0-9_-]`; no path traversal.
- **SQL:** Parameterized queries only in repository; no injection risk.
- **Secrets:** `.env` in `.gitignore`; no backend keys in frontend build.
- **Health/status:** Unauthenticated for load balancers and checks.
- **Debug gating:** Error detail gated on `AKILI_DEBUG`; generic messages in production.
- **401 handling:** Frontend signs out and shows login on 401.

### 2.2 Recommendations (Open)

- **Rate limiting:** No rate limit on /ingest or /query; consider per-IP or per-user limits when auth is enabled to protect Gemini quota.

---

## 3. Backend Code Quality

- **Lint/format:** CI runs Ruff (check + format) and Flake8; pyproject has ruff and flake8 config.
- **Tests:** 81 passing tests across 5 files; shared fixtures in `conftest.py`.
- **Verification:** 30 rules in priority registry with centralized matchers; each rule independently testable.
- **Confidence:** Three-component scoring with configurable thresholds and per-answer tier classification.
- **Store:** Single global Store; no connection pooling (fine for SQLite MVP).

---

## 4. Frontend

- **Stack:** React, TypeScript, Vite, Tailwind; Firebase optional; pdfjs-dist for viewer.
- **API client:** All requests use `authHeaders()` (Bearer when signed in); endpoints aligned with backend.
- **PDF viewer:** Loads via `getDocumentFile`; worker via `?url`; proof overlay on answer.
- **Confidence display:** Color-coded badges (green = VERIFIED, yellow = REVIEW, red = REFUSED) with percentage.
- **Formatting transparency:** "AI-rephrased" badge when `formatting_source === "gemini_rephrase"`.
- **CI:** Build uses empty VITE_* env vars.

---

## 5. CI/CD

| Workflow | Trigger | Jobs |
|----------|---------|------|
| **CI** | push/PR to main, master, develop | Backend: Python 3.11/3.12, pip install -e ".[dev]", Ruff, Flake8, pytest, coverage; Frontend: npm ci, lint, typecheck, build. |

- **Deploy:** Deploy workflow removed; only CI runs. Add a deploy workflow when ready.

---

## 6. Docker

- **Compose:** `api` (port 8000) + `frontend` (3001→3000); `.env` and `AKILI_DB_PATH=/data/akili.db`; volume `akili-data` for `/data` (DB + docs).
- **Frontend:** Proxy target `http://api:8000`.
- **Healthcheck:** API checked via request to `/docs`.

---

## 7. Documentation

| Document | Status | Notes |
|----------|--------|-------|
| **README.md** | Updated | Reflects 30 rules, confidence scoring, shadow formatting fix, 81 tests, current project structure and roadmap. |
| **ARCHITECTURE.md** | Updated | Rule registry pattern, matchers module, confidence scoring, shadow formatting design, query response shapes. |
| **INGEST-FLOW.md** | Current | Accurate engineer-level ingest walkthrough with code references. |
| **UI-SPEC.md** | Mostly current | Minor gaps: "Locate" link per canonical row not implemented; proof legend with type-colored swatches not implemented; confidence tier badges not in spec (but implemented). |
| **UX-DESIGN-BRIEF.md** | Current | Design principles and flows remain accurate. Doesn't cover confidence tiers or formatting transparency (implemented features beyond original brief). |
| **TECHNICAL-EXECUTION-PLAN.md** | Current | Stage A tasks marked complete; Stages B–D planned. |

---

## 8. Summary

| Area | Verdict |
|------|---------|
| **Goals** | All four pillars implemented: canonicalization, coordinate grounding, deterministic refusal, confidence scoring. 30 verification rules cover the 25+ most common EE query types. |
| **Security** | Auth and CORS configurable; upload limit; doc_id validated; debug gating; no key leakage; rate limiting recommended. |
| **Testing** | 81 tests across verification, storage, confidence, API, and models. Shared fixtures for reproducibility. |
| **CI/CD** | Backend and frontend jobs consistent with pyproject and package.json. |
| **Docs** | README, ARCHITECTURE, and AUDIT updated to match current implementation. |

---

## 9. Gaps and Next Steps

| Priority | Item | Status |
|----------|------|--------|
| **High** | Extraction prompt improvement (few-shot, structured output, page-type classification) | Planned (A3) |
| **High** | Ingestion pipeline integration test (PDF in → canonical out against ground truth) | Planned (A4.1) |
| **High** | Extraction quality benchmark harness | Planned (A4.5) |
| **Medium** | CI integration (pytest in CI with coverage gating) | Planned (A4.6) |
| **Medium** | Rate limiting on API endpoints | Not implemented |
| **Medium** | UI-SPEC update for confidence tiers and formatting labels | Not done |
| **Low** | Proof type-colored legend in viewer | Not implemented |
| **Low** | "Locate on PDF" per canonical row | Not implemented |

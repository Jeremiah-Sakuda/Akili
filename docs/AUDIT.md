# Akili — Full Repository Audit

**Date:** February 2025  
**Scope:** README/goals alignment, architecture, security, CI/CD, docs, and gaps.

---

## 1. Goals vs. Implementation

### 1.1 Core Pillars (README)

| Pillar | Status | Notes |
|--------|--------|--------|
| **Structural canonicalization** | Done | Unit, Bijection, Grid in Pydantic; canonicalize rejects invalid/ambiguous; store persists only validated objects. |
| **Coordinate-level grounding** | Done | Every answer includes proof with `(x, y, page)`; ProofPoint has page for overlay. |
| **Deterministic refusal** | Done | `verify_and_answer` returns Refuse when no rule derives the answer; rule order is fixed. |

### 1.2 Tech Stack (README)

| Layer | README | Implementation |
|-------|--------|----------------|
| Runtime | Python 3.11+ | pyproject.toml `requires-python = ">=3.11"`; CI matrix 3.11, 3.12. |
| LLM / Vision | Google Gemini | `google-generativeai`; `gemini_extract.py` uses `gemini-3.0-flash`. |
| Canonical model | Pydantic v2 | `canonical/models.py`; extract_schema + canonicalize. |
| Document processing | PyMuPDF, pdf2image | `pdf_loader.py` uses PyMuPDF (fitz); pdf2image in deps but not used in code. |
| Store | SQLite (MVP) | `store/repository.py`; SQLite only; no PostgreSQL path yet. |
| Verification | Rule-based + optional Z3 | Rule-based in `verify/proof.py` (pin, voltage max, unit lookup); no Z3. |
| API | FastAPI | `api/app.py`; all stated endpoints plus `/status`, `/health`, `/documents/{id}/file`. |
| Viewer | React + PDF.js | React + Vite; PDF.js via `pdfjs-dist`; DocumentViewer with overlay. |

### 1.3 API Surface

| Endpoint | README / ARCHITECTURE | Status |
|----------|------------------------|--------|
| POST /ingest | Yes | Implemented; PDF stored under `docs/`; max size via AKILI_MAX_UPLOAD_BYTES. |
| POST /query | Yes | Implemented; returns answer + proof or REFUSE. |
| GET /documents | Yes | Implemented. |
| GET /documents/{id}/canonical | Yes | Implemented. |
| GET /documents/{id}/file | UI-SPEC | Implemented; serves stored PDF. |
| GET /status, /health | Doc | Implemented; public (no auth). |

### 1.4 UI (README + UI-SPEC)

| Feature | Spec | Status |
|---------|------|--------|
| Three-pane layout | UI-SPEC 2.1 | Left (docs + canonical), center (viewer), right (query + result). |
| Upload drop zone | UI-SPEC 2.2 | FileUploader; PDF only; doc_id + copy button. |
| Document list | UI-SPEC 2.3 | SidebarLeft; filename, meta (counts); selected state. |
| Canonical inspector | UI-SPEC 2.4 | SidebarLeft tabs Units \| Bijections \| Grids; GET canonical. |
| PDF viewer | UI-SPEC 2.5 | DocumentViewer with pdfjs-dist; page canvas. |
| Proof overlay | UI-SPEC 2.5 | Overlay when `overlayProof` set; “Show on document” sets it. |
| Query + result | UI-SPEC 2.6 | SidebarRight; VERIFIED / REFUSED; proof list; page in proof. |
| Firebase / Google sign-in | README | Optional; LoginPage; auth gates app; API sends Bearer when signed in. |

### 1.5 Gaps vs. Docs

- **README project structure:** Lists only `ci.yml`; repo has `deploy.yml` as well.
- **README API list:** Does not mention `GET /documents/{doc_id}/file` (used for viewer).
- **ARCHITECTURE “Retrieval”:** Describes semantic/coordinate retrieval; current code loads all canonical for `doc_id` (no semantic/embedding filtering).
- **UI-SPEC “Locate” link:** Optional “Locate” per canonical row (scroll PDF, show marker) not implemented.
- **UI-SPEC proof legend:** “Unit · Bijection · Grid” swatches below viewer not implemented (overlay is single style).
- **pdf2image:** In requirements/pyproject; only PyMuPDF used in code (no functional gap; could remove from deps for clarity).

---

## 2. Security

### 2.1 In Place

- **CORS:** Configurable via `AKILI_CORS_ORIGINS`; default localhost only.
- **API auth:** Optional Firebase ID token; `AKILI_REQUIRE_AUTH` + `FIREBASE_PROJECT_ID`; `firebase-admin` optional dep `.[auth]`; ImportError handled.
- **Upload limit:** `AKILI_MAX_UPLOAD_BYTES` (default 100 MB); 413 when exceeded.
- **doc_id validation:** `_validate_doc_id` allows only `[a-zA-Z0-9_-]`; no path traversal.
- **SQL:** Parameterized queries only in repository; no injection risk.
- **Secrets:** `.env` in `.gitignore`; no backend keys in frontend build (Vite define removed).
- **Health/status:** Unauthenticated for load balancers and checks.

### 2.2 Recommendations

- **401 handling (frontend):** On 401 from API, consider redirect to login or token refresh instead of generic “Failed to fetch” (e.g. in `api.ts` or a fetch wrapper).
- **Rate limiting:** No rate limit on /ingest or /query; consider per-IP or per-user limits when auth is on to protect Gemini quota.
- **Docker PDF persistence:** PDFs live in `docs/` next to DB; with `AKILI_DB_PATH=/data/akili.db`, `docs` is `/data/docs` and covered by the same volume; no change needed.

---

## 3. Backend Code Quality

- **Lint/format:** CI runs Ruff (check + format) and Flake8; pyproject has ruff and flake8 config.
- **Tests:** `tests/test_verify.py`, `tests/test_canonical.py`; verify covers refuse, bijection, units, grid pin name.
- **Ingest:** Pipeline uses page delay and (if implemented) retries for 429; `.env.example` documents retry/backoff vars.
- **Store:** Single global Store; no connection pooling (fine for SQLite MVP).

---

## 4. Frontend

- **Stack:** React, TypeScript, Vite, Tailwind; Firebase optional; pdfjs-dist for viewer.
- **API client:** All requests use `authHeaders()` (Bearer when signed in); endpoints aligned with backend.
- **PDF viewer:** Loads via `getDocumentFile`; worker via `?url`; `vite-env.d.ts` declares `*?url`.
- **CI:** Build uses empty VITE_* env vars including `VITE_FIREBASE_MEASUREMENT_ID`.

---

## 5. CI/CD

| Workflow | Trigger | Jobs |
|----------|---------|------|
| **CI** | push/PR to main, master, develop | Backend: Python 3.11/3.12, pip install -e ".[dev]", Ruff, Flake8, pytest, coverage; Frontend: npm ci, lint, typecheck, build. |
| **Deploy** | push to main/master, workflow_dispatch | Build frontend with Firebase secrets; deploy to Firebase Hosting. |

- **Backend CI:** No `firebase-admin` (auth optional); tests use `GOOGLE_API_KEY: dummy`.
- **Deploy:** Uses repo secrets for Firebase and `FIREBASE_TOKEN`; optional `production` environment.

---

## 6. Docker

- **Compose:** `api` (port 8000) + `frontend` (3001→3000); `.env` and `AKILI_DB_PATH=/data/akili.db`; volume `akili-data` for `/data` (DB + docs).
- **Frontend:** Proxy target `http://api:8000`; `.env` mounted for VITE_*.
- **Healthcheck:** API checked via request to `/docs`.

---

## 7. Documentation

- **README:** Run instructions, Docker, Firebase, CI/CD, env vars; project structure slightly out of date (missing deploy.yml, GET /file).
- **.env.example:** GOOGLE_API_KEY, AKILI_*, Firebase VITE_*; retry/backoff optional vars documented.
- **ARCHITECTURE.md:** Matches design; retrieval described as semantic/coordinate but not implemented that way.
- **UI-SPEC.md:** Matches layout and components; minor gaps (Locate link, proof legend).

---

## 8. Summary

| Area | Verdict |
|------|--------|
| **Goals** | Core pillars and stated API/UI are implemented; optional viewer, canonical inspector, proof overlay, and doc file endpoint are in place. |
| **Security** | Auth and CORS configurable; upload limit; doc_id validated; no key leakage; 401 UX and rate limiting recommended. |
| **CI/CD** | Backend and frontend jobs consistent with pyproject and package.json; flake8 in dev deps. |
| **Docs** | Small README/API list and project-structure updates would align docs with current behavior. |

No critical gaps. Suggested next steps: (1) Update README with `GET /documents/{id}/file` and deploy.yml in project structure, (2) Optional: 401 → login or refresh in frontend, (3) Optional: rate limiting when auth is enabled.

---

## 9. Check (latest)

**Verified:** February 2025 (follow-up pass).

- **docs/INGEST-FLOW.md:** Present; describes API → pipeline → pdf_loader → gemini_extract with code references. Actual code matches: pipeline has per-page try/except and page delay; pdf_loader has per-page try/except; gemini_extract uses `AKILI_GEMINI_MODEL`, retries on 429, normalizes extraction.
- **.env.example:** Includes `AKILI_GEMINI_MODEL` (gemini-3.0-flash / gemini-3-*); retry/backoff vars documented. Backend reads these in `gemini_extract.py` and `pipeline.py`.
- **.github/dependabot.yml:** npm (frontend), pip (root), github-actions; weekly; limits 5/5/3 PRs. No issues.
- **CI:** Unchanged; backend Ruff + Flake8 + pytest; frontend lint, typecheck, build with empty VITE_*.
- **README:** Project structure still lists only `ci.yml` (add `deploy.yml`). API list still omits `GET /documents/{doc_id}/file`.
- **Security / implementation:** No changes; auth optional, CORS and upload limit in place, doc_id validated.

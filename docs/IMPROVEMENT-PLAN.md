# Akili — Technical Audit & Improvement Plan

*Deep-dive review of the Akili proof-of-concept. Scope: verify the public claims against
the actual code, identify gaps, and propose a prioritized improvement plan. Every finding
below is grounded in a `file:line` citation and, where possible, was confirmed by running
the code (297 backend tests pass; benchmark stub, consensus default, Z3 wiring, and the
multi-tenant gap were each verified directly).*

> **One-line verdict:** Akili is a well-engineered PoC with a clean architecture and a
> genuinely deterministic rule engine — but the **headline claims that make it sound like a
> verification product (coordinate-grounded "proof", a measured 15% hallucination reduction,
> Z3 "mathematical guarantees", confidence-based refusal) are not backed by the code as
> shipped.** The single most valuable work is to either make those claims true or restate them
> honestly. Nothing here is unfixable; most of it is wiring and honesty.

---

## 0. Implementation status (this plan, executed)

Most of this plan has been implemented on the `improvement-plan` branch. Summary:

| Area | Status |
|------|--------|
| P0 packaging, `.env.example`, Dockerfile/nginx `$PORT`, `.dockerignore` | ✅ Done |
| P0 real CI workflow (`.github/workflows/ci.yml`) | ✅ Done |
| P0 de-fabricate benchmark (real runner; illustrative-labeled landing data) | ✅ Done |
| P1 **coordinate grounding** against the PDF text layer (`ingest/grounding.py`) | ✅ Done |
| P1 proof overlay draws the real bbox (not a full-width band); grounding test | ✅ Done |
| P2 confidence gating (`/query` refuses below threshold); every answer scored | ✅ Done |
| P2 grounding earns VERIFIED; flagged facts capped | ✅ Done |
| P2 Z3 wired into ingest + tautology/contradiction fixes | ✅ Done |
| P2 max/min unit-magnitude, path-traversal, consensus no-op, learn transforms | ✅ Done |
| P3 per-user ownership + IDOR fix; `get_document_owner` on Postgres; fail-closed auth | ✅ Done |
| P3 bounded uploads; append-only audit log (DB triggers) | ✅ Done |
| P4 public corpus on SQLite; migration preserves ownership + corpus | ✅ Done |
| P4 UsageLimitModal wired; ShareButton origin fixed | ✅ Done |
| Docs updated to match reality | ✅ Done |

**Deferred (with reason):**
- **`Range`/`ConditionalUnit` from live extraction** — needs Gemini prompt/schema iteration
  validated against real datasheets; not meaningfully testable without a live API key. The
  canonical types and the corpus path already support them.
- **`google-generativeai` → `google-genai` SDK migration** — a blind swap of the core LLM
  client cannot be verified in this environment (integration tests require a live key and the
  unit tests mock the current SDK heavily); shipping it untested would risk the core path.
- **`ReviewPanel` / `CompareView` frontend components** — the backend `/corrections` and
  `/compare` endpoints exist, but these UIs are not built. Docs no longer claim them as shipped.

Test suite: **317 passing** backend tests (4 integration deselected) + **29** frontend tests;
`ruff`/`flake8`/`eslint`/`tsc` all clean.

---

## 1. What is genuinely strong (keep this)

These are real and should not be lost in the cleanup:

- **The rule engine is genuinely deterministic.** 30 rules (22 factory + 8 decorator, confirmed
  by runtime introspection of `proof._RULES`), priority-ordered, first-non-`None` wins, with a
  pure-regex intent pre-filter — same inputs always produce the same answer or the same refusal.
  No randomness, time, or network in the decision path. (`verify/proof.py:64-72,1038-1055`)
- **The derived-query engine is the best part of the codebase.** P=V×I, thermal
  (T_j = T_a + P·θ), voltage margin, and current budget all produce correct arithmetic with
  proper SI unit conversion and a real step-by-step `ProofChain`, with edge guards
  (`v_max==0`, `v_op>v_max`). (`verify/derived.py`)
- **The ingestion plumbing is thoughtfully defensive.** Messy-Gemini-JSON normalization,
  per-page fault tolerance, ret/backoff on 429, a call timeout, page-namespaced IDs.
  (`ingest/gemini_extract.py`, `ingest/pipeline.py`)
- **Real security engineering exists.** Auth defaults **on** (`config.py:81`), there is a
  fail-closed production guard (`api/app.py:196-210`), the prior `SECURITY_REVIEW.md` findings
  (path traversal, prompt injection, page limit, grid bounds, call timeout) were actually
  remediated in code, upload validation checks magic bytes + size, and SQL is parameterized
  throughout (no injection found).
- **The frontend is competent and has no XSS sinks.** Clean typed API client with Bearer-token
  auth + 401 sign-out, real pdfjs viewer, MSW-based tests. No `dangerouslySetInnerHTML`/`eval`
  anywhere (React escapes model output).
- **The Cloud Run deploy path is coherent and production-shaped** (Secret Manager wiring,
  sensible flags, multi-stage frontend build with security headers).
- **The PRD and `docs/DD-REMEDIATION-PLAN.md` are unusually candid** — they already name several
  of the issues below ("Z3 is marketing, not a moat"; "50 easy questions… Indefensible";
  "confidence is actually 2 components, not 3").

---

## 2. Claims-accuracy matrix

Status legend: ✅ accurate · 🟡 partially true / misleading · ❌ false as stated.

| # | Public claim | Status | Reality (evidence) |
|---|---|---|---|
| 1 | "Every answer tied to **exact (x,y) coordinates** on the source document, or it refuses. No citations — only proof." | ❌🟡 | Coordinates are **self-reported by Gemini** in its JSON; the prompt asks it to *"estimate"/"infer"* them (`gemini_extract.py:34,47-48`). Nothing ever validates them against the rendered page (no OCR, no PyMuPDF text geometry). Out-of-range coords are **silently clamped** into [0,1], not rejected (`gemini_extract.py:287-290`). The "refuses" half is real and deterministic. |
| 2 | "AKILI reduces hallucinations by **15%** vs raw Gemini (90% vs 75%)", tested on 50 pairs, with CI regression testing. | ❌ | The AKILI side of the benchmark is a **stub that hardcodes `correct=True`** for every question (`benchmark/run_benchmark.py:289-323`, "TODO: Implement actual AKILI API calls"). The README table and `frontend/.../benchmarkData.ts` are **hand-typed constants** that don't even match the stub's 100%. No `results.json` is ever produced. No CI exists. The 50-pair *dataset* is real. |
| 3 | "Z3 constraint solving provides **mathematical guarantees** for unit normalization, contradiction detection, range consistency." | ❌🟡 | `run_z3_checks` is **never called outside its own unit test** — not in ingest, not in query, never persisted (`z3_checks.py:607` is the only def; `ingest/pipeline.py` has no Z3). Even when run, unit-normalization is a **tautology** (`x != x`, can never fire), and contradiction/range checks pin all vars to constants — equivalent to `<=` in Python. README:138 lists a Z3 ingest stage that does not exist. |
| 4 | "Three-component confidence classifies answers as **VERIFIED ≥0.85 / REVIEW / REFUSED <0.50**." | 🟡 | The thresholds exist, but with consensus off by default `extraction_agreement` is pinned to 0.5, so **VERIFIED (≥0.85) is mathematically unreachable** single-pass (max ≈0.73 direct, ≈0.79 derived). Many rules return `confidence=None` (no tier at all). |
| 5 | "**Deterministic Refusal**: <50% confidence → refusal with reason." | 🟡 | Refusal is deterministic but is triggered **only by "no rule matched"**, never by confidence. `/query` returns *every* answer as HTTP 200 and attaches `confidence_tier` as **decorative metadata** (`routers/query.py:112-115`). A "refused"-tier answer is still served as an answer. |
| 6 | "Consensus before trust: dual-pass extraction prevents single-pass hallucinations." | 🟡 | Off by default (`config.py:63`). Worse, enabling it alone is a **silent no-op** — `should_use_consensus` requires a high-risk `page_type`, but `classify_page` returns `"other"` unless a *second* off-by-default flag (`PAGE_CLASSIFY_ENABLED`) is also on (`consensus.py:244`, `page_classifier.py:76-77`). |
| 7 | "Learn: correction patterns → auto-correction rules applied to future answers." | ❌🟡 | The analyzer works in isolation, but **nothing consumes it** — not the query path, not ingestion, not the UI. And the auto-correct transforms are **numerically wrong** (a mV→V "fix" yields `4500 V` from `4500 mV`; sub-unity scaling applies the factor backwards). `times_applied` is dead state. |
| 8 | "PostgreSQL store: **multi-tenant with org_id isolation on every table**." | ❌🟡 | The `org_id` column and filters exist, but `org_id` is **permanently `"default"`** for every user (never sourced from the request; `deps.py:37`, `store/__init__.py:14`). `corrections`/`usage`/`shared_answers`/`public_corpus` have **no `org_id` at all**. So it is single-tenant in practice. |
| 9 | "30 verification rules, priority order, first non-None wins." | ✅ | Confirmed exactly 30 (22 factory + 8 decorator). |
| 10 | "Derived queries produce a ProofChain with correct arithmetic." | ✅ | Confirmed end-to-end (e.g. 3.3V × 10mA → "33.0 mW"). |
| 11 | "280+ backend tests / 29 frontend tests." | ✅🟡 | **297** backend tests pass (4 integration deselected); 29 frontend tests exist. The README "280+" holds; `ARCHITECTURE.md`'s "205 across 16 files" is **stale** (actual 22 files). |
| 12 | "CI: GitHub Actions (3.11/3.12 + Node 20)…" + CI badge. | ❌ | **No `.github/` directory exists.** The README badge points at a nonexistent workflow. `docs/CI-CD-SECURITY-REVIEW.md` and `docs/AUDIT.md` cite line numbers in `ci.yml`/`dependabot.yml`/`.gitignore`/`.env.example` — **none of which exist**. |
| 13 | "Public corpus of 20 common chips" (instant results). | 🟡 | 20 chip *names* exist as a Python list; the committed DB has **0 corpus rows**, and corpus methods exist **only on the Postgres store** — `populate_corpus.py` `AttributeError`s on the default SQLite backend. Inert out of the box. |
| 14 | Frontend `ReviewPanel.tsx` / `CompareView.tsx` (Stage B/C review & compare UI). | ❌ | **Neither file exists.** Documented in detail in `ARCHITECTURE.md`/execution plan as shipped deliverables; they are vaporware. (The `/compare` and `/corrections` *backend* endpoints do exist.) |
| 15 | Quick Start: `cp .env.example .env`. | ❌ | **No `.env.example` exists.** `docker-compose.yml` hard-requires a `.env`, so a clean clone following the README cannot start. |
| 16 | `FRONTEND_SECURITY_REVIEW.md`: "2 CRITICAL XSS". | 🟡 | The opposite error: there are **no** XSS sinks in the code. The self-authored doc **overstates** a risk that doesn't exist. |

---

## 3. Gaps by severity

### 🔴 Critical

1. **Fabricated benchmark presented as measured results.** `benchmark/run_benchmark.py:289-323`
   hardcodes every AKILI answer correct; README §Benchmark and `benchmarkData.ts` are typed
   constants. This is the most material integrity problem — it puts an unmeasured marketing
   number in front of users and stakeholders.
2. **The core "coordinate-grounded proof" claim is not real.** (x,y) are unvalidated LLM
   self-reports; the PDF "proof overlay" draws a **full-width horizontal band at the y-coordinate
   and ignores x and bbox width entirely** (`DocumentViewer.tsx:203-224`) — so even the visual
   "proof" never points at a cell. `(0,0)` and `(5.0,-2.0)` origins are accepted as valid proof.
3. **Broken multi-tenant isolation / IDOR (security).** Even with auth on: `org_id` is hardcoded
   `"default"` for all users; `GET /documents` has no ownership filter, so **any authenticated
   user can enumerate every other user's documents** (`routers/documents.py:21-28`,
   `store/postgres.py:597-614`). The ownership gate `require_doc_access` calls
   `store.get_document_owner()`, **which does not exist on `PostgresStore`** → `AttributeError`/500
   in production (`deps.py:136`; method only in `repository.py:546`). The passing test mocks it,
   hiding the gap.

### 🟠 High

4. **Z3 is dead code** but is advertised as a documented ingest step and "mathematical
   guarantees." Never invoked outside tests; results never persisted or surfaced.
5. **Confidence is decorative.** Low-confidence answers are returned, not refused
   (`routers/query.py:112-115`); the VERIFIED tier is unreachable single-pass; `verification_strength`
   is a hardcoded per-rule constant (a *label*, not a measurement). The "verification layer"
   never checks whether the extracted *value* is correct — only that some keyword-matching fact exists.
6. **Consensus safeguard is inert** — off by default and a silent no-op even when its obvious flag
   is set (hidden dependency on a second flag).
7. **Fabricated CI/CD audit docs** (`CI-CD-SECURITY-REVIEW.md`, `AUDIT.md`) assert security
   controls (CI matrix, Dependabot, gitignored secrets) that **do not exist** — more dangerous
   than a missing feature because it asserts false assurance. No CI; dead README badge.
8. **The "learning" loop is not wired in and its transforms corrupt values** (mV→V keeps the
   magnitude; sub-unity scaling inverts the factor). If ever connected it would *inject* errors.
9. **No test validates coordinate-on-PDF grounding** — the product's central claim is untested
   and unfalsifiable by the suite. The unit suite feeds **hand-built canonical objects** to the
   rule engine; the one "integration" test mocks Gemini and asserts the mock's own coordinates.
10. **`Range` / `ConditionalUnit` are never produced by real ingestion** — only by the corpus
    loader (`canonicalize.py:115-127` returns only Unit/Bijection/Grid). The Stage-B min/typ/max
    feature is effectively dead on uploaded PDFs.
11. **Public corpus non-functional on the default backend** — corpus methods exist only on
    Postgres; `populate_corpus.py` cannot seed SQLite; `/library` reports all 20 chips
    `available:false`.

### 🟡 Medium

12. **`max`/`min` ignores unit magnitude** → "maximum current" of `500 mA` vs `2 A` returns
    `500 mA` because `500 > 2` (`proof.py:160-184`). Real correctness bug across all best-numeric rules.
13. **Out-of-range coordinates silently clamped** instead of flagged (`gemini_extract.py:287-290`),
    converting an obviously-hallucinated point into a plausible-looking one.
14. **`compute_agreement` returns 1.0 (perfect) when both consensus passes extract nothing**
    (`consensus.py:124-125`) — a double-failure scores as maximally trustworthy.
15. **Vaporware/dead frontend.** `ReviewPanel`/`CompareView` don't exist; `ShareButton`,
    `UsageLimitModal`, `LoginPage`, and `useOnboardingMetrics` are fully built but **never mounted**;
    the "first query without signup" (FR-ON-3) flow is not implemented (app gates everything behind login).
16. **Path-traversal guard uses fragile string `startswith`** (`pipeline.py:106-113`) — sibling-prefix
    bypass; use `pathlib` containment.
17. **Audit log "immutable" by convention only** — no trigger/REVOKE/hash-chain; HMAC export
    can't detect prior tampering.
18. **SQLite ↔ Postgres schema divergence** (`uploaded_by`, `get_document_owner`, projects/chat
    tables present on one backend only); the **migration tool drops provenance, audit, ownership,
    corrections, usage** (`migrate.py:38-62`).
19. **Auth can fail open** if the `auth` extra (`firebase-admin`) isn't installed or
    `FIREBASE_PROJECT_ID` is unset, even with `REQUIRE_AUTH=1` — only the Postgres prod guard
    catches it (`auth.py:36-37`).
20. **Upload reads the whole file into memory before the size check** (`routers/ingest.py:60-66`)
    — a DoS vector; free-tier is keyed on raw client IP when unauthenticated (trivially bypassable / proxy-shared).
21. **Dependency/packaging drift.** `requirements.txt` omits `slowapi`/`psycopg2`/`firebase-admin`
    (the manual `pip install -r` path produces a broken backend); the Dockerfile references a
    nonexistent `.[postgres]` extra; no `.dockerignore`; containers run as root; `akili.db` is committed.
22. **The Gemini SDK is end-of-life.** `google-generativeai` is deprecated ("All support has
    ended"); migrate to `google-genai`.

### 🟢 Low

23. Grid/bijection proof points cite the wrong cell and a whole-table bbox (`proof.py:213-224,445-456`).
24. Confidence worked example is wrong in the docs (0.78 vs actual 0.773); ARCHITECTURE shows
    pixel-scale `{x:142,y:387}` proof coords that contradict the "normalized 0–1" schema.
25. Doc test-count drift (README "280+", ARCHITECTURE "205", actual 297 / 22 files).
26. nginx hardcodes `listen 8080` while claiming to honor Cloud Run `$PORT` (`nginx.conf:34`).
27. Z3 contradiction check only compares the first element of each group and false-positives on
    multi-rail parameters (two distinct "VCC" rails flagged as a contradiction).

---

## 4. The improvement plan (phased)

### Phase 0 — Integrity & honesty *(days; do this first)*
The cheapest, highest-leverage work: stop asserting things the code doesn't do.
- **Benchmark:** either (a) wire `run_akili_benchmark` to the real pipeline, commit the 5 fixture
  PDFs to `tests/fixtures/`, run it, and have `benchmarkData.ts` read the produced `results.json`;
  or (b) **pull the benchmark table, the +15% claim, and the CI badge** until real numbers exist.
  Label any interim numbers "illustrative target," not "tested."
- **Docs vs reality:** delete or rewrite `CI-CD-SECURITY-REVIEW.md` and the CI/model sections of
  `AUDIT.md` (they cite nonexistent files); remove the dead CI badge; add the missing
  **`.env.example`** (all `GOOGLE_API_KEY`, `DATABASE_URL`, `VITE_FIREBASE_*`, `VITE_API_URL` keys);
  fix the README "280+/205" drift; reconcile `ARCHITECTURE.md` to remove the Z3 ingest step and
  the `ReviewPanel`/`CompareView` references (or build them — see Phase 4).
- **Restate the thesis honestly** until Phase 1 lands: "model-estimated source locations" instead
  of "exact coordinate-grounded proof"; "deterministic consistency checks" instead of "Z3
  mathematical guarantees."

### Phase 1 — Make the core thesis real: coordinate grounding *(the differentiator)*
This is what turns Akili from "LLM with nice UX" into a verification product.
- Extract **ground-truth geometry from PyMuPDF** (`page.get_text("words")` / `rawdict`) at ingest.
- **Snap** each Gemini-reported value to the nearest real text token; **reject (don't clamp)** when
  the claimed value doesn't appear within/near the claimed box; attach a grounding-confidence signal.
- Add a Pydantic validator constraining `origin`/`bbox` to [0,1] and rejecting degenerate boxes.
- **Fix the proof overlay** to draw a tight rectangle from the real bbox (or a point marker at
  (x,y)) instead of a full-width band.
- Add the missing test: render a known PDF, get true word bboxes, run extraction, assert the
  canonical origin falls inside the true bbox within tolerance.

### Phase 2 — Close the verification loop
Make "confidence" and "refusal" mean something.
- **Gate `/query` on confidence**: below `REVIEW_THRESHOLD` → return a `Refuse`, not a 200 answer.
- Make the tier reachable: either raise the single-pass `extraction_agreement` baseline, rebalance
  weights, or make consensus the default for high-risk pages — and ensure **every** answer carries
  a `ConfidenceScore` (pin/grid/range/multi-value rules currently return `None`).
- Replace the hardcoded `verification_strength` with a measured match-quality signal (exact
  structured match vs keyword fallback).
- **Wire Z3 into the pipeline** after multi-page merge, persist its issues, and route contradictions
  to REVIEW — *or* delete it and drop the claim. Fix the tautological unit-normalization check and
  the first-element-only contradiction loop. Fix the `max`/`min` unit-magnitude bug (#12).
- **Decouple consensus from page-classification** (or document the dual-flag requirement and log
  when consensus is requested but suppressed). Fix the both-empty agreement=1.0 bug.

### Phase 3 — Security & multi-tenancy hardening
- **Thread `org_id` from the authenticated principal** into every store call (per-request, not a
  global singleton); add `org_id` to `corrections`/`usage`/`shared_answers`; add an end-to-end test
  that org A cannot read org B's data.
- **Fix ownership enforcement**: add `uploaded_by` + `get_document_owner` to `PostgresStore` and
  `BaseStore`; make `GET /documents` filter by owner; replace the mocked test with a real one.
- Fail **closed** when `REQUIRE_AUTH=1` but Firebase can't initialize.
- Stream/limit uploads before buffering; key free-tier on authenticated uid (or signed token), not raw IP.
- Make the audit log append-only at the DB level (trigger/REVOKE) or hash-chain it if compliance is claimed.

### Phase 4 — Productization & polish
- **CI**: add `.github/workflows/ci.yml` (pytest 3.11/3.12, ruff/flake8, eslint, vitest, benchmark
  regression gate) — then the badge and the audit docs become true. Auto-generate test counts.
- **Tests that matter**: at least one un-mocked extraction test against a committed fixture; tests
  for the overlay coordinate math, auth/token flow, and refuse-vs-review rendering.
- **Corpus**: implement corpus methods on the SQLite store (or document Postgres-only and fix the
  README checkbox); actually populate and verify the 20 chips.
- **Build the claimed UI** (`ReviewPanel`, `CompareView`) or remove them from the docs; mount the
  dead components (`ShareButton`, `UsageLimitModal`) or delete them.
- **Produce `Range`/`ConditionalUnit` from real extraction**, not just the corpus.
- **Migrate off the EOL `google-generativeai` SDK** to `google-genai`.
- Packaging hygiene: reconcile `requirements.txt`↔`pyproject`, fix the `.[postgres]` typo, add
  `.dockerignore`, run containers as non-root, gitignore `akili.db` and ship migrations + seed.

---

## 5. Suggested sequencing

| Priority | Theme | Items | Rough effort |
|---|---|---|---|
| **P0** | Honesty (don't ship false claims) | #1, #4, #7, #12(doc), #15(docs), §Phase 0 | Days |
| **P1** | Real coordinate grounding | #2, #13, #23, Phase 1 | 1–2 weeks |
| **P1** | Security/tenancy | #3, #18, #19, #20, Phase 3 | 1–2 weeks |
| **P2** | Verification loop | #5, #6, #8, #9, #14, Phase 2 | 2–3 weeks |
| **P3** | Productization | #10, #11, #15(UI), #21, #22, Phase 4 | Ongoing |

*The two P0/P1 integrity items (benchmark, coordinate grounding) and the P1 IDOR are the ones to
fix before any external demo or diligence. Everything else is normal PoC→product hardening.*

---

*Generated from a multi-agent code audit (10 subsystem investigations + 5 adversarial claim
verifications) cross-checked against a live run of the test suite and direct inspection.*

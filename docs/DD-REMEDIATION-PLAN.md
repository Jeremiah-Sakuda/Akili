# DD Remediation Plan

**Owner:** Engineering
**Created:** 2026-05-03
**Horizon:** 12 weeks (4 sprints × 3 weeks)
**Source:** Investor diligence flags from VC technical review (see in-conversation memo, May 2026).

This document converts the diligence review's findings into a sprint-organized engineering plan. Each item lists the DD concern it answers, the verified current state of the code (re-checked against `v2/audit-improvements` HEAD), the work to do, and an acceptance criterion that closes the flag.

> **Reading order:** Skim §0 (the IC-objection map). Then read the sprint you are currently in. Each item is self-contained.

---

## 0. IC-Objection → Track Map

| Investor objection | Closed by track | Sprint |
|---|---|---|
| "The benchmark is 50 easy questions on famous chips. Indefensible." | **B (Diligence Credibility)** | 2 |
| "Gemini dependency. One model breakage breaks the product." | **B4 (LLM abstraction)** | 1–2 |
| "Z3 is marketing, not a moat." | **B6 (cross-param constraints)** | 2 |
| "Confidence score has a hardcoded 0.5 — it's actually 2 components, not 3." | **B5 (consensus → confidence)** | 0 |
| "Keyword substring matching will produce embarrassing demo failures." | **B7 (intent classifier)** | 3 |
| "Demo is a single-doc chat. No retention story." | **D1, D2, D3 (workspace)** | 3–4 |
| "Solo founder, no customer evidence." | **D5 (20-engineer onboarding study)** | 3–4 |
| "Aerospace/medical compliance moat is hypothetical." | **C3 (audit export)** | 3 |
| "PDF authorization, rate limiting, sync sleeping threads — production hygiene." | **A1, A2, A3, A7 (production hardening)** | 0–1 |

---

## 1. Tracks

The plan has four tracks, executed in parallel:

- **Track A — Production Hardening.** Things that block paying customers, embarrassing demo failures, or get reported in a security review. Mostly P0.
- **Track B — Diligence Credibility.** The specific items a technical due-diligence partner will drill on. The benchmark, the LLM dependency, the moat claims that don't yet hold up.
- **Track C — Moat Hardening.** Things that compound over time and define the Series A pitch in 12 months. Knowledge graph, audit trail, flywheel.
- **Track D — Retention & GTM.** Workspace, plugin, customer development. Determines whether MRR exists.

---

## 2. Sprint 0 — Quick Wins (Week 1, ≤ 5 working days)

**Goal:** Close every embarrassing hole that a hostile diligence call could surface this week. None of these take more than half a day.

### A2 — Tighten PDF authorization check

- **DD finding:** "Any authenticated user can download any other user's PDF by guessing the UUID."
- **Current state (verified):** `routers/documents.py:60–65` does an ownership check, but only when `_user is not None and is_auth_required()`. With `AKILI_REQUIRE_AUTH=0` (the default in the .env.example), the check is skipped entirely. The same pattern is missing on `/canonical` and `/ingest/stream`-served files.
- **Work:**
  1. Move owner check into a shared dependency: `require_doc_access(doc_id, user) -> None`.
  2. Apply to all document-scoped endpoints: `/documents/{id}/file`, `/documents/{id}/canonical`, `/documents/{id}` (DELETE), `/query`, `/share`, `/compare`.
  3. When auth is disabled in a prod-like env (`DATABASE_URL` set), still log and return 403 on cross-user access.
- **Acceptance:** A second user with a valid token cannot read documents owned by user A. Test added: `tests/test_api.py::test_cross_user_pdf_access_denied`.
- **Files:** `src/akili/api/deps.py`, `src/akili/api/routers/documents.py`, `corrections.py`, `query.py`, `share.py`, `compare.py`.
- **Effort:** 0.5 day.

### A4 — Strict UUID validation for `doc_id`

- **DD finding:** "`_validate_doc_id` regex matches any alphanumeric string."
- **Current state (verified):** `src/akili/api/deps.py:80–83` allows `^[a-zA-Z0-9_-]+$`. Strings like `"admin"` or `"test"` pass.
- **Work:** Replace with strict UUID4 validation. Maintain the regex as a fallback for legacy doc IDs (warn-log only).
- **Acceptance:** New test `tests/test_api.py::test_validate_doc_id_rejects_non_uuid` passes. All ingest paths still produce IDs that pass.
- **Effort:** 30 min.

### A5 — Replace bare `catch {}` blocks with logged error handling

- **DD finding:** Frontend swallows query errors, hiding them from the user, Sentry, and the founder.
- **Current state (verified):** Bare `catch {}` in `frontend/src/App.tsx:110`, `components/FileUploader.tsx:82`, `components/SidebarLeft.tsx:50`, `api.ts:29`.
- **Work:** Each `catch` block must (a) capture the error, (b) call `addToast(...)` with a user-facing message, (c) `console.error(...)` for dev visibility, (d) when `import.meta.env.PROD`, send to a telemetry endpoint (or stub now, real later).
- **Acceptance:** `eslint` rule `no-empty` set to `error`. Added test in `App.test.tsx` that mocks an API failure and asserts the toast is shown.
- **Effort:** 0.5 day.

### A6 — Pin Gemini model + add fallback config

- **DD finding:** Preview models will rug you.
- **Current state (verified):** `config.py:41` defaults to `gemini-3-flash` (not preview, good). But there's no fallback model and no version pin.
- **Work:**
  1. Default to a dated stable, e.g. `gemini-3-flash-002` (or current stable).
  2. Add `AKILI_GEMINI_FALLBACK_MODEL` (no fallback by default).
  3. In `gemini_extract.py`, on `NotFound`/`PermissionDenied`/specific 4xx, log + retry once with fallback before raising.
- **Acceptance:** Unit test that monkey-patches `genai.GenerativeModel` to raise `NotFound` on first call, returns successfully on the second.
- **Effort:** 0.5 day.

### A7 — Fail-closed auth in production-like environments

- **DD finding:** Auth bypass with `AKILI_REQUIRE_AUTH=0` is silent. A misconfigured deploy is fully open.
- **Current state (verified):** `app.py:184–195` logs at ERROR if `_is_production_environment()` and auth is disabled, but doesn't actually fail the startup.
- **Work:**
  1. New env var `AKILI_ALLOW_OPEN_PROD=0` (default).
  2. If `_is_production_environment()` and auth disabled and `ALLOW_OPEN_PROD=0`, raise on startup.
  3. Add `/health` flag `auth_required: bool` so deploy scripts and load balancers can verify the deployment.
- **Acceptance:** New test `tests/test_api.py::test_prod_env_without_auth_fails_startup`.
- **Effort:** 0.5 day.

### B5 — Kill remaining `extraction_agreement=0.5` hardcodes

- **DD finding:** Confidence score is "actually two-component, not three."
- **Current state (verified):** Mostly fixed. `Unit.extraction_agreement` is now a Pydantic field; pipeline.py:189–190 sets it from consensus agreement; `proof.py:120` reads it via `getattr`. **But four hardcodes remain in `verify/derived.py:198, 351, 452, 563`** — derived answers (P=V×I, T_junction, voltage margin, current budget) all default to 0.5 regardless of the source units' agreement scores.
- **Work:** Each derived answer must compute `extraction_agreement` as the **min** of the source units' agreement scores (worst-case), not 0.5.
- **Acceptance:** New test `tests/test_derived.py::test_derived_propagates_min_agreement` verifies that `derive_power(unit_v, unit_i)` returns confidence with `extraction_agreement == min(unit_v.agreement, unit_i.agreement)`.
- **Effort:** 1 hr.

### Track-D groundwork — book customer dev calls

- **Work:** Identify 30 working PCB engineers (LinkedIn, EEVblog, NSBE, robotics startup eng leads). Send personal cold-email — not "try my product," but "20-min screen-share where I watch you do datasheet review." Goal: 8 booked by end of Week 1, 20 booked by end of Week 4.
- **Acceptance:** Calendar shows 8 calls.
- **Effort:** 2 hrs of writing + ongoing followup.

**Sprint 0 exit criteria:** All seven items above merged. CI green. README updated. **Diligence-call posture:** "We closed those before you asked."

---

## 3. Sprint 1 — Production Hardening (Weeks 2–3, ~10 working days)

**Goal:** Make the system safe to launch a paid tier on. After this sprint, you should be willing to handle 100 concurrent users.

### A1 — Replace synchronous `time.sleep` ingest with a job queue

- **DD finding:** "For a 50-page datasheet at 4s delay, that's 200 seconds of a thread doing nothing. Batch upload spawns unbounded threads."
- **Current state (verified):** `pipeline.py:173, 207`, `gemini_extract.py:598`, `page_classifier.py:90` use `time.sleep`. `routers/ingest.py:210` spawns a `threading.Thread` per upload. No bounded executor.
- **Work:**
  1. Introduce a process-wide `concurrent.futures.ThreadPoolExecutor` with `max_workers = AKILI_INGEST_WORKERS` (default 4).
  2. Replace `threading.Thread(target=...)` in `routers/ingest.py` with `executor.submit(...)`.
  3. Replace blocking `time.sleep` calls inside the pipeline with a non-blocking `Event.wait(timeout=...)` that respects shutdown signals.
  4. Add an in-memory job-status table keyed by `doc_id`: `pending | running | done | error`. Persist last-known status to DB so SSE reconnects work.
  5. **Defer Redis/RQ/Celery** until concurrent users exceed 50.
- **Acceptance:** Load test (`scripts/load_test_ingest.py`, new file) submits 20 PDFs concurrently. No process exceeds 4 active extractions at any time. All complete or fail cleanly. Total wall time ≤ 1.2× single-PDF time × ceil(20/4).
- **Files:** `src/akili/api/routers/ingest.py`, `src/akili/ingest/pipeline.py`, `src/akili/ingest/gemini_extract.py`, `src/akili/ingest/page_classifier.py`, new `src/akili/jobs/executor.py`, new `src/akili/jobs/status.py`.
- **Effort:** 3 days.

### A3 — UID + fingerprint rate limiting for anonymous tier

- **DD finding:** Anonymous tier is IP-only and trivially bypassed behind a load balancer.
- **Current state (verified):** `app.py:101–115` falls back to `get_remote_address` when no auth header. Behind Cloud Run / Vercel that's the LB IP.
- **Work:**
  1. When auth is disabled, derive a stable fingerprint from `X-Forwarded-For` (last hop) + `User-Agent` hash + a session cookie set on first request.
  2. When `X-Forwarded-For` is unset, fall back to `request.client.host`.
  3. Document the rate-limit-key logic in `docs/SECURITY.md`.
- **Acceptance:** Unit test for `_rate_limit_key` covering: authed request → uid; anonymous with XFF → "fp:..."; anonymous without XFF → IP.
- **Effort:** 0.5 day.

### A8 — Eliminate vestigial `_conn()` legacy methods in stores

- **DD finding:** Connection-per-operation pattern.
- **Current state (verified):** Already mostly fixed. `Store`, `CorrectionStore`, `UsageStore` all use `ConnectionManager`. But `repository.py:51–53` still has a legacy `_conn()` that creates a fresh `sqlite3.connect`. Worth verifying nothing calls it.
- **Work:**
  1. Grep for `self._conn()` calls. Replace with `self._mgr.connection()`.
  2. Delete the legacy method.
  3. Add `ConnectionManager.close()` to lifespan shutdown in `app.py`.
- **Acceptance:** No `_conn(` matches except in `connection.py`. App shuts down cleanly (no "connection not closed" warnings under `pytest -W error`).
- **Effort:** 1 hr.

### B4 — LLM provider abstraction

- **DD finding:** "One provider, one model. The 'LLM abstraction' is on the roadmap but doesn't exist in code."
- **Current state (verified):** Direct `import google.generativeai as genai` in `gemini_extract.py`, `gemini_format.py`, `page_classifier.py`. No `llm/` module.
- **Work:**
  1. New module `src/akili/llm/` with:
     - `base.py` — `LLMProvider` ABC: `extract_structured(prompt, image, schema, **kwargs) -> dict`, `format_text(prompt, **kwargs) -> str`, `name: str`, `model_id: str`.
     - `gemini.py` — wraps current `genai` calls.
     - `openai.py` — uses Responses API + structured outputs (or vision if available).
     - `anthropic.py` — uses Claude vision.
     - `factory.py` — `get_provider(name: str) -> LLMProvider` from `AKILI_LLM_PROVIDER` env (default `gemini`).
  2. Refactor `gemini_extract.py` and `gemini_format.py` to call through the provider interface.
  3. CI: install `openai` and `anthropic` only as `pip install -e ".[llm-extra]"` to keep base install lean.
  4. Document tradeoffs in `docs/LLM-PROVIDERS.md`.
- **Non-goals:** Do **not** rewrite the prompts. Do **not** change defaults. The extraction prompt is the asset; the goal is dependency neutrality, not migration.
- **Acceptance:**
  - All existing tests pass with `AKILI_LLM_PROVIDER=gemini` (the default).
  - Three new mock-based tests verify each provider's adapter returns a `PageExtraction` of the correct shape.
  - One live integration test (`@pytest.mark.integration`) per provider that runs the same prompt and validates the result against ground truth.
  - Benchmark (B1) run with all three providers; results published.
- **Effort:** 5 days.

**Sprint 1 exit criteria:** Production-grade. Can stand up a paid tier behind it without breaking. LLM dependency neutralized. **Diligence-call posture:** "Here's our concurrency load test, here's our provider matrix benchmark."

---

## 4. Sprint 2 — Diligence Credibility Pack (Weeks 4–6, ~15 working days)

**Goal:** When the partner asks "show me the data," you have it. This sprint is the single highest-leverage block of work in the entire 12-week plan.

### B1 — Expand benchmark to 150 questions × 15 chips × 5 manufacturers

- **DD finding:** "50 easy questions on famous chips, all over-represented in Gemini's training data."
- **Current state (verified):** `benchmark/dataset.json` has 50 Q&A across 5 chips (ATmega328P, ESP32, STM32F103, NE555, LM7805). All from the same general consumer-electronics segment.
- **Work:**
  1. **Diversify chips** to cover failure modes: regulators (TPS7A20, AP2112, LT3045, MIC5219), ADCs (ADS1115, MCP3008), MCUs (STM32F407, ATmega328P, RP2040, ESP32), drivers (DRV8825, A4988), connectors (Molex Pico-Lock with confusing pinout tables), passives (Murata GRM ceramic capacitor with derating curve).
  2. **Stratify by difficulty:**
     - **30% easy** (front-page features, single-cell lookups).
     - **50% medium** (electrical characteristics tables — values with conditions).
     - **20% hard** (derating curves, cross-page tables, conditional units, absolute-max-vs-recommended distinction).
  3. **Five manufacturers** (TI, ST, Microchip, Diodes Inc, Murata, ON Semi — pick five) to neutralize "trained on Microchip docs" objections.
  4. **Hand-label** each question with: expected answer, source page, source bbox (approximate), difficulty band, "trap" flag (questions designed to make hallucinators fail — e.g. asking for "max input voltage" on a regulator that has both absolute-max and recommended-max).
- **Acceptance:** `benchmark/dataset.json` has ≥150 questions with the schema above, schema-validated by a new `tests/benchmark/test_dataset_schema.py`.
- **Effort:** 4 days. (~30 min per question, including reading the datasheet.)

### B2 — False-accept rate as headline metric

- **DD finding:** "+15% accuracy" is a vanity metric. The number that matters in safety-critical industries is **how often Akili says VERIFIED when the answer is wrong.**
- **Current state (verified):** `benchmark/run_benchmark.py` reports overall accuracy. No false-accept rate.
- **Work:**
  1. New metric: **false-accept rate** = `count(status=VERIFIED ∧ correct=False) / count(status=VERIFIED)`.
  2. New metric: **REFUSE precision** = `count(status=REFUSED ∧ correct=False) / count(status=REFUSED)` — i.e., how often we correctly refused.
  3. Output a confusion matrix: rows = (correct, incorrect, unknown), columns = (VERIFIED, REVIEW, REFUSED).
  4. CI regression: false-accept rate ≤ 1% gates merges to `main`. (Today; tighten to 0.5% by end of quarter.)
- **Acceptance:** `benchmark/run_benchmark.py --check-regression` fails if false-accept rate exceeds threshold. README's table swapped from "+15% accuracy" to "0.X% false-accept rate" as headline.
- **Effort:** 1 day.

### B3 — Head-to-head benchmark vs GPT-5 + Claude Sonnet 4.5

- **DD finding:** The threat is frontier models adding native PDF extraction. Show you measure against them.
- **Current state (verified):** Baseline is "raw Gemini." No comparison to other frontier models with their native PDF tooling.
- **Work:**
  1. Add baselines to `run_benchmark.py`: `gpt-5-mini` with PDF input, `claude-sonnet-4.5` with PDF input, raw `gemini-3-flash`. Each gets the same datasheet PDF and the same 150 questions, no preprocessing.
  2. Compare against AKILI's full pipeline.
  3. Publish results matrix: model × difficulty band → (accuracy, false-accept rate, latency, cost-per-query).
  4. Generate a one-page PDF for the data room.
- **Acceptance:** `benchmark/results/2026-Q2.json` exists. README's benchmark section shows AKILI ≥ best baseline on **medium** and **hard** difficulty bands. (Easy band may be a tie — that's expected and OK.)
- **Effort:** 3 days. (Most of the time is API latency + cost; budget $200–500 for one full run.)

### B6 — Z3 cross-parameter physical constraints

- **DD finding:** "Z3 is marketing, not a moat. Today it's arithmetic assertions."
- **Current state (verified):** `verify/z3_checks.py` (~700 LOC) handles unit normalization, contradiction detection, and `min ≤ typ ≤ max`. Real but shallow.
- **Work:** Add 5 cross-parameter constraint types. Each is a Z3 model wired to canonical objects:
  1. **Power-budget consistency:** for any `Range` with label "P", `P_max ≥ V_op_max × I_op_max` for all extracted V/I in the same component.
  2. **Thermal viability:** if `θ_JA` and `T_J_max` and `T_A_max` exist, `T_J_max ≥ T_A_max + P_max × θ_JA`.
  3. **LDO dropout margin:** for regulators, `V_in_min - V_out ≥ V_dropout`.
  4. **Voltage-rail compatibility:** if a part has `V_supply_min..V_supply_max`, flag any spec measured at `V = X` where `X` is outside that range.
  5. **Absolute-max vs operating disambiguation:** if both abs-max and recommended values exist for the same parameter, abs-max ≥ recommended (catches a common Gemini extraction bug where it confuses them).
- **Wire-up:** Z3 results feed back into `verify/proof.py` as a `verification_strength` modifier — facts that violate physical constraints get reduced confidence.
- **Acceptance:** Each constraint has 2–3 test cases (`tests/test_z3_checks.py`). At least one **real** datasheet in the benchmark surfaces a constraint violation that catches an extraction error. (This is the demo moment in the pitch.)
- **Effort:** 4 days.

### B7 — Intent classifier replaces keyword substring matching (start; finish in S3)

- **DD finding:** "`'voltage' in question` triggers voltage rules on 'voltage divider design' questions."
- **Current state (verified):** `verify/proof.py:138` `_has_any` does naive substring matching across all 30 rules. There is no question-classification step.
- **Work (S2 portion):**
  1. Define an `Intent` enum: `voltage_spec`, `current_spec`, `power_spec`, `thermal_query`, `pin_lookup`, `package_query`, `timing_query`, `temperature_query`, `general_question`, `out_of_scope`.
  2. Build a **regex + keyword classifier** (deterministic, no LLM) as the first pass — covers ~70% of cases.
  3. Add an `Intent` parameter to rule signatures; rules become `@rule(priority=200, intent=Intent.voltage_spec)` and only fire when intent matches.
  4. Run benchmark with and without intent filtering — measure precision improvement.
- **Defer to S3:** LLM-backed classifier as a fallback for ambiguous questions.
- **Acceptance:** Benchmark false-accept rate decreases by ≥ 30% on the **medium** difficulty band after intent filtering.
- **Effort:** 3 days (rest in S3).

**Sprint 2 exit criteria:** Data room contains: expanded benchmark (150 questions), confusion matrix per provider, false-accept rate < 1%, head-to-head vs GPT-5/Claude with AKILI winning on medium+hard. **Diligence-call posture:** "Here's the dataset, here's our methodology, here's the script you can re-run."

---

## 5. Sprint 3 — Moat & Workspace (Weeks 7–9, ~15 working days)

**Goal:** The features that determine retention and the Series A pitch in 12 months.

### B7 (continued) — LLM intent classifier fallback

- **Work:** When the regex classifier returns `Intent.general_question` or low-confidence, call a small Gemini/GPT call (~50ms latency target) to classify. Cache aggressively (the same question text hashes to the same intent).
- **Acceptance:** Benchmark false-accept rate ≤ 0.5% on medium band.
- **Effort:** 2 days.

### C1 — Real-PDF benchmark in CI

- **DD finding:** "Every Gemini call is mocked. The benchmark is the only thing exercising the live path, and it doesn't run in CI."
- **Current state (verified):** Benchmark exists (`benchmark/run_benchmark.py`); CI workflow exists (`benchmark` GitHub Actions). Need to verify it actually runs on PRs and gates merges.
- **Work:**
  1. Run benchmark nightly on `main` and on every PR labeled `benchmark`.
  2. Cache extracted canonical objects (keyed by PDF SHA + extractor version) to avoid re-running Gemini on every PR.
  3. Surface accuracy + false-accept rate as a status check.
- **Acceptance:** A PR that regresses false-accept rate above threshold cannot be merged.
- **Effort:** 1 day.

### C3 — Audit trail export (compliance moat MVP)

- **DD finding:** "Compliance audit trail can't be replicated by a base model. But you don't have one yet."
- **Current state (verified):** Store has `audit_log` plumbing; no export endpoint or UI.
- **Work:**
  1. New endpoint `GET /documents/{id}/audit?format=pdf|csv|json` — emits the full provenance chain: who uploaded, when; every extracted unit with timestamp + extractor version + Gemini model id; every correction with corrector + timestamp + diff; every query with answer + confidence + proof points.
  2. PDF export uses ReportLab (no Chromium) — keep deps lean.
  3. Sign exports with HMAC keyed on `AKILI_AUDIT_SIGNING_KEY` so tampering is detectable.
  4. Document in `docs/COMPLIANCE.md`.
- **Acceptance:** End-to-end test: ingest a doc, make a correction, run a query, export audit, verify HMAC, verify all events present.
- **Effort:** 3 days. *This is the demo for an aerospace/medical pilot — even one screenshot is worth its weight.*

### D1 — Project workspace (data model)

- **DD finding:** "Demo is a single-doc chat. No retention story."
- **Current state (verified):** No `Project` concept anywhere.
- **Work:**
  1. Schema: `projects(id, name, owner_uid, created_at)`, `project_documents(project_id, doc_id)`. Migrations for both SQLite and PG.
  2. API: `POST /projects`, `GET /projects`, `POST /projects/{id}/documents`, `DELETE /projects/{id}/documents/{doc_id}`.
  3. Query takes optional `project_id` for project-scoped context.
  4. Frontend: project picker in Header, sidebar shows project tree.
- **Acceptance:** A user can create "Motor Controller v2," add 3 datasheets, ask a question, get an answer. Refresh the page, the project still exists, the chat history loads.
- **Effort:** 4 days.

### D2 — Persistent chat per document

- **Work:**
  1. Schema: `chat_messages(id, doc_id, project_id, user_id, role, text, response_json, created_at)`.
  2. API: `GET /documents/{id}/chat`, `POST /documents/{id}/chat`. Auto-loads history on doc select.
  3. Frontend: `useChat(docId)` hook replaces local state.
- **Acceptance:** Send a question, refresh the browser, the conversation is still there.
- **Effort:** 2 days.

### D5 (continued) — Customer dev study

- **Work:** By end of Week 9, complete 20 watch sessions. Synthesize findings into a doc: top 5 query patterns, top 3 pain points, top 3 product surprises (where the user expected behavior we don't have).
- **Acceptance:** `docs/CUSTOMER-DEV-FINDINGS.md` exists.
- **Effort:** ~10 hrs in Sprint 3 (continuing from S0 booking).

**Sprint 3 exit criteria:** Workspace + persistent chat live. Audit export demo-ready. Real customer feedback in hand. **Diligence-call posture:** "Here's a 30-second recording of an actual aerospace engineer using the audit export."

---

## 6. Sprint 4 — Plugin & GTM (Weeks 10–12, ~15 working days)

**Goal:** The product-led-growth wedge plus the picks-and-shovels API positioning.

### D3 — Comparison matrix UX

- **Work:** Cross-doc compare endpoint already exists (`/compare`). Build the UI: select 2–5 components, pick parameters from a list, get a sortable matrix with proof links and best-value highlighting. Export to CSV.
- **Acceptance:** A user can compare 5 voltage regulators by V_dropout, I_quiescent, V_out_accuracy, package, and export the result.
- **Effort:** 3 days.

### D4 — KiCad plugin alpha

- **DD finding:** "The plugin is the proof point that 'Akili sits inside the workflow,' which is the actual investment thesis."
- **Work:**
  1. Standalone repo `akili-kicad`.
  2. Right-click on a component in the schematic → "Verify with Akili" → opens a panel showing: extracted absolute-max ratings, recommended operating ranges, your design's operating conditions (parsed from net labels) → green/yellow/red verdict per parameter.
  3. Publishes to KiCad Plugin and Content Manager.
- **Non-goals:** Polish, KiCad 9 support, multi-board projects. This is an alpha.
- **Acceptance:** A working video demo. 1 external alpha tester from the customer-dev pool installs it.
- **Effort:** 6 days.

### C2 — Component knowledge graph (corpus expansion)

- **Work:** Pre-ingest the top 100 chips by query volume from customer-dev sessions. Stored as the public corpus. New users get instant verified answers for these chips with no upload.
- **Acceptance:** `scripts/populate_corpus.py` produces a verified corpus of 100 chips. Library UI surfaces them.
- **Effort:** 2 days of script work, 1–2 days of Gemini API spend.

### C4 — Correction pattern flywheel surfaced in UI

- **Work:** `learn/pattern_analyzer.py` already exists. Surface its output in the UI: "We've corrected this same extraction error 7 times across 4 datasheets — apply auto-correction rule?" Engineers click yes; the system learns.
- **Acceptance:** Once an engineer applies an auto-correction rule, the next datasheet that triggers the pattern gets corrected silently and logged in the audit trail.
- **Effort:** 2 days.

### D5 (continued) — Soft launch

- **Work:** With 20 customer-dev users now familiar with the product, post on EEVblog forum, r/PrintedCircuitBoard, and Hacker News. Goal: 200 signups in first 72 hrs, 5 paying conversions.
- **Acceptance:** Public launch metrics dashboard tracks: visits → signups → first-doc-uploaded → first-query-asked → second-session → paid conversion. Each step has a baseline number.
- **Effort:** Ongoing.

**Sprint 4 exit criteria:** KiCad plugin shipped to alpha testers. Public corpus of 100 chips. Comparison matrix in production. **Diligence-call posture:** "Here's our PLG funnel from launch week."

---

## 7. Definition of Done — DD-Pack Checklist

When all four sprints are complete, the diligence pack contains:

- [ ] Benchmark dataset: 150 Q&A × 15 chips × 5 manufacturers, schema-validated. (B1)
- [ ] Confusion matrix per LLM provider; false-accept rate ≤ 0.5%. (B2)
- [ ] Head-to-head benchmark vs GPT-5 + Claude Sonnet 4.5 with AKILI winning on medium+hard bands. (B3)
- [ ] LLM provider abstraction with three implementations and benchmark results for each. (B4)
- [ ] All `extraction_agreement` paths use real consensus scores, not 0.5. (B5)
- [ ] Five Z3 cross-parameter constraints active. At least one catches a real extraction error in the benchmark. (B6)
- [ ] Intent classifier deployed; benchmark false-accept rate dropped ≥ 30% on medium band. (B7)
- [ ] PDF authorization tightened across all document-scoped endpoints. (A2)
- [ ] Strict UUID `doc_id` validation. (A4)
- [ ] No bare `catch {}` in frontend; ESLint enforces. (A5)
- [ ] Gemini model pinned to dated stable; fallback configured. (A6)
- [ ] Auth fail-closed in production-like environments. (A7)
- [ ] Bounded executor for ingest; load test at 20 concurrent uploads. (A1)
- [ ] UID + fingerprint rate limiting. (A3)
- [ ] Project workspace + persistent chat. (D1, D2)
- [ ] Comparison matrix UI. (D3)
- [ ] KiCad plugin alpha installed by ≥ 1 external user. (D4)
- [ ] Audit trail export with HMAC signature. (C3)
- [ ] Public corpus of 100 chips. (C2)
- [ ] Customer-dev findings doc; 20 watch sessions completed. (D5)

---

## 8. Out of Scope (Explicitly Deferred)

The following are valuable but **not** in this 12-week plan. Each is named so future-you doesn't quietly add them:

- Altium plugin, VS Code extension, GitHub Action for CI. *(Phase 2 platform play. After we have one shipping plugin.)*
- RBAC, SSO, on-prem deployment. *(Enterprise-tier features. After 2–3 enterprise pilots in pipeline.)*
- Mechanical / systems / field-tech expansion. *(TAM expansion story. Real after PLG wedge is proven.)*
- Datasheet diff. *(Feature, not differentiator. Wait for pull from real users.)*
- Multi-language datasheet support (JP/KR/CN). *(Unblocked once a customer asks for it.)*
- Real Redis/Celery job queue. *(Unblocked at >50 concurrent ingest users. The bounded ThreadPoolExecutor handles us until then.)*
- Custom extraction templates / fine-tuning. *(Unblocked when a paying customer offers ≥ $50K to make it work.)*

---

## 9. Risks & Watchlist

| Risk | Likelihood | Mitigation |
|---|---|---|
| Customer-dev pool doesn't yield 20 engineers in 6 weeks | Medium | Backfill from EEVblog forum DMs; offer $50 Amazon for completed session. |
| GPT-5/Claude PDF tools score ≥ AKILI on hard band | Medium | Then the moat is the audit trail + Z3 constraints + corrections flywheel, not the extraction. Adjust messaging; do not panic. |
| Benchmark expansion takes > 4 days | High | Hire one EE student via Upwork ($25/hr × ~30 hr) to label questions. |
| KiCad plugin alpha shipped, nobody uses it | Medium | Plugin is a credibility artifact for the deck; usage is upside, not the goal of S4. |
| Solo founder overload by Week 8 | High | Hire a contract backend engineer for Sprint 2 (~$8K for 3 weeks) to free founder for benchmark + customer dev. |

---

## 10. How to Use This Doc

- Each sprint is a GitHub project board. One column per track. Each `Aₙ`/`Bₙ`/`Cₙ`/`Dₙ` becomes one issue.
- Start every Monday by reviewing exit criteria of the current sprint. Do not begin the next sprint until the prior sprint exits cleanly.
- Update this doc inline as items complete. Strikethrough and link the merged PR. (`~~A2~~ → #142`)
- Re-run the IC-Objection map (§0) before any investor meeting. It is the order in which they will ask questions.

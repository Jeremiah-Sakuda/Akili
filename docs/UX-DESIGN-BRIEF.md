# Akili — UX Design Brief

**Document purpose:** Design brief for the Akili web UI. Use this to scope flows, define screens, and align visual direction with product goals.  
**Audience:** UX / product designers.  
**Last updated:** February 2026.

---

## 1. Product context

**What Akili is**  
Akili is a deterministic verification layer for technical documentation (datasheets, pinout tables, schematics). It turns PDFs into a "canonical truth store" (typed facts with coordinates) and only answers questions when the answer can be **proven** from that store -- otherwise it **refuses**. The value proposition: "No citations; only proof."

**Why a UI**  
The UI should let users (and judges in a demo) **ingest documents**, **see what was extracted** (canonical facts + coordinates), **ask questions**, and **see the exact place on the document that proves the answer** -- or see a clear refusal. The experience should feel like a verification workspace, not a chatbot.

**Current capabilities (supported in the UI)**  
- Ingest: upload PDF -> get `doc_id` + counts of units, bijections, grids.
- List documents: see all ingested docs with counts.
- Inspect canonical: view units, bijections, grids for a document (with page and coordinates).
- Query: submit a question for a document -> get either **answer + proof + confidence** or **REFUSE** (short reason).
- Confidence tiers: answers classified as VERIFIED (green), REVIEW (yellow), or REFUSED (red) based on three-component scoring.
- Shadow formatting: opt-in Gemini rephrasing, labeled as "AI-rephrased" when active.

---

## 2. User goals and scenarios

| Goal | Scenario |
|------|----------|
| Get a document into the system | User uploads a PDF; they need clear confirmation (doc_id, counts) and to see the doc in the document list. |
| Understand what Akili "knows" | User selects a document and wants to see all canonical facts (units, bijections, grids) and their coordinates. |
| Ask a question and trust the answer | User asks a question (e.g. "What is pin 5?"); they need to see the answer, the confidence level, the proof (where on the doc it came from), and optionally the same region highlighted on the PDF. |
| Understand when Akili won't answer | When the system refuses, the user should see a clear "REFUSED" state and the reason -- no answer-like text, no gray area. |
| Assess answer reliability | When confidence is in the REVIEW range, the user should see a yellow indicator and understand the answer needs confirmation. |
| Demo to judges | A judge should be able to: upload a doc, ask a question, and point at the PDF to show "the answer is proven here." |

---

## 3. Design principles

- **Control plane, not chat.** The UI is a verification workspace: document-centric, stateful, and proof-forward. Avoid a generic "AI chat" layout.
- **Proof is first-class.** Every proven answer must be tied to visible proof (coordinates, source id/type) and, where possible, to a highlight on the PDF.
- **Refusal is explicit.** When Akili refuses, it should be prominent and calm (e.g. dedicated block, amber tone). No fake answers or vague "I'm not sure" that looks like an answer.
- **Confidence is transparent.** The three-tier confidence system (VERIFIED / REVIEW / REFUSED) should be immediately visible, with color-coded badges and optional percentage.
- **Formatting is labeled.** When AI rephrasing is used, it must be clearly distinguished from the raw verified fact. The user should never confuse a Gemini-rephrased answer with the deterministic proof.
- **Canonical store is inspectable.** Users should be able to see what's in the truth store (units, bijections, grids) and their coordinates -- supporting trust and debugging.
- **Engineering-grade tone.** Visual language should feel precise, confident, and suitable for technical/ops contexts. No playful or consumer-chat aesthetics.

---

## 4. Visual direction (high level)

- **Tone:** Engineering / mission-critical. Confident, legible, minimal decoration.
- **Palette (suggested):**
  - Verified: restrained green (>= 85% confidence).
  - Review: amber/yellow (50-85% confidence, needs confirmation).
  - Refused: red or deep amber (< 50% confidence or deterministic refusal).
  - Accent: one clear color for primary actions and links (e.g. blue).
  - Dark mode option: charcoal/slate background, light text; same semantic colors.
- **Typography:** Clear hierarchy (document and query result primary; proof and metadata secondary). Monospace for coordinates, ids, confidence percentages, and canonical data.
- **Refusal treatment:** Dedicated block or card: "REFUSED" + reason. Distinct from the REVIEW state.

---

## 5. Information architecture

**Primary areas:**

1. **Document intake**
   - Upload PDF.
   - Outcome: doc_id, filename, page count, counts (units, bijections, grids).

2. **Document list**
   - All ingested documents.
   - Per row: filename, doc_id (copyable), page count, units/bijections/grids counts.
   - Action: select document (drives PDF viewer and query context).

3. **Canonical inspector**
   - For selected document only.
   - Sections: Units | Bijections | Grids.
   - Per item: id, relevant fields (value, mapping, dimensions), **page**, **(x, y)**.

4. **PDF viewer**
   - Renders the selected document.
   - **Overlay:** when a query returns a proof, show highlights/rectangles at proof coordinates (page + bbox or point).

5. **Query**
   - Document selector (or pre-filled from selection).
   - Question input.
   - Submit -> result (answer + proof + confidence, or refuse).

6. **Result**
   - **If verified/review:** Confidence badge (green/yellow) + percentage + answer text + "Proof" list + "Show on document". If AI-rephrased, "AI-rephrased" label.
   - **If refuse:** "REFUSED" badge + reason; no answer block.

**Layout:**
- **Left:** Document list + canonical inspector (or tabs).
- **Center:** PDF viewer (with overlay when proof exists).
- **Right:** Chat-style query input + result (answer with confidence or refuse).

---

## 6. Screen / area specs

### 6.1 Ingest (upload)

- **Input:** File drop zone or picker; accept PDF only.
- **On success:** Show doc_id (with copy), filename, page count, units/bijections/grids counts. Short confirmation line (e.g. "Document canonicalized. You can query it below.").
- **On error:** Clear message (e.g. "Upload failed", "Invalid PDF").
- **No chat history.** Ingest is a one-off action with a clear outcome.

### 6.2 Document list

- **Content:** One row/card per document: filename, doc_id (copyable), page count, units count, bijections count, grids count.
- **Action:** Select/open document -> loads in PDF viewer and sets query context.
- **Empty state:** Message like "No documents yet. Upload a PDF to get started."

### 6.3 Canonical inspector

- **Scope:** Selected document only.
- **Sections:** Units | Bijections | Grids (tabs or accordions).
- **Units:** Rows with id, label, value, unit of measure, page, (x, y).
- **Bijections:** Rows with id, mapping (key -> value), page, (x, y).
- **Grids:** Rows with id, rows x cols, cell count, page, (x, y).

### 6.4 PDF viewer

- **Content:** Rendered PDF for selected document (pdfjs-dist).
- **Overlay (when proof exists):** Semi-transparent rectangles or markers at proof coordinates; color by source type.
- **Empty state:** "Select a document to view" or "Upload and select a document."

### 6.5 Query

- **Document:** Pre-filled from current selection.
- **Question:** Single-line or short text area.
- **Submit:** Button or Enter.
- **Loading:** "Verifying..." or similar; disable submit until response.

### 6.6 Result (verified / review)

- **Confidence badge:** Green "VERIFIED" or yellow "REVIEW" with percentage.
- **Answer:** Prominent line with the proven answer text.
- **Formatting label:** "AI-rephrased" badge if Shadow Formatting was used.
- **Proof:** List of proof points: page, x, y, source_id, source_type.
- **Action:** "Show on document" -> focus PDF viewer on relevant page and show overlay at proof coordinates.

### 6.7 Result (refuse)

- **State label:** "REFUSED" (clear, visible, red/amber badge).
- **Reason:** Short copy (e.g. "No canonical fact derives this answer.").
- **No answer block.** No placeholder text that could be read as an answer.

---

## 7. Content and copy

- **Ingest success:** e.g. "Document canonicalized. You can query it below."
- **Proof label:** "Proof" (with list of page, x, y, source).
- **Show on document:** "Show on document" or "Show proof on PDF."
- **Verified:** "VERIFIED" + green badge + confidence %.
- **Review:** "REVIEW" + yellow badge + confidence % + implicit "needs confirmation."
- **Refuse:** "REFUSED" + reason from API (e.g. "No canonical fact derives this answer.").
- **AI-rephrased:** "AI-rephrased" in gray badge, next to confidence badge.
- **Empty documents:** "No documents yet. Upload a PDF to get started."
- **Empty canonical:** "No units/bijections/grids for this document."

---

## 8. States to design for

| State | Notes |
|-------|--------|
| **Loading (ingest)** | Upload in progress; show progress or spinner. |
| **Loading (query)** | "Verifying..."; disable query submit. |
| **Empty (no documents)** | Clear CTA to upload. |
| **Empty (document, no canonical)** | Possible if extraction returned nothing; show message. |
| **Answer - VERIFIED** | Green badge, answer + proof list + "Show on document." |
| **Answer - REVIEW** | Yellow badge, answer + proof list + "needs confirmation" implicit. |
| **Answer - AI-rephrased** | "AI-rephrased" label alongside confidence badge. |
| **Refuse** | REFUSED badge + reason; no answer. |
| **Error (network / server)** | Generic error message; retry option where appropriate. |
| **Error (invalid file)** | e.g. "Please upload a valid PDF." |

---

## 9. Constraints and technical notes

- **API:** REST (FastAPI). Endpoints: `POST /ingest`, `POST /query` (returns `confidence`, `confidence_tier`, `formatting_source`), `GET /documents`, `GET /documents/{doc_id}/canonical`, `GET /documents/{doc_id}/file`.
- **Proof format:** List of objects with `x`, `y`, optional `source_id`, `source_type`. Bbox may be available from canonical store for overlay.
- **Confidence:** `ConfidenceScore` object with `extraction_agreement`, `canonical_validation`, `verification_strength`, `overall`. `confidence_tier`: `"verified"`, `"review"`, or `"refused"`.
- **Formatting source:** `"verified_raw"` (default) or `"gemini_rephrase"` (when AI rephrasing is requested and succeeds).
- **PDF in browser:** pdfjs-dist; overlay must align with page coordinates (same coordinate system as API).
- **Document selection:** Frontend tracks selected `doc_id` for query and canonical inspector; PDF fetched via `GET /documents/{id}/file`.

---

## 10. Open questions for design

1. **Overlay coordinate system:** Confirm with backend how the viewer should scale to PDF page dimensions.
2. **Mobile / small screen:** Full three-pane may not fit; confirm priority (e.g. query + result first, PDF in a separate tab).
3. **Accessibility:** Keyboard flow, focus order, and screen reader treatment for confidence tiers and proof list.
4. **Copy:** Finalize microcopy (especially refuse reason and empty states) with product.

---

## 11. Out of scope for this brief

- Backend or API changes (except where noted as "optional" or "if added").
- Detailed visual specs (typography scale, spacing tokens) -- defined in `UI-SPEC.md`.
- Multi-user or org features (Firebase auth is optional and implemented).
- Chat history or multi-turn conversation.

---

*This brief is the single source for UX scope and direction for the Akili web UI. When in doubt, align with "verification workspace, proof-first, refusal explicit, canonical inspectable."*

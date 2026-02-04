# Akili — UX Design Brief

**Document purpose:** Design brief for the Akili web UI. Use this to scope flows, define screens, and align visual direction with product goals.  
**Audience:** UX / product designers.  
**Last updated:** February 2025.

---

## 1. Product context

**What Akili is**  
Akili is a deterministic verification layer for technical documentation (datasheets, pinout tables, schematics). It turns PDFs into a “canonical truth store” (typed facts with coordinates) and only answers questions when the answer can be **proven** from that store—otherwise it **refuses**. The value proposition: “No citations; only proof.”

**Why a UI**  
The UI should let users (and judges in a demo) **ingest documents**, **see what was extracted** (canonical facts + coordinates), **ask questions**, and **see the exact place on the document that proves the answer**—or see a clear refusal. The experience should feel like a verification workspace, not a chatbot.

**Current capabilities (to support in the UI)**  
- Ingest: upload PDF → get `doc_id` + counts of units, bijections, grids.  
- List documents: see all ingested docs with counts.  
- Inspect canonical: view units, bijections, grids for a document (with page and coordinates).  
- Query: submit a question for a document → get either **answer + proof** (list of coordinates/sources) or **REFUSE** (short reason).

---

## 2. User goals and scenarios

| Goal | Scenario |
|------|----------|
| Get a document into the system | User uploads a PDF; they need clear confirmation (doc_id, counts) and to see the doc in the document list. |
| Understand what Akili “knows” | User selects a document and wants to see all canonical facts (units, bijections, grids) and their coordinates. |
| Ask a question and trust the answer | User asks a question (e.g. “What is pin 5?”); they need to see the answer, the proof (where on the doc it came from), and optionally the same region highlighted on the PDF. |
| Understand when Akili won’t answer | When the system refuses, the user should see a clear “REFUSED” state and the reason—no answer-like text, no gray area. |
| Demo to judges | A judge should be able to: upload a doc, ask a question, and point at the PDF to show “the answer is proven here.” |

---

## 3. Design principles

- **Control plane, not chat.** The UI is a verification workspace: document-centric, stateful, and proof-forward. Avoid a generic “AI chat” layout.  
- **Proof is first-class.** Every proven answer must be tied to visible proof (coordinates, source id/type) and, where possible, to a highlight on the PDF.  
- **Refusal is explicit.** When Akili refuses, it should be prominent and calm (e.g. dedicated block, amber tone). No fake answers or vague “I’m not sure” that looks like an answer.  
- **Canonical store is inspectable.** Users should be able to see what’s in the truth store (units, bijections, grids) and their coordinates—supporting trust and debugging.  
- **Engineering-grade tone.** Visual language should feel precise, confident, and suitable for technical/ops contexts (e.g. dashboards, verification tools). No playful or consumer-chat aesthetics.

---

## 4. Visual direction (high level)

- **Tone:** Engineering / mission-critical. Confident, legible, minimal decoration.  
- **Palette (suggested):**  
  - Verified / success: restrained green.  
  - Refuse: amber (warning, not error red).  
  - Accent: one clear color for primary actions and links (e.g. blue or cyan).  
  - Dark mode option: charcoal/slate background, light text; same semantic colors.  
- **Typography:** Clear hierarchy (document and query result primary; proof and metadata secondary). Consider monospace or technical sans for coordinates, ids, and canonical data.  
- **Refusal treatment:** Dedicated block or card: “REFUSED” + reason. No red error styling unless product wants to emphasize “do not use this as truth.”

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
   - Optional: “Locate on PDF” to scroll viewer to page and show a marker.

4. **PDF viewer**  
   - Renders the selected document.  
   - **Overlay:** when a query returns a proof, show highlights/rectangles at proof coordinates (page + bbox or point).  
   - Optional: legend (e.g. unit = green, bijection = blue, grid = orange).

5. **Query**  
   - Document selector (or pre-filled from selection).  
   - Question input.  
   - Submit → result (answer + proof, or refuse).

6. **Result**  
   - **If answer:** Answer text + “Proof” (list of proof points: page, x, y, source_id, source_type) + “Show on document” (focus PDF and overlay).  
   - **If refuse:** “REFUSED” + reason; no answer block.

**Suggested layout:**  
- **Left:** Document list + canonical inspector (or tabs).  
- **Center:** PDF viewer (with overlay when proof exists).  
- **Right:** Query input + result (answer or refuse).

**Alternative (narrow viewport):**  
Linear flow: Ingest → Documents → Select doc → Query → Result. Same building blocks; PDF + overlay can be a dedicated step or tab when “showing the proof.”

---

## 6. Screen / area specs

### 6.1 Ingest (upload)

- **Input:** File drop zone or picker; accept PDF only.  
- **On success:** Show doc_id (with copy), filename, page count, units/bijections/grids counts. Short confirmation line (e.g. “Document canonicalized. You can query it below.”).  
- **On error:** Clear message (e.g. “Upload failed”, “Invalid PDF”).  
- **No chat history.** Ingest is a one-off action with a clear outcome.

### 6.2 Document list

- **Content:** One row/card per document: filename, doc_id (copyable), page count, units count, bijections count, grids count.  
- **Action:** Select/open document → loads in PDF viewer and sets query context.  
- **Empty state:** Message like “No documents yet. Upload a PDF to get started.”

### 6.3 Canonical inspector

- **Scope:** Selected document only.  
- **Sections:** Units | Bijections | Grids (tabs or accordions).  
- **Units:** Rows with id, label, value, unit of measure, page, (x, y).  
- **Bijections:** Rows with id, mapping (key → value), page, (x, y).  
- **Grids:** Rows with id, rows×cols, cell count, page, (x, y).  
- **Optional:** “Locate on PDF” per row → scroll viewer to page and show marker at origin.

### 6.4 PDF viewer

- **Content:** Rendered PDF for selected document (e.g. PDF.js or equivalent).  
- **Overlay (when proof exists):** Semi-transparent rectangles or markers at proof coordinates; color by source type (unit / bijection / grid).  
- **Legend (if overlay used):** e.g. “Unit · Bijection · Grid” with matching colors.  
- **Empty state:** “Select a document to view” or “Upload and select a document.”

### 6.5 Query

- **Document:** Dropdown or selector (default to current document if one is selected).  
- **Question:** Single-line or short text area.  
- **Submit:** Button or Enter.  
- **Loading:** “Verifying…” or similar; disable submit until response.

### 6.6 Result (answer)

- **Answer:** Prominent line (e.g. “Answer: &lt;value&gt;”).  
- **Proof:** List of proof points: page, x, y, source_id, source_type.  
- **Action:** “Show on document” → focus PDF viewer on relevant page and show overlay at proof coordinates.  
- **No “related” or “similar” answers.** Only the single proven answer.

### 6.7 Result (refuse)

- **State label:** “REFUSED” (clear, visible).  
- **Reason:** Short copy (e.g. “No canonical fact derives this answer.”).  
- **No answer block.** No placeholder text that could be read as an answer.  
- **Tone:** Calm, informative (e.g. amber), not “error” unless product wants to stress “do not use.”

---

## 7. Content and copy

- **Ingest success:** e.g. “Document canonicalized. You can query it below.”  
- **Proof label:** “Proof” (with list of page, x, y, source).  
- **Show on document:** “Show on document” or “Show proof on PDF.”  
- **Refuse:** “REFUSED” + reason from API (e.g. “No canonical fact derives this answer.”).  
- **Empty documents:** “No documents yet. Upload a PDF to get started.”  
- **Empty canonical:** “No units/bijections/grids for this document.” (If applicable.)

---

## 8. States to design for

| State | Notes |
|-------|--------|
| **Loading (ingest)** | Upload in progress; show progress or spinner. |
| **Loading (query)** | “Verifying…”; disable query submit. |
| **Empty (no documents)** | Clear CTA to upload. |
| **Empty (document, no canonical)** | Possible if extraction returned nothing; show message. |
| **Answer with proof** | Answer + proof list + optional “Show on document.” |
| **Refuse** | REFUSED + reason; no answer. |
| **Error (network / server)** | Generic error message; retry option where appropriate. |
| **Error (invalid file)** | e.g. “Please upload a valid PDF.” |

---

## 9. Constraints and technical notes

- **API:** REST (FastAPI). Endpoints: `POST /ingest` (multipart file), `POST /query` (JSON: doc_id, question), `GET /documents`, `GET /documents/{doc_id}/canonical`.  
- **Proof format:** List of objects with `x`, `y`, optional `source_id`, `source_type`. Bbox (x1, y1, x2, y2) may be available from canonical store for overlay.  
- **PDF in browser:** Use a client-side PDF renderer (e.g. PDF.js); overlay must align with page coordinates (same coordinate system as API).  
- **Document selection:** Front-end must track selected `doc_id` for query and canonical inspector; PDF URL or blob can come from a separate “get PDF” endpoint if added later.

---

## 10. Open questions for design

1. **Layout:** Two-pane (list + viewer) vs three-pane (list | viewer | query+result)—which fits target viewport and demo flow?  
2. **PDF source:** Do we need a “get PDF by doc_id” endpoint so the UI can show the same file that was ingested, or is “viewer only when file is still in session” acceptable for v1?  
3. **Overlay coordinate system:** API uses normalized 0–1 or page-relative pixels; confirm with backend and document how the viewer should scale to PDF page dimensions.  
4. **Mobile / small screen:** Full three-pane may not fit; confirm priority (e.g. query + result first, PDF in a separate tab).  
5. **Accessibility:** Keyboard flow, focus order, and screen reader treatment for “answer vs refuse” and for proof list.  
6. **Copy:** Finalize microcopy (especially refuse reason and empty states) with product.

---

## 11. Out of scope for this brief

- Backend or API changes (except where noted as “optional” or “if added”).  
- Detailed visual specs (typography scale, spacing tokens)—to be defined in design system.  
- Auth, multi-user, or org features.  
- Chat history or multi-turn conversation.

---

*This brief is the single source for UX scope and direction for the Akili web UI. When in doubt, align with “verification workspace, proof-first, refusal explicit, canonical inspectable.”*

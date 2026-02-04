# Akili — UI Specification

**Purpose:** Visual and component-level spec for the Akili web UI. Use with `UX-DESIGN-BRIEF.md` for flows and content; this doc defines look, components, and layout.  
**Audience:** UI designers, front-end developers.  
**Last updated:** February 2025.

---

## 1. Design system (suggested)

### 1.1 Color

| Role | Light mode | Dark mode | Use |
|------|------------|----------|-----|
| **Background (primary)** | `#FAFAFA` / white | `#1A1D21` | Main canvas |
| **Background (secondary)** | `#F0F0F0` | `#25282C` | Sidebars, panels |
| **Text (primary)** | `#1A1A1A` | `#E8E8E8` | Headings, body |
| **Text (secondary)** | `#5C5C5C` | `#A0A0A0` | Labels, metadata |
| **Border** | `#E0E0E0` | `#3A3D42` | Dividers, cards |
| **Verified / success** | `#0D7B4C` | `#2DA66A` | Answer, proof, “canonical” |
| **Refuse / warning** | `#B45300` | `#E89540` | REFUSED state, caution |
| **Accent (primary action)** | `#0066CC` | `#4DA3FF` | Buttons, links, focus |
| **Accent (hover)** | `#0052A3` | `#6BB3FF` | Hover states |
| **Error** | `#C00` | `#E06060` | Upload/API errors |

### 1.2 Typography

| Element | Suggested | Size | Weight | Use |
|--------|-----------|------|--------|-----|
| **Page title** | Sans (e.g. system-ui or Inter) | 1.5rem | 600 | “Akili” / app title |
| **Section heading** | Same | 1rem | 600 | “Documents”, “Query”, “Proof” |
| **Body** | Same | 0.875rem | 400 | Descriptions, list content |
| **Data / coordinates** | Monospace (e.g. JetBrains Mono, ui-monospace) | 0.8125rem | 400 | doc_id, (x,y), source_id |
| **Answer (result)** | Same as body or slightly larger | 1rem | 500 | The proven answer text |
| **Refuse label** | Same | 1rem | 600 | “REFUSED” |

### 1.3 Spacing and layout

- **Base unit:** 4px (or 0.25rem).
- **Panel padding:** 16px (or 1rem).
- **Gap between panes:** 1px divider or 8px gap.
- **Card/block padding:** 12px–16px.
- **Input height:** 40px; button height 40px (or match inputs).

### 1.4 Components (patterns)

- **Buttons:** Primary = accent fill; secondary = border only; danger = refuse/red for destructive only.
- **Inputs:** Border 1px; focus ring 2px accent; error state = red border + short message below.
- **Cards:** Light border, subtle shadow (e.g. 0 1px 3px rgba(0,0,0,0.08)); rounded corners 6–8px optional.
- **Badges/pills:** For counts (e.g. “3 units”); small, rounded; secondary background + primary text.
- **Proof list:** One row per proof point: `page N · (x, y)` · source_id; monospace for numbers/ids.
- **Refuse block:** Distinct background (e.g. refuse/warning tint), border, “REFUSED” in bold; reason below.

---

## 2. Layout

### 2.1 Desktop (three-pane)

```
┌─────────────────┬──────────────────────────────┬─────────────────┐
│  Documents      │  PDF viewer                   │  Query          │
│  + Canonical    │  (+ overlay when proof)        │  + Result       │
│  (scroll)       │  (scroll by page)             │  (scroll)       │
│  ~280px         │  flex 1                       │  ~320px         │
└─────────────────┴──────────────────────────────┴─────────────────┘
```

- **Left:** Fixed or min-width ~280px. Document list on top; below it, canonical inspector (tabs: Units | Bijections | Grids) for selected doc.
- **Center:** PDF viewer, flex-grow. Toolbar optional (zoom, page nav). Overlay layer above PDF canvas for proof highlights.
- **Right:** Fixed or min-width ~320px. Document selector + question input + submit; below, result (answer + proof or refuse).

### 2.2 Ingest (upload)

- Can sit at top of left pane, or as a modal/drop zone that appears when “Upload PDF” is clicked.
- Drop zone: dashed border, “Drop PDF or click to upload”; on success → toast or inline message with doc_id + counts.
- Show doc_id with a copy button.

### 2.3 Document list (left)

- One card or row per document: **filename** (truncate if long), **doc_id** (monospace, copy button), **counts** (e.g. “2 units · 1 bijection · 0 grids”).
- Selected state: background or left border accent.
- Empty: “No documents yet. Upload a PDF to get started.” + CTA.

### 2.4 Canonical inspector (left, below list)

- Only when a document is selected.
- Tabs: **Units** | **Bijections** | **Grids**.
- **Units:** Table or list: id, label, value, unit, page, (x, y).
- **Bijections:** id, mapping (e.g. “5 → VCC”), page, (x, y).
- **Grids:** id, rows×cols, page, (x, y). Optional expand to show cell count.
- Use monospace for id, page, coordinates. Optional “Locate” link per row (scrolls PDF, shows marker).

### 2.5 PDF viewer (center)

- Full height of center pane. Toolbar: page N of M, prev/next, zoom if needed.
- Canvas: PDF.js (or equivalent) with coordinate system aligned to backend (normalized 0–1 or page pixels).
- **Overlay:** When result has proof, draw rectangles or markers at (page, bbox or point). Colors: unit = verified green, bijection = accent blue, grid = e.g. orange. Semi-transparent fill + stroke.
- Legend below or beside viewer: “Unit · Bijection · Grid” with swatches.
- Empty: “Select a document to view” (or “Upload and select a document”).

### 2.6 Query + result (right)

- **Document:** Dropdown or single-select list (pre-filled with selected doc from left).
- **Question:** Text input or textarea, placeholder e.g. “e.g. What is pin 5?”
- **Submit:** Primary button “Verify” or “Ask”.
- **Loading:** Disable submit, show “Verifying…” under button or in result area.
- **Result (answer):**
  - Heading “Answer” + the answer text (slightly emphasized).
  - Section “Proof” + list of proof points (page, x, y, source_id, source_type).
  - Button “Show on document” → scroll center pane to page and draw overlay.
- **Result (refuse):**
  - Block with refuse background/border; “REFUSED” label; reason text below.
  - No answer-style text.

### 2.7 Responsive / narrow

- Stack vertically or use tabs: **Documents** | **Viewer** | **Query**.
- Priority: Query + result visible first; PDF in second tab; document list + canonical in first tab or drawer.
- Or: Single column — Upload → Document list → Select → Query → Result; PDF viewer as full-screen or modal when “Show on document” is used.

---

## 3. Component inventory (checklist)

| Component | Notes |
|----------|--------|
| **Upload drop zone** | Dashed border, PDF only, copy doc_id on success |
| **Document list** | Rows with filename, doc_id (copy), counts, selected state |
| **Canonical tabs** | Units / Bijections / Grids with table or list rows |
| **PDF viewer** | Page nav, canvas, overlay layer for proof |
| **Document selector** | Dropdown or list for query |
| **Question input** | Single line or short textarea + submit |
| **Answer block** | Answer text + proof list + “Show on document” |
| **Refuse block** | REFUSED label + reason, distinct styling |
| **Proof list item** | page, x, y, source_id, source_type (monospace where needed) |
| **Copy button** | For doc_id and optionally proof coordinates |
| **Loading state** | Spinner or “Verifying…” for query |
| **Empty states** | No documents; no canonical; no document selected for viewer |

---

## 4. Accessibility (UI)

- **Focus:** Visible focus ring (2px accent) on all interactive elements.
- **Contrast:** Text/background and button/background meet WCAG AA (e.g. 4.5:1 for normal text).
- **Refuse:** Ensure “REFUSED” and reason are announced (e.g. live region) so answer vs refuse is clear to screen readers.
- **Proof list:** Use list markup; optional “Show on document” as button with clear label.
- **PDF overlay:** If overlay is decorative, keep it subtle; if it conveys “proof location,” ensure there’s a text equivalent (proof list).

---

## 5. Tech stack (suggested)

- **Framework:** React, Vue, or Svelte (or static HTML + minimal JS if preferred).
- **PDF:** PDF.js for render + overlay (same coordinate system as API).
- **API:** Fetch to existing FastAPI endpoints; `POST /ingest` (FormData with `file`), `POST /query` (JSON), `GET /documents`, `GET /documents/{id}/canonical`.
- **State:** Selected doc_id, last query result (answer + proof or refuse), optional “overlay active” flag for viewer.
- **Styling:** CSS variables for colors/spacing above; Tailwind, plain CSS, or design-system library aligned to this spec.

---

## 6. File / serving

- UI can live in a folder (e.g. `frontend/` or `web/`) and be served by the same host as the API (FastAPI static mount) or a separate dev server (CORS to API).
- For “Show on document,” the UI needs the PDF bytes for the selected doc: either a new endpoint (e.g. `GET /documents/{id}/file`) or the client retains the file from upload (v1).

---

*Use this spec with `docs/UX-DESIGN-BRIEF.md` for a complete UX + UI handoff. Implement layout and components first, then wire to API and overlay logic.*

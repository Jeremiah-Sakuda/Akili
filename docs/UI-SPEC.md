# Akili — UI Specification

**Purpose:** Visual and component-level spec for the Akili web UI. Use with `UX-DESIGN-BRIEF.md` for flows and content; this doc defines look, components, and layout.  
**Audience:** UI designers, front-end developers.  
**Last updated:** February 2026.

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
| **Verified / success** | `#0D7B4C` | `#2DA66A` | VERIFIED tier answer, proof |
| **Review / caution** | `#B45300` | `#E89540` | REVIEW tier answer, flagged for confirmation |
| **Refuse / warning** | `#C00` | `#E06060` | REFUSED tier, deterministic refusal |
| **Accent (primary action)** | `#0066CC` | `#4DA3FF` | Buttons, links, focus |
| **Accent (hover)** | `#0052A3` | `#6BB3FF` | Hover states |

### 1.2 Typography

| Element | Suggested | Size | Weight | Use |
|--------|-----------|------|--------|-----|
| **Page title** | Sans (e.g. system-ui or Inter) | 1.5rem | 600 | "Akili" / app title |
| **Section heading** | Same | 1rem | 600 | "Documents", "Query", "Proof" |
| **Body** | Same | 0.875rem | 400 | Descriptions, list content |
| **Data / coordinates** | Monospace (e.g. JetBrains Mono, ui-monospace) | 0.8125rem | 400 | doc_id, (x,y), source_id, confidence % |
| **Answer (result)** | Same as body or slightly larger | 1rem | 500 | The proven answer text |
| **Refuse label** | Same | 1rem | 600 | "REFUSED" |
| **Confidence %** | Monospace | 0.625rem | 400 | Overall confidence percentage next to tier badge |

### 1.3 Spacing and layout

- **Base unit:** 4px (or 0.25rem).
- **Panel padding:** 16px (or 1rem).
- **Gap between panes:** 1px divider or 8px gap.
- **Card/block padding:** 12px-16px.
- **Input height:** 40px; button height 40px (or match inputs).

### 1.4 Components (patterns)

- **Buttons:** Primary = accent fill; secondary = border only; danger = refuse/red for destructive only.
- **Inputs:** Border 1px; focus ring 2px accent; error state = red border + short message below.
- **Cards:** Light border, subtle shadow (e.g. 0 1px 3px rgba(0,0,0,0.08)); rounded corners 6-8px optional.
- **Badges/pills:** For counts (e.g. "3 units"); small, rounded; secondary background + primary text.
- **Proof list:** One row per proof point: `page N (x, y)` source_id; monospace for numbers/ids.
- **Refuse block:** Distinct background (e.g. refuse/warning tint), border, "REFUSED" in bold; reason below.
- **Confidence badges:** Color-coded pills for the confidence tier:
  - Green "VERIFIED" (overall >= 85%)
  - Yellow "REVIEW" (50-85%)
  - Red/amber "REFUSED" (< 50%)
  - Optional: overall percentage in monospace next to the badge (e.g. "78%").
- **Formatting label:** When `formatting_source` is `"gemini_rephrase"`, a subtle "AI-rephrased" badge (gray background, small text) appears next to the confidence badge. Raw verified answers show no extra label.

---

## 2. Layout

### 2.1 Desktop (three-pane)

```
+-------------------+--------------------------------+-------------------+
|  Documents        |  PDF viewer                    |  Query            |
|  + Canonical      |  (+ overlay when proof)        |  + Result         |
|  (scroll)         |  (scroll by page)              |  (scroll)         |
|  ~280px           |  flex 1                        |  ~320px           |
+-------------------+--------------------------------+-------------------+
```

- **Left:** Fixed or min-width ~280px. Document list on top; below it, canonical inspector (tabs: Units | Bijections | Grids) for selected doc.
- **Center:** PDF viewer, flex-grow. Toolbar optional (zoom, page nav). Overlay layer above PDF canvas for proof highlights.
- **Right:** Fixed or min-width ~320px. Chat-style query interface; below, result with confidence badge + proof or refuse.

### 2.2 Ingest (upload)

- Can sit at top of left pane, or as a modal/drop zone that appears when "Upload PDF" is clicked.
- Drop zone: dashed border, "Drop PDF or click to upload"; on success -> toast or inline message with doc_id + counts.
- Show doc_id with a copy button.

### 2.3 Document list (left)

- One card or row per document: **filename** (truncate if long), **doc_id** (monospace, copy button), **counts** (e.g. "2 units, 1 bijection, 0 grids").
- Selected state: background or left border accent.
- Empty: "No documents yet. Upload a PDF to get started." + CTA.

### 2.4 Canonical inspector (left, below list)

- Only when a document is selected.
- Tabs: **Units** | **Bijections** | **Grids**.
- **Units:** Table or list: id, label, value, unit, page, (x, y).
- **Bijections:** id, mapping (e.g. "5 -> VCC"), page, (x, y).
- **Grids:** id, rows x cols, page, (x, y). Optional expand to show cell count.
- Use monospace for id, page, coordinates.

### 2.5 PDF viewer (center)

- Full height of center pane. Toolbar: page N of M, prev/next, zoom if needed.
- Canvas: PDF.js with coordinate system aligned to backend.
- **Overlay:** When result has proof, draw rectangles or markers at (page, bbox or point). Colors: unit = verified green, bijection = accent blue, grid = orange. Semi-transparent fill + stroke.
- Empty: "Select a document to view" (or "Upload and select a document").

### 2.6 Query + result (right)

- **Question:** Text input or textarea, placeholder e.g. "e.g. What is pin 5?"
- **Submit:** Primary button "Ask" or Enter to submit.
- **Loading:** Disable submit, show "Verifying..." under button or in result area.
- **Result (verified / review):**
  - Confidence badge: green "VERIFIED" or yellow "REVIEW" with percentage.
  - Answer text.
  - If `formatting_source === "gemini_rephrase"`: "AI-rephrased" label next to badge.
  - Section "Proof" + list of proof points (page, x, y, source_id, source_type).
  - Button "Show on document" -> scroll center pane to page and draw overlay.
- **Result (refuse):**
  - Red/amber "REFUSED" badge.
  - Reason text below.
  - No answer-style text.

### 2.7 Responsive / narrow

- Stack vertically or use tabs: **Documents** | **Viewer** | **Query**.
- Priority: Query + result visible first; PDF in second tab; document list + canonical in first tab or drawer.

---

## 3. Component inventory (checklist)

| Component | Notes |
|----------|--------|
| **Upload drop zone** | Dashed border, PDF only, copy doc_id on success |
| **Document list** | Rows with filename, doc_id (copy), counts, selected state |
| **Canonical tabs** | Units / Bijections / Grids with table or list rows |
| **PDF viewer** | Page nav, canvas, overlay layer for proof |
| **Question input** | Single line or short textarea + submit |
| **Answer block** | Confidence badge + answer text + proof list + "Show on document" |
| **Refuse block** | REFUSED badge + reason, distinct styling |
| **Confidence badge** | Green/yellow/red pill with tier label and optional % |
| **Formatting label** | "AI-rephrased" gray badge when Gemini-formatted |
| **Proof list item** | page, x, y, source_id, source_type (monospace where needed) |
| **Copy button** | For doc_id and optionally proof coordinates |
| **Loading state** | Spinner or "Verifying..." for query |
| **Empty states** | No documents; no canonical; no document selected for viewer |

---

## 4. Accessibility (UI)

- **Focus:** Visible focus ring (2px accent) on all interactive elements.
- **Contrast:** Text/background and button/background meet WCAG AA (e.g. 4.5:1 for normal text).
- **Refuse:** Ensure "REFUSED" and reason are announced (e.g. live region) so answer vs refuse is clear to screen readers.
- **Confidence tier:** The tier label text ("VERIFIED", "REVIEW", "REFUSED") provides accessible information beyond color alone.
- **Proof list:** Use list markup; optional "Show on document" as button with clear label.
- **PDF overlay:** If overlay is decorative, keep it subtle; if it conveys "proof location," ensure there's a text equivalent (proof list).

---

## 5. Tech stack

- **Framework:** React + TypeScript + Vite.
- **PDF:** pdfjs-dist for render + overlay (same coordinate system as API).
- **API:** Fetch to FastAPI endpoints; `POST /ingest` (FormData with `file`), `POST /query` (JSON), `GET /documents`, `GET /documents/{id}/canonical`, `GET /documents/{id}/file`.
- **State:** Selected doc_id, last query result (answer + proof + confidence, or refuse), overlay active flag.
- **Styling:** Tailwind CSS; CSS variables for color tokens above.
- **Auth:** Optional Firebase Google sign-in (AuthContext).
- **Theme:** Dark mode support (ThemeContext).

---

## 6. File / serving

- UI lives in `frontend/` and is served by a Vite dev server (proxied to API) or built and served via Firebase Hosting / Docker.
- For "Show on document," the UI fetches PDF bytes via `GET /documents/{id}/file`.

---

*Use this spec with `docs/UX-DESIGN-BRIEF.md` for a complete UX + UI handoff. Implement layout and components first, then wire to API and overlay logic.*

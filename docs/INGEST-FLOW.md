# Ingest flow (engineer-level)

What happens when a PDF is uploaded, with code references.

---

## 1. API receives the file

**Where:** `src/akili/api/app.py` — `POST /ingest`

- Request must be multipart with a PDF file.
- We validate extension, non-empty body, and optional size limit.
- Bytes are written to a **temp file** so the rest of the pipeline can use a `Path`.

```python
# app.py (excerpt)
if not file.filename or not file.filename.lower().endswith(".pdf"):
    raise HTTPException(status_code=400, detail="File must be a PDF")
content = await file.read()
# ...
with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
    tmp.write(content)
    tmp_path = Path(tmp.name)
try:
    doc_id, canonical = ingest_document(tmp_path, store=store)
    # ... copy to docs_dir, then respond
finally:
    tmp_path.unlink(missing_ok=True)
```

---

## 2. Pipeline entrypoint

**Where:** `src/akili/ingest/pipeline.py` — `ingest_document()`

- Generates or uses provided `doc_id` (UUID if not provided).
- Loads PDF into page images, then for **each page**: call Gemini → canonicalize → accumulate. Failed pages are skipped (try/except per page).
- Optionally writes to the store and returns `(doc_id, list[Unit|Bijection|Grid])`.

```python
# pipeline.py (excerpt)
def ingest_document(pdf_path, doc_id=None, store=None):
    doc_id = doc_id or str(uuid.uuid4())
    pages = load_pdf_pages(pdf_path)   # list of (page_index, png_bytes)
    all_canonical = []

    for i, (page_index, image_bytes) in enumerate(pages):
        if i > 0 and _PAGE_DELAY > 0:
            time.sleep(_PAGE_DELAY)
        try:
            extraction = gemini_extract_page(page_index, image_bytes, doc_id)
            canonical = canonicalize_page(extraction, doc_id, page_index)
            all_canonical.extend(canonical)
        except Exception:
            continue

    if store is not None:
        units = [o for o in all_canonical if isinstance(o, Unit)]
        bijections = [o for o in all_canonical if isinstance(o, Bijection)]
        grids = [o for o in all_canonical if isinstance(o, Grid)]
        store.store_canonical(doc_id, pdf_path.name, len(pages), units, bijections, grids)

    return doc_id, all_canonical
```

---

## 3. PDF → page images

**Where:** `src/akili/ingest/pdf_loader.py` — `load_pdf_pages()`

- PyMuPDF (`fitz`) opens the PDF and iterates pages.
- Each page is rendered at 150 DPI, no alpha, then encoded as PNG bytes for Gemini.
- Per-page try/except: a bad page is skipped so the rest of the doc still ingests.

```python
# pdf_loader.py (excerpt)
def load_pdf_pages(pdf_path: Path) -> list[tuple[int, bytes]]:
    pages = []
    doc = fitz.open(pdf_path)
    try:
        for page_index in range(len(doc)):
            try:
                page = doc[page_index]
                pix = page.get_pixmap(dpi=150, alpha=False)
                png_bytes = pix.tobytes(output="png")
                pages.append((page_index, png_bytes))
            except Exception:
                continue
    finally:
        doc.close()
    return pages
```

---

## 4. Per-page Gemini extraction

**Where:** `src/akili/ingest/gemini_extract.py` — `extract_page()`

- One Gemini call per page: image (base64 PNG) + prompt asking for **units**, **bijections**, **grids** with `origin.x`, `origin.y` (and optional bbox).
- Response is free-form JSON; we **normalize** then validate with Pydantic.
- Normalization: fill missing `id` / `value` from `text`; drop units without valid `origin` or `value`; ensure `units`/`bijections`/`grids` are lists.
- On JSON parse failure or `ValidationError`, we return an empty `PageExtraction` for that page (no crash).
- 429 is retried with exponential backoff.

```python
# gemini_extract.py (excerpt)
def extract_page(page_index: int, image_png_bytes: bytes, doc_id: str) -> PageExtraction:
    # ...
    image_part = {
        "inline_data": {
            "mime_type": "image/png",
            "data": base64.standard_b64encode(image_png_bytes).decode("utf-8"),
        }
    }
    contents = [prompt, image_part]
    response = model.generate_content(contents, generation_config=...)  # or plain contents

    text = response.text or (candidates[0].content.parts[0].text if ...)
    data = json.loads(text)
    data = _normalize_extraction(data, page_index)   # fill id/value, drop bad units; ids namespaced p{page}_u{i}
    try:
        return PageExtraction.model_validate(data)
    except ValidationError:
        return PageExtraction(units=[], bijections=[], grids=[])
```

Normalization keeps only units that have a valid origin and a value:

```python
# _normalize_extraction(data, page_index) (excerpt)
# Ids are namespaced by page so they are unique across the document (avoids duplicate React keys).
page_prefix = f"p{page_index}_"
if u.get("value") is None and u.get("text") is not None:
    u["value"] = u["text"]
if u.get("id") is None or u.get("id") == "":
    u["id"] = f"{page_prefix}u{i}"   # e.g. p0_u0, p1_u0
if not _has_valid_origin(u):
    continue
if u.get("value") is None:
    continue
kept.append(u)
data["units"] = kept
# Bijections/grids: item["id"] = f"{page_prefix}b{i}" or f"{page_prefix}g{i}"
```

---

## 5. Extraction → canonical models

**Where:** `src/akili/ingest/canonicalize.py` — `canonicalize_page()`

- `PageExtraction` (extract schema) is mapped to our domain models: `Unit`, `Bijection`, `Grid`.
- Each item is built with `doc_id`, `page`, and coordinates; invalid items are skipped (per-item try/except). Only coordinate-grounded facts enter the store.

```python
# canonicalize.py (excerpt)
def canonicalize_units(extracts: list[UnitExtract], doc_id: str, page: int) -> list[Unit]:
    out = []
    for e in extracts:
        try:
            out.append(
                Unit(
                    id=e.id,
                    label=e.label,
                    value=e.value,
                    unit_of_measure=e.unit_of_measure,
                    origin=_point(e.origin),
                    doc_id=doc_id,
                    page=page,
                    bbox=_bbox(e.bbox),
                )
            )
        except Exception:
            continue
    return out
```

Same idea for `canonicalize_bijections` and `canonicalize_grids`; `canonicalize_page()` concatenates the three lists.

---

## 6. Persistence

**Where:** `src/akili/store/repository.py` — `Store.store_canonical()`

- Inserts/updates `documents` row (doc_id, filename, page_count).
- Inserts/updates rows in `units`, `bijections`, `grids` with (doc_id, page, id, …) and JSON for origin/bbox/cells. Unique key is (doc_id, page, unit_id) (or bijection_id / grid_id).

```python
# repository.py (excerpt)
def store_canonical(self, doc_id, filename, page_count, units, bijections, grids):
    self.add_document(doc_id, filename, page_count)
    with self._conn() as c:
        for u in units:
            c.execute(
                """INSERT OR REPLACE INTO units (doc_id, page, unit_id, label, value,
                   unit_of_measure, origin_json, bbox_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (u.doc_id, u.page, u.id, u.label, str(u.value), u.unit_of_measure,
                 _point_to_json(u.origin), _bbox_to_json(u.bbox)),
            )
        # same pattern for bijections, grids
```

---

## 7. API response

**Where:** `src/akili/api/app.py` — after `ingest_document()`

- Temp file is deleted in `finally`.
- PDF is copied to `docs/{doc_id}.pdf` if you use that feature.
- Response body: `doc_id`, `filename`, `page_count`, `units_count`, `bijections_count`, `grids_count`.

---

## End-to-end call chain

```
POST /ingest (app.py)
  → ingest_document(tmp_path, store=store)   [pipeline.py]
       → load_pdf_pages(pdf_path)            [pdf_loader.py]  → list[(page_index, png_bytes)]
       → for each page:
            → gemini_extract_page(...)       [gemini_extract.py]  → PageExtraction
            → canonicalize_page(...)         [canonicalize.py]     → list[Unit|Bijection|Grid]
       → store.store_canonical(...)          [repository.py]
  → JSONResponse(doc_id, counts)
```

---

## Failure behavior

| Stage | On failure |
|-------|------------|
| Single page render (pdf_loader) | Skip that page, continue. |
| Single page extract/canonicalize (pipeline) | Skip that page, continue. |
| JSON parse or ValidationError (gemini_extract) | Return empty PageExtraction for that page. |
| 429 from Gemini | Retry with backoff; after max retries, pipeline raises → API returns 429. |
| Any other exception in ingest_document | Propagates → API returns 500 (or 429 if rate-limit message). |

So one bad page or one bad Gemini response doesn’t kill the whole document; only that page contributes no canonical objects.

"""
Call Gemini with a page image and get structured extraction (units, bijections, grids).

Uses response_mime_type=application/json when supported; otherwise prompt-based JSON.
Retries on 429 (Resource exhausted) with exponential backoff.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time

import google.generativeai as genai
from pydantic import ValidationError

from akili import config
from akili.ingest.errors import is_rate_limit_error as _is_rate_limit_error
from akili.ingest.extract_schema import PageExtraction

logger = logging.getLogger(__name__)


EXTRACT_PROMPT = """\
You are extracting structured, coordinate-grounded facts from a single page of \
technical documentation (datasheet, schematic, pinout table, etc.).

## Rules

- Extract ONLY facts you can tie to a specific (x, y) location on the page. \
Use normalized coordinates 0.0-1.0 (top-left = 0,0; bottom-right = 1,1).
- For each fact, provide origin with x and y (numbers). \
If you can infer a bounding box, provide bbox with x1, y1, x2, y2.
- Use short, unique ids (e.g. "u1", "b1", "g1"). \
Leave arrays empty if nothing of that type is on the page.
- Do not guess. If a coordinate or value is ambiguous, omit that fact.

## Coordinate Calibration

- origin should point to the CENTER of the text or value being extracted.
- bbox should cover the ENTIRE cell, row, or region containing the fact, NOT just the header.
- Correct: bbox covers "4.2V" cell from its top-left to bottom-right corners.
- Incorrect: bbox covers only the column header "Max Voltage" but not the value row.
- For tables: the grid's origin should be the top-left corner of the table; \
the grid's bbox should cover the entire table from top-left to bottom-right.
- When estimating coordinates, use surrounding text and layout as reference points. \
A value near the top of the page has y close to 0.0; near the bottom, close to 1.0.

## Unit Extraction Rules

- For every unit, ALWAYS include a `context` field describing what the value represents \
in the document. This is critical for question matching.
  - Good context examples: "nominal supply voltage", "absolute maximum junction temperature", \
"typical propagation delay", "ESD Human Body Model rating", "package thermal resistance theta-JA"
  - Bad context: "" (empty), "value", "specification" (too vague)
- Split compound values like "4.2V" or "2500mAh" into value (number) and \
unit_of_measure (e.g. V, mA, mAh).
- For min/typ/max tables: extract EACH value as a separate unit with context indicating \
whether it is minimum, typical, or maximum (e.g. "minimum supply voltage", "maximum supply voltage").
- Include the section heading or table title in the context when available \
(e.g. "Absolute Maximum Ratings - storage temperature", "Electrical Characteristics - input leakage current").

## JSON Format

- units: array of objects, each with: id (string), value (string or number), \
origin (object with x, y), label (string, short name like "VCC" or "tPD"), \
unit_of_measure (string like "V", "mA", "ns", "MHz", "mm"), \
context (string describing what this value is), bbox (object with x1, y1, x2, y2).
- bijections: array of 1:1 mappings. Each object MUST have: id (string), \
left_set (array of strings), right_set (array of strings), \
mapping (object: left label -> right label), origin (object with x, y), optional bbox. \
Example: {"id":"b1","left_set":["1","2","3"],"right_set":["VCC","GND","CLK"],\
"mapping":{"1":"VCC","2":"GND","3":"CLK"},"origin":{"x":0.2,"y":0.3}}.
- grids: array of tables. Each object MUST have: id (string), rows (integer), \
cols (integer), cells (array of objects with row (int), col (int), value (string or number), \
optional origin), origin (object with x, y for the grid top-left), optional bbox. \
Do NOT use "rows" as a list of row objects; use rows and cols as numbers and put all cells \
in the cells array with row/col indices. Row 0 should be the header row.

## Few-Shot Examples

### Example 1: Pinout Table Page
Input: A page showing a pin assignment table with columns "Pin Number", "Pin Name", "Function".
Expected output:
```json
{
  "units": [],
  "bijections": [
    {
      "id": "b1",
      "left_set": ["1", "2", "3", "4"],
      "right_set": ["VCC", "GND", "DATA", "CLK"],
      "mapping": {"1": "VCC", "2": "GND", "3": "DATA", "4": "CLK"},
      "origin": {"x": 0.3, "y": 0.25},
      "bbox": {"x1": 0.1, "y1": 0.15, "x2": 0.9, "y2": 0.55}
    }
  ],
  "grids": [
    {
      "id": "g1", "rows": 5, "cols": 3,
      "cells": [
        {"row": 0, "col": 0, "value": "Pin Number"},
        {"row": 0, "col": 1, "value": "Pin Name"},
        {"row": 0, "col": 2, "value": "Function"},
        {"row": 1, "col": 0, "value": "1"},
        {"row": 1, "col": 1, "value": "VCC"},
        {"row": 1, "col": 2, "value": "Power Supply"},
        {"row": 2, "col": 0, "value": "2"},
        {"row": 2, "col": 1, "value": "GND"},
        {"row": 2, "col": 2, "value": "Ground"},
        {"row": 3, "col": 0, "value": "3"},
        {"row": 3, "col": 1, "value": "DATA"},
        {"row": 3, "col": 2, "value": "Serial Data I/O"},
        {"row": 4, "col": 0, "value": "4"},
        {"row": 4, "col": 1, "value": "CLK"},
        {"row": 4, "col": 2, "value": "Clock Input"}
      ],
      "origin": {"x": 0.1, "y": 0.15},
      "bbox": {"x1": 0.1, "y1": 0.15, "x2": 0.9, "y2": 0.55}
    }
  ]
}
```

### Example 2: Electrical Characteristics Table
Input: A page with a table titled "Electrical Characteristics (TA = 25C)" with columns \
"Parameter", "Symbol", "Min", "Typ", "Max", "Unit".
Expected output:
```json
{
  "units": [
    {"id": "u1", "label": "VCC", "value": 2.7, "unit_of_measure": "V", "context": "Electrical Characteristics - minimum supply voltage", "origin": {"x": 0.35, "y": 0.32}},
    {"id": "u2", "label": "VCC", "value": 3.3, "unit_of_measure": "V", "context": "Electrical Characteristics - typical supply voltage", "origin": {"x": 0.5, "y": 0.32}},
    {"id": "u3", "label": "VCC", "value": 3.6, "unit_of_measure": "V", "context": "Electrical Characteristics - maximum supply voltage", "origin": {"x": 0.65, "y": 0.32}},
    {"id": "u4", "label": "ICC", "value": 5, "unit_of_measure": "mA", "context": "Electrical Characteristics - typical supply current", "origin": {"x": 0.5, "y": 0.38}},
    {"id": "u5", "label": "ICC", "value": 10, "unit_of_measure": "mA", "context": "Electrical Characteristics - maximum supply current", "origin": {"x": 0.65, "y": 0.38}}
  ],
  "bijections": [],
  "grids": [
    {
      "id": "g1", "rows": 3, "cols": 6,
      "cells": [
        {"row": 0, "col": 0, "value": "Parameter"}, {"row": 0, "col": 1, "value": "Symbol"},
        {"row": 0, "col": 2, "value": "Min"}, {"row": 0, "col": 3, "value": "Typ"},
        {"row": 0, "col": 4, "value": "Max"}, {"row": 0, "col": 5, "value": "Unit"},
        {"row": 1, "col": 0, "value": "Supply Voltage"}, {"row": 1, "col": 1, "value": "VCC"},
        {"row": 1, "col": 2, "value": "2.7"}, {"row": 1, "col": 3, "value": "3.3"},
        {"row": 1, "col": 4, "value": "3.6"}, {"row": 1, "col": 5, "value": "V"},
        {"row": 2, "col": 0, "value": "Supply Current"}, {"row": 2, "col": 1, "value": "ICC"},
        {"row": 2, "col": 2, "value": "-"}, {"row": 2, "col": 3, "value": "5"},
        {"row": 2, "col": 4, "value": "10"}, {"row": 2, "col": 5, "value": "mA"}
      ],
      "origin": {"x": 0.05, "y": 0.2},
      "bbox": {"x1": 0.05, "y1": 0.2, "x2": 0.95, "y2": 0.5}
    }
  ]
}
```

### Example 3: Absolute Maximum Ratings Table
Input: A page showing "Absolute Maximum Ratings" with parameters, ratings, and units.
Expected output:
```json
{
  "units": [
    {"id": "u1", "label": "VCC", "value": 7.0, "unit_of_measure": "V", "context": "Absolute Maximum Ratings - supply voltage", "origin": {"x": 0.5, "y": 0.28}},
    {"id": "u2", "label": "TSTG", "value": -65, "unit_of_measure": "C", "context": "Absolute Maximum Ratings - storage temperature minimum", "origin": {"x": 0.4, "y": 0.34}},
    {"id": "u3", "label": "TSTG", "value": 150, "unit_of_measure": "C", "context": "Absolute Maximum Ratings - storage temperature maximum", "origin": {"x": 0.6, "y": 0.34}},
    {"id": "u4", "label": "IO", "value": 25, "unit_of_measure": "mA", "context": "Absolute Maximum Ratings - output current per pin", "origin": {"x": 0.5, "y": 0.4}},
    {"id": "u5", "label": "ESD HBM", "value": 2000, "unit_of_measure": "V", "context": "Absolute Maximum Ratings - ESD Human Body Model", "origin": {"x": 0.5, "y": 0.46}}
  ],
  "bijections": [],
  "grids": []
}
```

Respond with a single JSON object with keys: units, bijections, grids. No other text."""


def _simplified_extraction_schema() -> dict:
    """Build a flat JSON schema for PageExtraction without $defs.

    Pydantic's model_json_schema() uses $defs for shared sub-models (PointSchema,
    BBoxSchema, etc.) which Gemini's structured output mode doesn't support.
    This builds an equivalent flat schema that Gemini can use directly.
    """
    point = {
        "type": "object",
        "properties": {
            "x": {"type": "number"},
            "y": {"type": "number"},
        },
        "required": ["x", "y"],
    }
    bbox = {
        "type": "object",
        "properties": {
            "x1": {"type": "number"},
            "y1": {"type": "number"},
            "x2": {"type": "number"},
            "y2": {"type": "number"},
        },
        "required": ["x1", "y1", "x2", "y2"],
    }
    unit_item = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "label": {"type": "string"},
            "value": {},
            "unit_of_measure": {"type": "string"},
            "context": {"type": "string"},
            "origin": point,
            "bbox": bbox,
        },
        "required": ["id", "value", "origin"],
    }
    bijection_item = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "left_set": {"type": "array", "items": {"type": "string"}},
            "right_set": {"type": "array", "items": {"type": "string"}},
            "mapping": {"type": "object"},
            "origin": point,
            "bbox": bbox,
        },
        "required": ["id", "left_set", "right_set", "mapping", "origin"],
    }
    grid_cell = {
        "type": "object",
        "properties": {
            "row": {"type": "integer"},
            "col": {"type": "integer"},
            "value": {},
            "origin": point,
        },
        "required": ["row", "col", "value"],
    }
    grid_item = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "rows": {"type": "integer"},
            "cols": {"type": "integer"},
            "cells": {"type": "array", "items": grid_cell},
            "origin": point,
            "bbox": bbox,
        },
        "required": ["id", "rows", "cols", "cells", "origin"],
    }
    return {
        "type": "object",
        "properties": {
            "units": {"type": "array", "items": unit_item},
            "bijections": {"type": "array", "items": bijection_item},
            "grids": {"type": "array", "items": grid_item},
        },
        "required": ["units", "bijections", "grids"],
    }


def _normalize_origin(origin: object) -> dict | None:
    """Return {x, y} dict with numeric x,y; accept dict or [x,y] list."""
    if isinstance(origin, dict):
        x, y = origin.get("x"), origin.get("y")
        if (
            x is not None
            and y is not None
            and isinstance(x, (int, float))
            and isinstance(y, (int, float))
        ):
            return {"x": float(x), "y": float(y)}
        return None
    if isinstance(origin, (list, tuple)) and len(origin) >= 2:
        try:
            return {"x": float(origin[0]), "y": float(origin[1])}
        except (TypeError, ValueError):
            return None
    return None


def _normalize_bbox(bbox: object) -> dict | None:
    """Return {x1, y1, x2, y2} dict; accept dict or [x1,y1,x2,y2] list."""
    if isinstance(bbox, dict):
        x1, y1 = bbox.get("x1"), bbox.get("y1")
        x2, y2 = bbox.get("x2"), bbox.get("y2")
        if (
            x1 is not None
            and y1 is not None
            and x2 is not None
            and y2 is not None
            and all(isinstance(v, (int, float)) for v in (x1, y1, x2, y2))
        ):
            return {"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)}
        return None
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        try:
            return {
                "x1": float(bbox[0]),
                "y1": float(bbox[1]),
                "x2": float(bbox[2]),
                "y2": float(bbox[3]),
            }
        except (TypeError, ValueError):
            return None
    return None


def _normalize_bijection_item(item: dict, page_prefix: str, index: int) -> dict | None:
    """
    Convert Gemini bijection shape to schema: left_set, right_set, mapping, origin.
    Accepts: pair (list of 2), or key/value, or already left_set/right_set/mapping.
    """
    if not isinstance(item, dict):
        return None
    bid = item.get("id")
    if not isinstance(bid, str) or not bid.strip():
        bid = f"{page_prefix}b{index}"
    origin = _normalize_origin(item.get("origin"))
    if origin is None:
        return None
    bbox = _normalize_bbox(item.get("bbox"))

    left_set = item.get("left_set")
    right_set = item.get("right_set")
    mapping = item.get("mapping")

    if isinstance(item.get("pair"), (list, tuple)) and len(item["pair"]) >= 2:
        left_val = str(item["pair"][0])
        right_val = str(item["pair"][1])
        left_set = [left_val]
        right_set = [right_val]
        mapping = {left_val: right_val}
    elif "key" in item and "value" in item:
        k, v = str(item["key"]), str(item["value"])
        left_set = [k]
        right_set = [v]
        mapping = {k: v}
    elif not (
        isinstance(left_set, list)
        and isinstance(right_set, list)
        and isinstance(mapping, dict)
    ):
        return None

    return {
        "id": bid,
        "left_set": left_set,
        "right_set": right_set,
        "mapping": mapping,
        "origin": origin,
        "bbox": bbox,
    }


def _normalize_grid_item(item: object, page_prefix: str, index: int) -> dict | None:
    """
    Convert Gemini grid shape to schema: rows (int), cols (int),
    cells (list of {row, col, value, origin}).
    Accepts: rows as list of row objects with 'cells', or already rows/cols/cells.
    """
    if not isinstance(item, dict):
        return None
    gid = item.get("id")
    if not isinstance(gid, str) or not gid.strip():
        gid = f"{page_prefix}g{index}"
    origin = _normalize_origin(item.get("origin"))
    bbox = _normalize_bbox(item.get("bbox"))

    rows_raw = item.get("rows")
    cols_raw = item.get("cols")
    cells_raw = item.get("cells")

    # Gemini often returns rows as list of row objects: [{"id":"r1","cells":[...]}, ...]
    if isinstance(rows_raw, list) and rows_raw and not isinstance(rows_raw[0], (int, float)):
        cells_list: list[dict] = []
        nrows = len(rows_raw)
        ncols = 0
        for ri, row in enumerate(rows_raw):
            if not isinstance(row, dict):
                continue
            row_cells = row.get("cells") or row.get("cell") or []
            if not isinstance(row_cells, list):
                continue
            ncols = max(ncols, len(row_cells))
            for ci, cell in enumerate(row_cells):
                if isinstance(cell, dict):
                    val = cell.get("value") or cell.get("text") or cell.get("content")
                    if val is None:
                        val = ""
                    cell_origin = _normalize_origin(cell.get("origin"))
                    cells_list.append({
                        "row": ri,
                        "col": ci,
                        "value": val,
                        "origin": cell_origin,
                    })
                else:
                    cells_list.append({"row": ri, "col": ci, "value": str(cell), "origin": None})
        if not cells_list and nrows > 0:
            # No cell content but we have row count; create placeholder cells if needed
            ncols = max(ncols, 1)
        if origin is None:
            origin = {"x": 0.0, "y": 0.0}
        return {
            "id": gid,
            "rows": nrows,
            "cols": max(ncols, 1),
            "cells": cells_list,
            "origin": origin,
            "bbox": bbox,
        }
    # Already rows (int), cols (int), cells (list)
    if isinstance(rows_raw, (int, float)) and isinstance(cols_raw, (int, float)):
        if origin is None:
            origin = {"x": 0.0, "y": 0.0}
        if not isinstance(cells_raw, list):
            cells_raw = []
        normalized_cells = []
        for c in cells_raw:
            if not isinstance(c, dict):
                continue
            ro, co = c.get("row"), c.get("col")
            if ro is None or co is None:
                continue
            try:
                ro, co = int(ro), int(co)
            except (TypeError, ValueError):
                continue
            if ro < 0 or co < 0:
                continue
            val = c.get("value") or c.get("text") or c.get("content")
            if val is None:
                val = ""
            cell_origin = _normalize_origin(c.get("origin"))
            normalized_cells.append({
                "row": ro,
                "col": co,
                "value": val,
                "origin": cell_origin,
            })
        return {
            "id": gid,
            "rows": int(rows_raw),
            "cols": int(cols_raw),
            "cells": normalized_cells,
            "origin": origin,
            "bbox": bbox,
        }
    return None


def _normalize_extraction(data: dict, page_index: int = 0) -> dict:
    """
    Normalize Gemini response to match PageExtraction schema.
    Units: ensure id and value (from value/text/label/content); normalize origin; drop invalid.
    Ids are namespaced by page_index (e.g. p0_u0, p1_u0) so they are unique across pages.
    Bijections/grids: ensure list and fill missing id with same namespacing.
    """
    if not isinstance(data, dict):
        return {"units": [], "bijections": [], "grids": []}

    page_prefix = f"p{page_index}_"
    units_raw = data.get("units")
    if not isinstance(units_raw, list):
        data["units"] = []
    else:
        kept = []
        for i, u in enumerate(units_raw):
            if not isinstance(u, dict):
                continue
            origin = _normalize_origin(u.get("origin"))
            if origin is None:
                continue
            # Value: prefer value, then text/label/content; fallback "" so schema validates
            val = u.get("value")
            if val is None:
                val = u.get("text") or u.get("label") or u.get("content")
            if val is None:
                val = ""
            # Id: must be string; use existing if non-empty else p{page}_u{i} for global uniqueness
            uid = u.get("id")
            if not isinstance(uid, str) or not uid.strip():
                uid = f"{page_prefix}u{i}"
            uom = u.get("unit_of_measure")
            ctx = u.get("context")
            bbox = _normalize_bbox(u.get("bbox"))
            kept.append(
                {
                    "id": uid,
                    "label": u.get("label") if isinstance(u.get("label"), str) else None,
                    "value": val,
                    "unit_of_measure": uom if isinstance(uom, str) else None,
                    "context": ctx if isinstance(ctx, str) else None,
                    "origin": origin,
                    "bbox": bbox,
                }
            )
        data["units"] = kept

    # Bijections: normalize Gemini shapes (pair, key/value) to left_set, right_set, mapping
    bijections_raw = data.get("bijections")
    if not isinstance(bijections_raw, list):
        data["bijections"] = []
    else:
        data["bijections"] = [
            b
            for i, item in enumerate(bijections_raw)
            if (b := _normalize_bijection_item(item, page_prefix, i)) is not None
        ]

    # Grids: normalize Gemini shapes (rows as list of row objects) to rows, cols, cells
    grids_raw = data.get("grids")
    if not isinstance(grids_raw, list):
        data["grids"] = []
    else:
        data["grids"] = [
            g
            for i, item in enumerate(grids_raw)
            if (g := _normalize_grid_item(item, page_prefix, i)) is not None
        ]
    return data


def _ensure_configured() -> None:
    if not os.environ.get("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY environment variable is required for Gemini extraction")


def extract_page(
    page_index: int,
    image_png_bytes: bytes,
    doc_id: str,
    page_type_hint: str = "",
) -> PageExtraction:
    """
    Send one page image to Gemini and return structured extraction.

    Raises if API key is missing. Returns empty extraction on parse/API errors.
    page_type_hint is an optional string prepended to the prompt (from page_classifier).
    """
    _ensure_configured()
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

    model = genai.GenerativeModel(config.GEMINI_MODEL)
    image_part = {
        "inline_data": {
            "mime_type": "image/png",
            "data": base64.standard_b64encode(image_png_bytes).decode("utf-8"),
        }
    }
    hint_block = f"\n\nPAGE TYPE HINT: {page_type_hint}\n" if page_type_hint else ""
    prompt = (
        f"{EXTRACT_PROMPT}{hint_block}\n\n"
        f"This image is page {page_index}. "
        "Return JSON with keys: units, bijections, grids."
    )
    contents = [prompt, image_part]

    for attempt in range(config.GEMINI_MAX_RETRIES):
        try:
            try:
                generation_config = genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=_simplified_extraction_schema(),
                )
                response = model.generate_content(contents, generation_config=generation_config)
            except (TypeError, AttributeError, ValueError):
                response = model.generate_content(contents)
            break
        except Exception as e:
            if _is_rate_limit_error(e) and attempt < config.GEMINI_MAX_RETRIES - 1:
                wait = config.GEMINI_BACKOFF_BASE * (2**attempt)
                time.sleep(wait)
                continue
            raise

    text = ""
    if hasattr(response, "text") and response.text:
        text = response.text
    else:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            c = candidates[0]
            content = getattr(c, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if content and parts:
                part = parts[0]
                if hasattr(part, "text") and part.text:
                    text = part.text
    text = (text or "").strip()
    if not text:
        return PageExtraction(units=[], bijections=[], grids=[])

    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return PageExtraction(units=[], bijections=[], grids=[])

    data = _normalize_extraction(data, page_index)
    try:
        return PageExtraction.model_validate(data)
    except ValidationError as e:
        logger.exception(
            "PageExtraction validation failed (returning empty extraction). Full error: %s",
            e,
        )
        for err in e.errors():
            logger.error("Validation error detail: %s", err)
        return PageExtraction(units=[], bijections=[], grids=[])

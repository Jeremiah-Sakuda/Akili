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

from akili.ingest.extract_schema import PageExtraction

logger = logging.getLogger(__name__)

# Retry 429 / resource exhausted: max attempts, backoff base seconds
_GEMINI_MAX_RETRIES = int(os.environ.get("AKILI_GEMINI_MAX_RETRIES", "4"))
_GEMINI_BACKOFF_BASE = float(os.environ.get("AKILI_GEMINI_BACKOFF_BASE", "4.0"))
# Model: e.g. gemini-3.0-flash (default), gemini-3-flash-preview, gemini-3-pro-preview
_GEMINI_MODEL = os.environ.get("AKILI_GEMINI_MODEL", "gemini-3.0-flash")


def _is_rate_limit_error(e: BaseException) -> bool:
    msg = (getattr(e, "message", None) or str(e)).lower()
    return "429" in msg or "resource exhausted" in msg or "resourceexhausted" in msg


EXTRACT_PROMPT = (
    "You are extracting structured, coordinate-grounded facts from a single page of "
    "technical documentation (datasheet, schematic, pinout table, etc.).\n\n"
    "Rules:\n"
    "- Extract ONLY facts you can tie to a specific (x, y) location on the page. "
    "Use normalized coordinates 0.0–1.0 (e.g. top-left = 0,0; bottom-right = 1,1) or estimate from layout.\n"  # noqa: E501
    "- For each fact, provide origin.x and origin.y. If you can infer a bounding box, provide bbox (x1,y1,x2,y2).\n"  # noqa: E501
    "- Output only: units (discrete values like pin labels, voltages with position), "
    "bijections (1:1 mappings e.g. pin name <-> pin number), grids (tables with row/col and optional cell origins).\n"  # noqa: E501
    '- Use short, unique ids (e.g. "u1", "b1", "g1"). Leave arrays empty if nothing of that type is on the page.\n'  # noqa: E501
    "- Do not guess. If a coordinate or value is ambiguous, omit that fact.\n\n"
    "Respond with a single JSON object with keys: units (array), bijections (array), grids (array). No other text."  # noqa: E501
)


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
            bbox = _normalize_bbox(u.get("bbox"))
            kept.append(
                {
                    "id": uid,
                    "label": u.get("label") if isinstance(u.get("label"), str) else None,
                    "value": val,
                    "unit_of_measure": uom if isinstance(uom, str) else None,
                    "origin": origin,
                    "bbox": bbox,
                }
            )
        data["units"] = kept

    for key, prefix in (("bijections", "b"), ("grids", "g")):
        items = data.get(key)
        if not isinstance(items, list):
            data[key] = []
        else:
            for i, item in enumerate(items):
                if isinstance(item, dict):
                    if item.get("id") is None or item.get("id") == "":
                        item["id"] = f"{page_prefix}{prefix}{i}"
                    if not isinstance(item.get("bbox"), dict) and item.get("bbox") is not None:
                        item["bbox"] = _normalize_bbox(item["bbox"])
    return data


def _ensure_configured() -> None:
    if not os.environ.get("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY environment variable is required for Gemini extraction")


def extract_page(page_index: int, image_png_bytes: bytes, doc_id: str) -> PageExtraction:
    """
    Send one page image to Gemini and return structured extraction.

    Raises if API key is missing. Returns empty extraction on parse/API errors.
    """
    _ensure_configured()
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

    model = genai.GenerativeModel(_GEMINI_MODEL)
    image_part = {
        "inline_data": {
            "mime_type": "image/png",
            "data": base64.standard_b64encode(image_png_bytes).decode("utf-8"),
        }
    }
    prompt = (
        f"{EXTRACT_PROMPT}\n\n"
        f"This image is page {page_index} of document {doc_id}. "
        "Return JSON with keys: units, bijections, grids."
    )
    contents = [prompt, image_part]

    for attempt in range(_GEMINI_MAX_RETRIES):
        try:
            try:
                generation_config = genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=PageExtraction.model_json_schema(),
                )
                response = model.generate_content(contents, generation_config=generation_config)
            except (TypeError, AttributeError, ValueError):
                # Gemini API does not accept JSON Schema with $defs (from Pydantic);
                # use prompt-only and parse JSON
                response = model.generate_content(contents)
            break
        except Exception as e:
            if _is_rate_limit_error(e) and attempt < _GEMINI_MAX_RETRIES - 1:
                wait = _GEMINI_BACKOFF_BASE * (2**attempt)
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
        if hasattr(e, "errors") and e.errors:
            for err in e.errors:
                logger.error("Validation error detail: %s", err)
        return PageExtraction(units=[], bijections=[], grids=[])

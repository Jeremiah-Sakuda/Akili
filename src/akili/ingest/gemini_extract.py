"""
Call Gemini with a page image and get structured extraction (units, bijections, grids).

Uses response_mime_type=application/json when supported; otherwise prompt-based JSON.
"""

from __future__ import annotations

import base64
import json
import os

import google.generativeai as genai

from akili.ingest.extract_schema import PageExtraction

EXTRACT_PROMPT = """You are extracting structured, coordinate-grounded facts from a single page of technical documentation (datasheet, schematic, pinout table, etc.).

Rules:
- Extract ONLY facts you can tie to a specific (x, y) location on the page. Use normalized coordinates 0.0–1.0 (e.g. top-left = 0,0; bottom-right = 1,1) or estimate from layout.
- For each fact, provide origin.x and origin.y. If you can infer a bounding box, provide bbox (x1,y1,x2,y2).
- Output only: units (discrete values like pin labels, voltages with position), bijections (1:1 mappings e.g. pin name <-> pin number), grids (tables with row/col and optional cell origins).
- Use short, unique ids (e.g. "u1", "b1", "g1"). Leave arrays empty if nothing of that type is on the page.
- Do not guess. If a coordinate or value is ambiguous, omit that fact.

Respond with a single JSON object with keys: units (array), bijections (array), grids (array). No other text.
"""


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

    model = genai.GenerativeModel("gemini-2.0-flash")
    image_part = {
        "inline_data": {
            "mime_type": "image/png",
            "data": base64.standard_b64encode(image_png_bytes).decode("utf-8"),
        }
    }
    prompt = f"{EXTRACT_PROMPT}\n\nThis image is page {page_index} of document {doc_id}. Return JSON with keys: units, bijections, grids."
    contents = [prompt, image_part]

    try:
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json",
            response_schema=PageExtraction.model_json_schema(),
        )
        response = model.generate_content(contents, generation_config=generation_config)
    except (TypeError, AttributeError):
        response = model.generate_content(contents)

    text = getattr(response, "text", None) or (response.candidates[0].content.parts[0].text if response.candidates else "")
    if not text or not text.strip():
        return PageExtraction(units=[], bijections=[], grids=[])

    text = text.strip()
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

    return PageExtraction.model_validate(data)

"""
Classify a datasheet page type before extraction to enable type-specific prompting.

Uses a lightweight Gemini call to determine whether a page contains a pinout table,
electrical specs, absolute max ratings, block diagram, or general text.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Literal

import google.generativeai as genai

from akili import config
from akili.ingest.errors import is_rate_limit_error as _is_rate_limit_error

logger = logging.getLogger(__name__)

PageType = Literal[
    "pinout_table",
    "electrical_specs",
    "absolute_max_ratings",
    "timing_characteristics",
    "package_info",
    "block_diagram",
    "text_description",
    "other",
]

VALID_PAGE_TYPES: set[str] = {
    "pinout_table",
    "electrical_specs",
    "absolute_max_ratings",
    "timing_characteristics",
    "package_info",
    "block_diagram",
    "text_description",
    "other",
}

_CLASSIFY_PROMPT = """\
Classify this datasheet page into exactly ONE of these categories:
- pinout_table: Pin assignment table, pin diagram, or pin description table
- electrical_specs: Electrical characteristics table (voltage, current, power specs)
- absolute_max_ratings: Absolute maximum ratings table
- timing_characteristics: Timing diagrams or timing parameter tables
- package_info: Package dimensions, mechanical drawings, or package outline
- block_diagram: Functional block diagram or internal architecture
- text_description: General text (features, description, applications, ordering info)
- other: Anything not matching the above

Respond with ONLY the category name, nothing else."""



def classify_page(image_png_bytes: bytes) -> PageType:
    """Classify a page image into a PageType category.

    Returns "other" on any error or when classification is disabled.
    When AKILI_PAGE_CLASSIFY_ENABLED=0 (default), skips the API call.
    """
    if not config.PAGE_CLASSIFY_ENABLED:
        return "other"

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return "other"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(config.GEMINI_MODEL)
    image_part = {
        "inline_data": {
            "mime_type": "image/png",
            "data": base64.standard_b64encode(image_png_bytes).decode("utf-8"),
        }
    }

    for attempt in range(config.GEMINI_MAX_RETRIES):
        try:
            response = model.generate_content([_CLASSIFY_PROMPT, image_part])
            break
        except Exception as e:
            if _is_rate_limit_error(e) and attempt < config.GEMINI_MAX_RETRIES - 1:
                wait = config.GEMINI_BACKOFF_BASE * (2**attempt)
                time.sleep(wait)
                continue
            logger.warning("Page classification failed: %s", e)
            return "other"

    text = ""
    if hasattr(response, "text") and response.text:
        text = response.text.strip().lower()
    if text in VALID_PAGE_TYPES:
        return text  # type: ignore[return-value]
    return "other"


def get_extraction_hint(page_type: PageType) -> str:
    """Return a type-specific extraction hint to prepend to the extraction prompt."""
    hints: dict[str, str] = {
        "pinout_table": (
            "This page contains a PIN ASSIGNMENT TABLE. Focus on extracting: "
            "(1) a bijection mapping pin numbers to pin names, "
            "(2) a grid with all pin table columns (pin number, name, function, etc.), "
            "(3) units only for standalone specs not in the pin table."
        ),
        "electrical_specs": (
            "This page contains ELECTRICAL CHARACTERISTICS. Focus on extracting: "
            "(1) every parameter as a unit with context including 'Electrical Characteristics' "
            "and whether it is min/typ/max, "
            "(2) a grid capturing the full table structure with headers in row 0, "
            "(3) include test conditions in the context field."
        ),
        "absolute_max_ratings": (
            "This page contains ABSOLUTE MAXIMUM RATINGS. Focus on extracting: "
            "(1) every rating as a unit with context starting with 'Absolute Maximum Ratings - ', "
            "(2) for temperature ranges, extract min and max as separate units, "
            "(3) include ESD ratings if present."
        ),
        "timing_characteristics": (
            "This page contains TIMING CHARACTERISTICS. Focus on extracting: "
            "(1) every timing parameter as a unit (propagation delay, setup time, hold time, "
            "rise time, fall time, clock frequency) with context including 'timing', "
            "(2) a grid if a timing table is present."
        ),
        "package_info": (
            "This page contains PACKAGE INFORMATION. Focus on extracting: "
            "(1) package type, dimensions (length, width, height) as units, "
            "(2) thermal resistance (theta-JA, theta-JC) as units, "
            "(3) weight and MSL rating if present."
        ),
        "text_description": (
            "This page contains GENERAL TEXT (features, description, ordering). Focus on: "
            "(1) part number and ordering information as units, "
            "(2) the component description as a unit with context 'general description overview', "
            "(3) key feature values (e.g. 'operates at 3.3V') as units."
        ),
    }
    return hints.get(page_type, "")

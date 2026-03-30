"""
Shared regex patterns and parsers for the verification rule engine.

Each parser returns a list of (numeric_value, unit_string) tuples found in text.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Regex patterns — ordered by specificity (longer units first)
# ---------------------------------------------------------------------------

VOLTAGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:kV|mV|V|VOLT|VOLTS)\b", re.IGNORECASE
)
CURRENT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:µA|uA|mA|A)\b", re.IGNORECASE
)
CAPACITY_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:mAh|Ah|Wh)\b", re.IGNORECASE
)
RESISTANCE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:MΩ|kΩ|Ω|ohm|ohms)\b", re.IGNORECASE
)
POWER_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:mW|W|WATT|WATTS)\b", re.IGNORECASE
)
TEMPERATURE_PATTERN = re.compile(
    r"([+-]?\d+(?:\.\d+)?)\s*(?:°C|℃|°F|K)\b", re.IGNORECASE
)
FREQUENCY_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:GHz|MHz|kHz|Hz)\b", re.IGNORECASE
)
TIME_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:µs|us|ns|ps|ms|s)\b", re.IGNORECASE
)
DIMENSION_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:mm|mil|cm|in|inch)\b", re.IGNORECASE
)
WEIGHT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:mg|kg|g|oz)\b", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Unit normalization for parsed suffix → canonical unit string
# ---------------------------------------------------------------------------

_CURRENT_UNIT_MAP = {"µa": "µA", "ua": "µA", "ma": "mA", "a": "A"}
_CAPACITY_UNIT_MAP = {"mah": "mAh", "ah": "Ah", "wh": "Wh"}
_POWER_UNIT_MAP = {"mw": "mW", "w": "W", "watt": "W", "watts": "W"}
_TEMP_UNIT_MAP = {"°c": "°C", "℃": "°C", "°f": "°F", "k": "K"}
_FREQ_UNIT_MAP = {"ghz": "GHz", "mhz": "MHz", "khz": "kHz", "hz": "Hz"}
_TIME_UNIT_MAP = {"µs": "µs", "us": "µs", "ns": "ns", "ps": "ps", "ms": "ms", "s": "s"}
_VOLTAGE_UNIT_MAP = {"kv": "kV", "mv": "mV", "v": "V", "volt": "V", "volts": "V"}
_DIMENSION_UNIT_MAP = {"mm": "mm", "mil": "mil", "cm": "cm", "in": "in", "inch": "in"}
_WEIGHT_UNIT_MAP = {"mg": "mg", "g": "g", "kg": "kg", "oz": "oz"}


def _normalize_unit(raw_suffix: str, unit_map: dict[str, str]) -> str:
    return unit_map.get(raw_suffix.lower().strip(), raw_suffix.strip())


def _extract_suffix(match: re.Match) -> str:
    """Get the unit suffix from a regex match (everything after the number)."""
    full = match.group(0)
    num = match.group(1)
    return full[len(num):].strip()


# ---------------------------------------------------------------------------
# Public parsers
# ---------------------------------------------------------------------------

def parse_voltage(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for m in VOLTAGE_PATTERN.finditer(text):
        try:
            out.append((float(m.group(1)), _normalize_unit(_extract_suffix(m), _VOLTAGE_UNIT_MAP)))
        except (TypeError, ValueError):
            continue
    return out


def parse_current(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for m in CURRENT_PATTERN.finditer(text):
        try:
            out.append((float(m.group(1)), _normalize_unit(_extract_suffix(m), _CURRENT_UNIT_MAP)))
        except (TypeError, ValueError):
            continue
    return out


def parse_capacity(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for m in CAPACITY_PATTERN.finditer(text):
        try:
            out.append((float(m.group(1)), _normalize_unit(_extract_suffix(m), _CAPACITY_UNIT_MAP)))
        except (TypeError, ValueError):
            continue
    return out


def parse_power(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for m in POWER_PATTERN.finditer(text):
        try:
            out.append((float(m.group(1)), _normalize_unit(_extract_suffix(m), _POWER_UNIT_MAP)))
        except (TypeError, ValueError):
            continue
    return out


def parse_temperature(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for m in TEMPERATURE_PATTERN.finditer(text):
        try:
            out.append((float(m.group(1)), _normalize_unit(_extract_suffix(m), _TEMP_UNIT_MAP)))
        except (TypeError, ValueError):
            continue
    return out


def parse_frequency(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for m in FREQUENCY_PATTERN.finditer(text):
        try:
            out.append((float(m.group(1)), _normalize_unit(_extract_suffix(m), _FREQ_UNIT_MAP)))
        except (TypeError, ValueError):
            continue
    return out


def parse_time(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for m in TIME_PATTERN.finditer(text):
        try:
            out.append((float(m.group(1)), _normalize_unit(_extract_suffix(m), _TIME_UNIT_MAP)))
        except (TypeError, ValueError):
            continue
    return out


def parse_dimension(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for m in DIMENSION_PATTERN.finditer(text):
        try:
            out.append((float(m.group(1)), _normalize_unit(_extract_suffix(m), _DIMENSION_UNIT_MAP)))
        except (TypeError, ValueError):
            continue
    return out


def parse_weight(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for m in WEIGHT_PATTERN.finditer(text):
        try:
            out.append((float(m.group(1)), _normalize_unit(_extract_suffix(m), _WEIGHT_UNIT_MAP)))
        except (TypeError, ValueError):
            continue
    return out


# ---------------------------------------------------------------------------
# Keyword helpers
# ---------------------------------------------------------------------------

#: Common stop words removed when scoring keyword overlap between question and unit text
STOP_WORDS = frozenset({
    "what", "is", "the", "of", "this", "document", "a", "an", "are", "for",
    "in", "on", "at", "to", "and", "or", "it", "its", "how", "does", "do",
    "that", "which", "with", "from", "can", "has", "have", "be", "was",
    "many", "much",
})


def keyword_overlap(question: str, text: str) -> int:
    """Count meaningful question words that appear in text (case-insensitive)."""
    words = set(re.findall(r"[a-z0-9.]+", question.lower()))
    words -= STOP_WORDS
    text_lower = text.lower()
    return sum(1 for w in words if len(w) > 1 and w in text_lower)


def get_unit_text(u: Any) -> str:
    """Concatenate value, label, and context for parsing and intent matching."""
    parts = [
        str(getattr(u, "value", "")),
        getattr(u, "label", "") or "",
        getattr(u, "context", "") or "",
    ]
    return " ".join(p for p in parts if p)

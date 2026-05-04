"""
Intent classification for query matching (B7).

Deterministic regex + keyword classifier that maps questions to intent categories.
Rules can then filter by intent to avoid spurious matches (e.g., "voltage divider"
shouldn't trigger all voltage rules).
"""

from __future__ import annotations

import re
from enum import Enum, auto


class Intent(Enum):
    """Query intent categories for rule filtering."""

    # Specification lookups
    VOLTAGE_SPEC = auto()
    CURRENT_SPEC = auto()
    POWER_SPEC = auto()
    TEMPERATURE_SPEC = auto()
    TIMING_SPEC = auto()
    FREQUENCY_SPEC = auto()

    # Structural queries
    PIN_LOOKUP = auto()
    PACKAGE_QUERY = auto()
    THERMAL_QUERY = auto()

    # General/fallback
    GENERAL_QUESTION = auto()
    OUT_OF_SCOPE = auto()


# ---------------------------------------------------------------------------
# Pattern definitions for each intent
# ---------------------------------------------------------------------------

# Patterns that indicate the question is asking for a specific value
_SPEC_INDICATORS = re.compile(
    r"\b(what is|what's|what are|how much|how many|value of|rating|spec|specification|limit)\b",
    re.IGNORECASE,
)

# Exclusion patterns - if present, don't classify as that intent
_DESIGN_CONTEXT = re.compile(
    r"\b(design|circuit|schematic|calculate|divider|network|resistor network|"
    r"how do i|how to|recommend|choose|select|compare|versus|vs\.?|between)\b",
    re.IGNORECASE,
)

# Intent-specific patterns
_VOLTAGE_PATTERNS = [
    re.compile(r"\b(max(?:imum)?|min(?:imum)?|operating|supply|input|output)\s+voltage\b", re.I),
    re.compile(r"\bv(?:cc|dd|in|out|oh|ol|ih|il|bat|bus|ref|ss)\b", re.I),
    re.compile(r"\babsolute\s+max(?:imum)?\s+(?:rating)?\s*.*voltage\b", re.I),
    re.compile(r"\bvoltage\s+(?:range|limit|rating|spec)\b", re.I),
]

_CURRENT_PATTERNS = [
    re.compile(r"\b(max(?:imum)?|min(?:imum)?|operating|supply|input|output)\s+current\b", re.I),
    re.compile(r"\bi(?:cc|dd|oh|ol|in|out|q|leak|standby|sleep)\b", re.I),
    re.compile(r"\bcurrent\s+(?:consumption|draw|limit|rating|spec)\b", re.I),
    re.compile(r"\bleakage\s+current\b", re.I),
]

_POWER_PATTERNS = [
    re.compile(r"\bpower\s+(?:dissipation|consumption|rating|limit)\b", re.I),
    re.compile(r"\b(?:max(?:imum)?|total)\s+power\b", re.I),
    re.compile(r"\bp(?:d|tot|max)\b", re.I),
    re.compile(r"\b(?:milliwatts?|watts?|mw|w)\s+(?:rating|dissipation)\b", re.I),
]

_TEMPERATURE_PATTERNS = [
    re.compile(r"\b(operating|storage|junction|ambient)\s+temp(?:erature)?\b", re.I),
    re.compile(r"\bt(?:j|a|op|stg|amb)(?:_max|_min)?\b", re.I),
    re.compile(r"\btemp(?:erature)?\s+(?:range|limit|rating)\b", re.I),
    re.compile(r"\bsoldering?\s+temp(?:erature)?\b", re.I),
    re.compile(r"\breflow\b", re.I),
]

_TIMING_PATTERNS = [
    re.compile(r"\b(propagation|rise|fall|setup|hold)\s+(?:time|delay)\b", re.I),
    re.compile(r"\bt(?:pd|r|f|su|h|phl|plh)\b", re.I),
    re.compile(r"\bslew\s+rate\b", re.I),
    re.compile(r"\bdelay\s+time\b", re.I),
]

_FREQUENCY_PATTERNS = [
    re.compile(r"\b(clock|operating|max(?:imum)?)\s+frequency\b", re.I),
    re.compile(r"\bf(?:max|clk|osc)\b", re.I),
    re.compile(r"\bbandwidth\b", re.I),
    re.compile(r"\bdata\s+rate\b", re.I),
    re.compile(r"\b(?:mhz|ghz|khz)\b", re.I),
]

_PIN_PATTERNS = [
    re.compile(r"\bpin\s+(?:\d+|number|#|no\.?)\b", re.I),
    re.compile(r"\bwhat\s+is\s+pin\s+\d+\b", re.I),
    re.compile(r"\bpin(?:out|assignment|description|function)\b", re.I),
    re.compile(r"\bfunction\s+of\s+pin\b", re.I),
]

_PACKAGE_PATTERNS = [
    re.compile(r"\bpackage\s+(?:type|size|dimensions?|footprint)\b", re.I),
    re.compile(r"\b(?:soic|qfp|qfn|bga|dip|sot|tssop|lqfp|dfn)\b", re.I),
    re.compile(r"\bpin\s+count\b", re.I),
    re.compile(r"\b(?:how\s+many|number\s+of)\s+pins\b", re.I),
    re.compile(r"\bfootprint\b", re.I),
    re.compile(r"\bdimensions?\b", re.I),
    re.compile(r"\bweight\b", re.I),
    re.compile(r"\bmsl\b", re.I),
    re.compile(r"\bmoisture\s+sensitivity\b", re.I),
]

_THERMAL_PATTERNS = [
    re.compile(r"\bthermal\s+(?:resistance|impedance)\b", re.I),
    re.compile(r"\b[rθ](?:ja|jc|ca)\b", re.I),
    re.compile(r"\bjunction[\s-]to[\s-](?:ambient|case)\b", re.I),
    re.compile(r"\bθ(?:ja|jc)\b", re.I),
    re.compile(r"\bthermal\s+(?:pad|via|management)\b", re.I),
]

_OUT_OF_SCOPE_PATTERNS = [
    re.compile(r"\b(weather|stock|price|news|who is|where is|when did)\b", re.I),
    re.compile(r"\b(recipe|movie|song|book|game)\b", re.I),
]


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------


def _has_design_context(question: str) -> bool:
    """Check if question is about design/calculation rather than spec lookup."""
    return _DESIGN_CONTEXT.search(question) is not None


def _match_any(patterns: list[re.Pattern], question: str) -> bool:
    """Check if any pattern matches the question."""
    return any(p.search(question) for p in patterns)


def classify_intent(question: str) -> Intent:
    """
    Classify a question into an intent category.

    This is a deterministic regex + keyword classifier that covers ~70% of cases.
    The goal is to filter out spurious rule matches while allowing legitimate
    spec lookups through.

    Returns:
        The classified intent. If uncertain, returns GENERAL_QUESTION.
    """
    q = question.strip()

    # Check for clearly out-of-scope questions
    if _match_any(_OUT_OF_SCOPE_PATTERNS, q):
        return Intent.OUT_OF_SCOPE

    # Check if asking for a specific spec value (not design context)
    is_spec_question = _SPEC_INDICATORS.search(q) is not None
    has_design_ctx = _has_design_context(q)

    # PIN_LOOKUP is usually unambiguous
    if _match_any(_PIN_PATTERNS, q):
        return Intent.PIN_LOOKUP

    # PACKAGE_QUERY is fairly unambiguous
    if _match_any(_PACKAGE_PATTERNS, q):
        return Intent.PACKAGE_QUERY

    # THERMAL_QUERY
    if _match_any(_THERMAL_PATTERNS, q):
        return Intent.THERMAL_QUERY

    # For spec lookups, check if it's a clear specification question
    # and not a design/calculation question
    if is_spec_question or not has_design_ctx:
        # Priority order: more specific patterns first
        if _match_any(_VOLTAGE_PATTERNS, q):
            return Intent.VOLTAGE_SPEC

        if _match_any(_CURRENT_PATTERNS, q):
            return Intent.CURRENT_SPEC

        if _match_any(_POWER_PATTERNS, q):
            return Intent.POWER_SPEC

        if _match_any(_TEMPERATURE_PATTERNS, q):
            return Intent.TEMPERATURE_SPEC

        if _match_any(_TIMING_PATTERNS, q):
            return Intent.TIMING_SPEC

        if _match_any(_FREQUENCY_PATTERNS, q):
            return Intent.FREQUENCY_SPEC

    # If we have design context, be conservative
    if has_design_ctx:
        return Intent.GENERAL_QUESTION

    # Default to general question
    return Intent.GENERAL_QUESTION


def intent_allows_rule(question_intent: Intent, rule_intents: set[Intent] | None) -> bool:
    """
    Check if a rule should fire given the question's intent.

    Args:
        question_intent: The classified intent of the question.
        rule_intents: Set of intents the rule handles. None means rule accepts all.

    Returns:
        True if the rule should be considered for this question.
    """
    # OUT_OF_SCOPE should refuse all rules
    if question_intent == Intent.OUT_OF_SCOPE:
        return False

    # Rules with no intent filter accept all questions (except OUT_OF_SCOPE)
    if rule_intents is None:
        return True

    # GENERAL_QUESTION allows all rules (fallback behavior)
    if question_intent == Intent.GENERAL_QUESTION:
        return True

    # Check if the question intent matches any rule intent
    return question_intent in rule_intents


# ---------------------------------------------------------------------------
# Intent-to-rule mapping helpers
# ---------------------------------------------------------------------------

# Map rule names to their allowed intents
RULE_INTENT_MAP: dict[str, set[Intent]] = {
    # Pin/ID lookups
    "pin_lookup": {Intent.PIN_LOOKUP},
    "pin_count": {Intent.PIN_LOOKUP, Intent.PACKAGE_QUERY},
    # Package queries
    "package_type": {Intent.PACKAGE_QUERY},
    "package_dimensions": {Intent.PACKAGE_QUERY},
    "weight": {Intent.PACKAGE_QUERY},
    "moisture_sensitivity": {Intent.PACKAGE_QUERY},
    # Voltage specs
    "absolute_max_voltage": {Intent.VOLTAGE_SPEC},
    "max_voltage": {Intent.VOLTAGE_SPEC},
    "operating_voltage_range": {Intent.VOLTAGE_SPEC},
    "threshold_voltage": {Intent.VOLTAGE_SPEC},
    # Current specs
    "absolute_max_current": {Intent.CURRENT_SPEC},
    "max_current": {Intent.CURRENT_SPEC},
    "leakage_current": {Intent.CURRENT_SPEC},
    # Power specs
    "power_dissipation": {Intent.POWER_SPEC},
    # Temperature specs
    "operating_temperature_range": {Intent.TEMPERATURE_SPEC},
    "storage_temperature": {Intent.TEMPERATURE_SPEC},
    "soldering_temperature": {Intent.TEMPERATURE_SPEC},
    # Thermal queries
    "thermal_resistance": {Intent.THERMAL_QUERY},
    # Timing specs
    "propagation_delay": {Intent.TIMING_SPEC},
    "rise_fall_time": {Intent.TIMING_SPEC},
    "setup_hold_time": {Intent.TIMING_SPEC},
    # Frequency specs
    "clock_frequency": {Intent.FREQUENCY_SPEC},
    # General/fallback rules (no intent filter - accept all)
    # These are handled by rule_intents=None
}


def get_rule_intents(rule_name: str) -> set[Intent] | None:
    """Get the allowed intents for a rule, or None if rule accepts all."""
    return RULE_INTENT_MAP.get(rule_name)

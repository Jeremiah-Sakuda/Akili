"""
Shadow formatting: rephrase a verified fact into a 1-sentence answer using Gemini.

Strict fact-only prompting; no outside knowledge. Returns None on failure or UNABLE TO PHRASE.
Used only when we already have an AnswerWithProof — never blocks or replaces the verified answer.
"""

from __future__ import annotations

import logging
import os

import google.generativeai as genai

logger = logging.getLogger(__name__)

_GEMINI_MODEL = os.environ.get("AKILI_GEMINI_MODEL", "gemini-3-pro-preview")
UNABLE_TO_PHRASE = "UNABLE TO PHRASE"

FORMAT_PROMPT = (
    "Input: User Question [Q], Verified Fact [F], Coordinates [C].\n"
    "Task: Rephrase F into a 1-sentence answer to Q. "
    "DO NOT add outside knowledge. Do not add units or interpretation not present in F.\n"
    "If F does not answer Q, return exactly: UNABLE TO PHRASE\n\n"
    "Q: {question}\n"
    "F: {verified_fact}\n"
    "C: {coordinates}\n\n"
    "One sentence only, or UNABLE TO PHRASE."
)


def format_answer(question: str, verified_fact: str, coordinates: str) -> str | None:
    """
    Ask Gemini to rephrase the verified fact into a 1-sentence answer to the question.

    Returns the sentence, or None if API key missing, call fails, or model returns UNABLE TO PHRASE.
    """
    if not os.environ.get("GOOGLE_API_KEY", "").strip():
        return None
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(_GEMINI_MODEL)
    prompt = FORMAT_PROMPT.format(
        question=question,
        verified_fact=verified_fact,
        coordinates=coordinates,
    )
    try:
        response = model.generate_content(prompt)
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
        if not text or UNABLE_TO_PHRASE in text.upper():
            return None
        return text
    except Exception as e:
        logger.warning("Gemini format_answer failed (silent fallback): %s", e)
        return None


REFUSAL_PROMPT = (
    "The user asked a question about a technical document. No verified answer was found.\n\n"
    "User question: {question}\n\n"
    "Document contents: {doc_summary}\n\n"
    "Task: Write a short refusal reason (1–2 sentences) in plain language. "
    "Examples: 'No mention of that was found in the document.' "
    "'The document has pin mappings but none match your question.' "
    "'I found voltage values in the doc but they don't match what you asked.' "
    "Do not invent facts; only refer to what is in the document or that nothing matched. "
    "One or two sentences only."
)


def format_refusal(
    question: str,
    n_units: int,
    n_bijections: int,
    n_grids: int,
) -> str | None:
    """
    Ask Gemini to phrase a short, natural-language reason for refusing to answer.

    Returns the reason string, or None if API key missing, call fails, or empty response.
    """
    if not os.environ.get("GOOGLE_API_KEY", "").strip():
        return None
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(_GEMINI_MODEL)
    doc_summary = (
        f"{n_units} units (e.g. voltages, labels), "
        f"{n_bijections} bijections (e.g. pin name ↔ number), "
        f"{n_grids} grids (tables)."
    )
    prompt = REFUSAL_PROMPT.format(question=question, doc_summary=doc_summary)
    try:
        response = model.generate_content(prompt)
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
            return None
        return text
    except Exception as e:
        logger.warning("Gemini format_refusal failed (silent fallback): %s", e)
        return None

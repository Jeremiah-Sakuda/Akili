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

_GEMINI_MODEL = os.environ.get("AKILI_GEMINI_MODEL", "gemini-3.0-flash")
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

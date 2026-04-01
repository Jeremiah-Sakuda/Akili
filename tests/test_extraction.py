"""Tests for extraction prompt, schema simplification, and page classifier."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from akili.ingest.gemini_extract import EXTRACT_PROMPT, _simplified_extraction_schema
from akili.ingest.page_classifier import (
    VALID_PAGE_TYPES,
    classify_page,
    get_extraction_hint,
)


class TestExtractPrompt:
    """A3.T1: Verify the prompt includes few-shot examples and key instructions."""

    def test_prompt_has_pinout_example(self):
        assert "Pin Assignment Table" in EXTRACT_PROMPT or "Pin Number" in EXTRACT_PROMPT

    def test_prompt_has_electrical_example(self):
        assert "Electrical Characteristics" in EXTRACT_PROMPT

    def test_prompt_has_absolute_max_example(self):
        assert "Absolute Maximum Ratings" in EXTRACT_PROMPT

    def test_prompt_has_coordinate_calibration(self):
        assert "Coordinate Calibration" in EXTRACT_PROMPT
        assert "bbox should cover the ENTIRE" in EXTRACT_PROMPT

    def test_prompt_has_context_instructions(self):
        assert "ALWAYS include a `context` field" in EXTRACT_PROMPT

    def test_prompt_has_min_typ_max_instruction(self):
        assert "min/typ/max" in EXTRACT_PROMPT

    def test_prompt_has_section_heading_instruction(self):
        assert "section heading" in EXTRACT_PROMPT


class TestSimplifiedSchema:
    """A3.T2: Verify the simplified schema has no $defs."""

    def test_no_defs_key(self):
        schema = _simplified_extraction_schema()
        assert "$defs" not in schema
        assert "definitions" not in schema

    def test_has_required_top_level_keys(self):
        schema = _simplified_extraction_schema()
        assert schema["type"] == "object"
        props = schema["properties"]
        assert "units" in props
        assert "bijections" in props
        assert "grids" in props

    def test_units_schema_has_required_fields(self):
        schema = _simplified_extraction_schema()
        unit_schema = schema["properties"]["units"]["items"]
        assert "id" in unit_schema["properties"]
        assert "value" in unit_schema["properties"]
        assert "origin" in unit_schema["properties"]
        assert "context" in unit_schema["properties"]
        assert "label" in unit_schema["properties"]
        assert "unit_of_measure" in unit_schema["properties"]

    def test_origin_is_flat_object(self):
        schema = _simplified_extraction_schema()
        origin = schema["properties"]["units"]["items"]["properties"]["origin"]
        assert origin["type"] == "object"
        assert "x" in origin["properties"]
        assert "y" in origin["properties"]


class TestPageClassifier:
    """A3.T3: Test page classifier behavior."""

    def test_valid_page_types_comprehensive(self):
        assert "pinout_table" in VALID_PAGE_TYPES
        assert "electrical_specs" in VALID_PAGE_TYPES
        assert "absolute_max_ratings" in VALID_PAGE_TYPES
        assert "timing_characteristics" in VALID_PAGE_TYPES
        assert "package_info" in VALID_PAGE_TYPES
        assert "block_diagram" in VALID_PAGE_TYPES
        assert "text_description" in VALID_PAGE_TYPES
        assert "other" in VALID_PAGE_TYPES

    def test_classify_returns_other_when_disabled(self):
        result = classify_page(b"fake_image_bytes")
        assert result == "other"

    @patch("akili.config.PAGE_CLASSIFY_ENABLED", True)
    @patch("akili.ingest.page_classifier.genai")
    def test_classify_returns_valid_type(self, mock_genai):
        mock_response = MagicMock()
        mock_response.text = "electrical_specs"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        import os
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            result = classify_page(b"fake_image_bytes")
        assert result == "electrical_specs"

    @patch("akili.config.PAGE_CLASSIFY_ENABLED", True)
    @patch("akili.ingest.page_classifier.genai")
    def test_classify_invalid_response_returns_other(self, mock_genai):
        mock_response = MagicMock()
        mock_response.text = "some_invalid_type"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        import os
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            result = classify_page(b"fake_image_bytes")
        assert result == "other"

    def test_classify_no_api_key_returns_other(self):
        import os
        with patch.dict(os.environ, {}, clear=True):
            with patch("akili.config.PAGE_CLASSIFY_ENABLED", True):
                result = classify_page(b"fake_image_bytes")
        assert result == "other"

    def test_extraction_hint_for_known_types(self):
        for ptype in ["pinout_table", "electrical_specs", "absolute_max_ratings",
                       "timing_characteristics", "package_info", "text_description"]:
            hint = get_extraction_hint(ptype)  # type: ignore[arg-type]
            assert len(hint) > 0, f"No hint for {ptype}"

    def test_extraction_hint_for_other(self):
        hint = get_extraction_hint("other")
        assert hint == ""

    def test_extraction_hint_for_block_diagram(self):
        hint = get_extraction_hint("block_diagram")
        assert hint == ""

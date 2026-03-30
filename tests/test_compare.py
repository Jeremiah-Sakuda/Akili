"""Tests for C3: Cross-Document Comparison."""

from __future__ import annotations

import pytest

from akili.canonical import Unit
from akili.canonical.models import Point
from akili.verify.compare import (
    ComparisonResult,
    compare_documents,
    format_comparison_response,
)


def _doc_units(
    doc_id: str,
    vcc: float = 3.3,
    vmax: float = 5.5,
    theta: float = 45.0,
) -> list[Unit]:
    return [
        Unit(id=f"{doc_id}_vcc", label="VCC", value=vcc, unit_of_measure="V",
             context="supply voltage", origin=Point(x=0.1, y=0.1), doc_id=doc_id, page=0),
        Unit(id=f"{doc_id}_vmax", label="VCC max", value=vmax, unit_of_measure="V",
             context="absolute maximum voltage", origin=Point(x=0.2, y=0.1), doc_id=doc_id, page=0),
        Unit(id=f"{doc_id}_theta", label="θJA", value=theta, unit_of_measure="°C/W",
             context="thermal resistance junction to ambient", origin=Point(x=0.3, y=0.3), doc_id=doc_id, page=2),
    ]


class TestCompareDocuments:
    def test_compare_max_voltage(self) -> None:
        doc_data = {
            "d1": ("Component A", _doc_units("d1", vmax=5.5)),
            "d2": ("Component B", _doc_units("d2", vmax=6.0)),
        }
        results = compare_documents("Compare the max voltage", doc_data)
        voltage_results = [r for r in results if "Voltage" in r.parameter]
        assert len(voltage_results) > 0
        vmax = [r for r in results if "Maximum Voltage" in r.parameter]
        assert len(vmax) == 1
        assert vmax[0].best_doc_id == "d1"
        assert vmax[0].best_value == 5.5

    def test_compare_thermal_resistance(self) -> None:
        doc_data = {
            "d1": ("Component A", _doc_units("d1", theta=45.0)),
            "d2": ("Component B", _doc_units("d2", theta=30.0)),
        }
        results = compare_documents("Which has lowest thermal resistance?", doc_data)
        thermal = [r for r in results if "Thermal" in r.parameter]
        assert len(thermal) == 1
        assert thermal[0].best_doc_id == "d2"
        assert thermal[0].best_value == 30.0

    def test_compare_all_parameters(self) -> None:
        doc_data = {
            "d1": ("Component A", _doc_units("d1")),
            "d2": ("Component B", _doc_units("d2")),
        }
        results = compare_documents("Compare all", doc_data)
        assert len(results) > 0

    def test_missing_param_in_one_doc(self) -> None:
        doc_data = {
            "d1": ("Component A", _doc_units("d1")),
            "d2": ("Component B", []),
        }
        results = compare_documents("Compare max voltage", doc_data)
        vmax = [r for r in results if "Maximum Voltage" in r.parameter]
        assert len(vmax) == 1
        rows = vmax[0].rows
        assert any(r.value is None for r in rows)

    def test_two_rows_per_doc(self) -> None:
        doc_data = {
            "d1": ("A", _doc_units("d1")),
            "d2": ("B", _doc_units("d2")),
            "d3": ("C", _doc_units("d3")),
        }
        results = compare_documents("Compare thermal resistance", doc_data)
        thermal = [r for r in results if "Thermal" in r.parameter][0]
        assert len(thermal.rows) == 3


class TestFormatComparisonResponse:
    def test_serialization(self) -> None:
        doc_data = {
            "d1": ("Component A", _doc_units("d1")),
            "d2": ("Component B", _doc_units("d2")),
        }
        results = compare_documents("Compare max voltage", doc_data)
        formatted = format_comparison_response(results)
        assert "comparisons" in formatted
        assert len(formatted["comparisons"]) > 0
        comp = formatted["comparisons"][0]
        assert "parameter" in comp
        assert "rows" in comp
        assert "best_doc_id" in comp

    def test_empty_results(self) -> None:
        formatted = format_comparison_response([])
        assert formatted == {"comparisons": []}

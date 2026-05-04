"""Tests for C3: Cross-Document Comparison."""

from __future__ import annotations

from akili.canonical import Unit
from akili.canonical.models import Point
from akili.verify.compare import (
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
        Unit(
            id=f"{doc_id}_vcc",
            label="VCC",
            value=vcc,
            unit_of_measure="V",
            context="supply voltage",
            origin=Point(x=0.1, y=0.1),
            doc_id=doc_id,
            page=0,
        ),
        Unit(
            id=f"{doc_id}_vmax",
            label="VCC max",
            value=vmax,
            unit_of_measure="V",
            context="absolute maximum voltage",
            origin=Point(x=0.2, y=0.1),
            doc_id=doc_id,
            page=0,
        ),
        Unit(
            id=f"{doc_id}_theta",
            label="θJA",
            value=theta,
            unit_of_measure="°C/W",
            context="thermal resistance junction to ambient",
            origin=Point(x=0.3, y=0.3),
            doc_id=doc_id,
            page=2,
        ),
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


# ---------------------------------------------------------------------------
# API endpoint tests (D3)
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from akili.api.app import app

client = TestClient(app)


class TestCompareEndpoint:
    """Tests for POST /compare."""

    def test_compare_requires_two_docs(self):
        """Comparison requires at least 2 documents."""
        r = client.post(
            "/compare",
            json={"doc_ids": ["doc1"], "question": "Compare voltage"},
        )
        assert r.status_code == 400
        assert "At least 2" in r.json()["detail"]

    @patch("akili.api.routers.compare.get_store")
    @patch("akili.api.routers.compare.compare_documents")
    @patch("akili.api.routers.compare.format_comparison_response")
    def test_compare_returns_results(self, mock_format, mock_compare, mock_get_store):
        """Comparison should return formatted results."""
        mock_store = MagicMock()
        mock_store.get_document_owner.return_value = None
        mock_store.list_documents.return_value = [
            {"doc_id": "doc1", "filename": "comp1.pdf"},
            {"doc_id": "doc2", "filename": "comp2.pdf"},
        ]
        mock_store.get_units_by_doc.return_value = []
        mock_get_store.return_value = mock_store

        mock_compare.return_value = []
        mock_format.return_value = {"comparisons": []}

        r = client.post(
            "/compare",
            json={"doc_ids": ["doc1", "doc2"], "question": "Compare max voltage"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "comparisons" in data


class TestCompareExport:
    """Tests for POST /compare/export (D3)."""

    @patch("akili.api.routers.compare.get_store")
    @patch("akili.api.routers.compare.compare_documents")
    def test_csv_export(self, mock_compare, mock_get_store):
        """CSV export should return valid CSV."""
        from akili.verify.compare import ComparisonResult, ComparisonRow

        mock_store = MagicMock()
        mock_store.get_document_owner.return_value = None
        mock_store.list_documents.return_value = [
            {"doc_id": "doc1", "filename": "comp1.pdf"},
            {"doc_id": "doc2", "filename": "comp2.pdf"},
        ]
        mock_store.get_units_by_doc.return_value = []
        mock_get_store.return_value = mock_store

        mock_compare.return_value = [
            ComparisonResult(
                parameter="Maximum Voltage",
                direction="lower",
                best_doc_id="doc1",
                best_value=5.0,
                rows=[
                    ComparisonRow(
                        doc_id="doc1",
                        doc_name="comp1.pdf",
                        parameter="Maximum Voltage",
                        value=5.0,
                        unit_of_measure="V",
                        source_unit_id="u1",
                        page=1,
                        proof=None,
                    ),
                    ComparisonRow(
                        doc_id="doc2",
                        doc_name="comp2.pdf",
                        parameter="Maximum Voltage",
                        value=6.0,
                        unit_of_measure="V",
                        source_unit_id="u2",
                        page=1,
                        proof=None,
                    ),
                ],
            )
        ]

        r = client.post(
            "/compare/export?format=csv",
            json={"doc_ids": ["doc1", "doc2"]},
        )
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]

        content = r.text
        assert "Parameter" in content
        assert "Maximum Voltage" in content

    def test_export_requires_two_docs(self):
        """Export requires at least 2 documents."""
        r = client.post(
            "/compare/export",
            json={"doc_ids": ["doc1"]},
        )
        assert r.status_code == 400

    def test_export_max_ten_docs(self):
        """Export is limited to 10 documents."""
        r = client.post(
            "/compare/export",
            json={"doc_ids": [f"doc{i}" for i in range(11)]},
        )
        assert r.status_code == 400
        assert "Maximum 10" in r.json()["detail"]

    @patch("akili.api.routers.compare.get_store")
    @patch("akili.api.routers.compare.compare_documents")
    @patch("akili.api.routers.compare.format_comparison_response")
    def test_json_export(self, mock_format, mock_compare, mock_get_store):
        """JSON export should return standard comparison response."""
        mock_store = MagicMock()
        mock_store.get_document_owner.return_value = None
        mock_store.list_documents.return_value = []
        mock_store.get_units_by_doc.return_value = []
        mock_get_store.return_value = mock_store

        mock_compare.return_value = []
        mock_format.return_value = {"comparisons": []}

        r = client.post(
            "/compare/export?format=json",
            json={"doc_ids": ["doc1", "doc2"]},
        )
        assert r.status_code == 200
        assert r.json()["comparisons"] == []

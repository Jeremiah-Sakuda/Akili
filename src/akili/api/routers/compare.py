"""
Document comparison endpoint (D3).

Supports cross-document parameter comparison with export to CSV.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from akili.api.auth import get_current_user
from akili.api.deps import get_store, require_doc_access, validate_doc_id
from akili.verify.compare import compare_documents, format_comparison_response

router = APIRouter(tags=["compare"])


class CompareRequest(BaseModel):
    doc_ids: list[str] = Field(..., description="2+ document IDs to compare")
    question: str = Field(..., description="What to compare (e.g. 'Compare max voltage')")


@router.post("/compare")
async def compare_docs(
    req: CompareRequest,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """Compare parameters across multiple documents."""
    if len(req.doc_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 doc_ids required")

    # A2: validate and check ownership for all documents upfront
    for did in req.doc_ids:
        validate_doc_id(did)
        require_doc_access(did, _user)

    store = get_store()
    docs = store.list_documents()
    doc_name_map = {d["doc_id"]: d.get("filename", d["doc_id"]) for d in docs}

    doc_units: dict[str, tuple[str, list]] = {}
    for did in req.doc_ids:
        units = store.get_units_by_doc(did)
        name = doc_name_map.get(did, did)
        doc_units[did] = (name, units)

    results = compare_documents(req.question, doc_units)
    return JSONResponse(content=format_comparison_response(results))


class CompareExportRequest(BaseModel):
    doc_ids: list[str] = Field(..., description="2+ document IDs to compare")
    parameters: list[str] = Field(
        default=None,
        description="Parameters to include (default: all detected)",
    )


def _generate_comparison_csv(results: list, doc_names: dict[str, str]) -> str:
    """Generate CSV from comparison results."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Build header: Parameter, Doc1, Doc2, Doc3, ..., Best
    doc_ids = []
    for r in results:
        for row in r.rows:
            if row.doc_id not in doc_ids:
                doc_ids.append(row.doc_id)

    header = ["Parameter"]
    header.extend(doc_names.get(did, did) for did in doc_ids)
    header.append("Best Value")
    header.append("Best Component")
    writer.writerow(header)

    # Data rows
    for r in results:
        row_data = [r.parameter]
        doc_values = {row.doc_id: row for row in r.rows}

        for did in doc_ids:
            dr = doc_values.get(did)
            if dr and dr.value is not None:
                val_str = f"{dr.value}"
                if dr.unit_of_measure:
                    val_str += f" {dr.unit_of_measure}"
                row_data.append(val_str)
            else:
                row_data.append("N/A")

        # Best value and component
        if r.best_value is not None:
            best_row = next((row for row in r.rows if row.doc_id == r.best_doc_id), None)
            unit = best_row.unit_of_measure if best_row else ""
            row_data.append(f"{r.best_value} {unit}".strip())
            row_data.append(doc_names.get(r.best_doc_id, r.best_doc_id))
        else:
            row_data.append("N/A")
            row_data.append("N/A")

        writer.writerow(row_data)

    return output.getvalue()


@router.post("/compare/export")
async def export_comparison(
    req: CompareExportRequest,
    format: Literal["csv", "json"] = Query("csv", description="Export format"),
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> Response:
    """
    Export comparison results.

    Generates a downloadable comparison matrix for 2-5 components.
    CSV format creates a spreadsheet-ready table with best values highlighted.
    """
    if len(req.doc_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 doc_ids required")
    if len(req.doc_ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 documents for comparison")

    # Validate and check access
    for did in req.doc_ids:
        validate_doc_id(did)
        require_doc_access(did, _user)

    store = get_store()
    docs = store.list_documents()
    doc_name_map = {d["doc_id"]: d.get("filename", d["doc_id"]) for d in docs}

    doc_units: dict[str, tuple[str, list]] = {}
    for did in req.doc_ids:
        units = store.get_units_by_doc(did)
        name = doc_name_map.get(did, did)
        doc_units[did] = (name, units)

    # Generate comparison for all parameters
    query = "Compare all parameters"
    if req.parameters:
        query = f"Compare {', '.join(req.parameters)}"

    results = compare_documents(query, doc_units)

    if format == "csv":
        csv_content = _generate_comparison_csv(results, doc_name_map)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=comparison_matrix.csv",
            },
        )
    else:
        return JSONResponse(content=format_comparison_response(results))

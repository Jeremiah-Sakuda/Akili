"""
Audit trail export endpoints (C3).

Provides exportable audit trails for compliance requirements.
Supports JSON, CSV, and PDF formats with HMAC signatures.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from akili.api.auth import get_current_user
from akili.api.deps import get_store, require_doc_access, validate_doc_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audit"])

# HMAC signing key from environment
AUDIT_SIGNING_KEY = os.environ.get("AKILI_AUDIT_SIGNING_KEY", "").encode("utf-8")


def _compute_hmac(data: bytes) -> str:
    """Compute HMAC-SHA256 signature for audit data."""
    if not AUDIT_SIGNING_KEY:
        return "unsigned"
    return hmac.new(AUDIT_SIGNING_KEY, data, hashlib.sha256).hexdigest()


def _format_timestamp(ts: str | None) -> str:
    """Format timestamp for display."""
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError):
        return str(ts)


def _flatten_details(details: dict | None) -> str:
    """Flatten details dict for CSV export."""
    if not details:
        return ""
    parts = []
    for key, value in details.items():
        if isinstance(value, (list, dict)):
            parts.append(f"{key}={json.dumps(value)}")
        else:
            parts.append(f"{key}={value}")
    return "; ".join(parts)


def _generate_json_export(
    doc_id: str, audit_entries: list[dict], doc_info: dict | None
) -> dict[str, Any]:
    """Generate JSON export with metadata."""
    export_time = datetime.now(timezone.utc).isoformat() + "Z"
    export_data = {
        "export_info": {
            "doc_id": doc_id,
            "export_time": export_time,
            "entry_count": len(audit_entries),
            "format": "json",
        },
        "document": doc_info or {},
        "audit_trail": audit_entries,
    }

    # Add HMAC signature
    data_bytes = json.dumps(export_data, sort_keys=True).encode("utf-8")
    export_data["signature"] = {
        "algorithm": "HMAC-SHA256",
        "value": _compute_hmac(data_bytes),
    }

    return export_data


def _generate_csv_export(doc_id: str, audit_entries: list[dict]) -> str:
    """Generate CSV export."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["id", "doc_id", "action", "actor", "details", "timestamp"])

    # Data rows
    for entry in audit_entries:
        writer.writerow(
            [
                entry.get("id", ""),
                entry.get("doc_id", ""),
                entry.get("action", ""),
                entry.get("actor", ""),
                _flatten_details(entry.get("details")),
                _format_timestamp(entry.get("created_at")),
            ]
        )

    csv_content = output.getvalue()

    # Append signature as comment
    signature = _compute_hmac(csv_content.encode("utf-8"))
    csv_content += f"\n# HMAC-SHA256: {signature}\n"

    return csv_content


def _generate_pdf_export(doc_id: str, audit_entries: list[dict], doc_info: dict | None) -> bytes:
    """Generate PDF export using ReportLab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="PDF export requires ReportLab. Install with: pip install reportlab",
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=20,
    )
    story.append(Paragraph("AKILI Audit Trail Export", title_style))
    story.append(Spacer(1, 12))

    # Document info
    story.append(Paragraph(f"<b>Document ID:</b> {doc_id}", styles["Normal"]))
    export_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    story.append(Paragraph(f"<b>Export Time:</b> {export_time}", styles["Normal"]))
    story.append(Paragraph(f"<b>Total Entries:</b> {len(audit_entries)}", styles["Normal"]))

    if doc_info:
        if doc_info.get("filename"):
            story.append(Paragraph(f"<b>Filename:</b> {doc_info['filename']}", styles["Normal"]))
        if doc_info.get("created_at"):
            story.append(
                Paragraph(
                    f"<b>Uploaded:</b> {_format_timestamp(doc_info['created_at'])}",
                    styles["Normal"],
                )
            )

    story.append(Spacer(1, 24))

    # Audit table
    story.append(Paragraph("<b>Audit Trail</b>", styles["Heading2"]))
    story.append(Spacer(1, 12))

    # Build table data
    table_data = [["#", "Action", "Actor", "Details", "Timestamp"]]
    for entry in audit_entries:
        details_str = _flatten_details(entry.get("details"))
        if len(details_str) > 50:
            details_str = details_str[:47] + "..."
        table_data.append(
            [
                str(entry.get("id", "")),
                entry.get("action", ""),
                entry.get("actor", "system"),
                details_str,
                _format_timestamp(entry.get("created_at")),
            ]
        )

    # Create table
    table = Table(table_data, colWidths=[0.5 * inch, 1.2 * inch, 1 * inch, 2.5 * inch, 1.5 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 24))

    # Build PDF content for signature
    doc.build(story)
    pdf_content = buffer.getvalue()
    signature = _compute_hmac(pdf_content)

    # Rebuild with signature footer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5 * inch)
    story.append(Spacer(1, 24))
    story.append(Paragraph(f"<b>HMAC-SHA256:</b> {signature}", styles["Normal"]))
    story.append(
        Paragraph(
            "<i>This signature can be verified against the AKILI audit signing key.</i>",
            styles["Normal"],
        )
    )
    doc.build(story)

    return buffer.getvalue()


@router.get("/documents/{doc_id}/audit")
async def export_audit_trail(
    doc_id: str,
    format: Literal["json", "csv", "pdf"] = Query("json", description="Export format"),
    limit: int = Query(1000, ge=1, le=10000, description="Max entries to export"),
    user: dict[str, Any] | None = Depends(get_current_user),
) -> Response:
    """
    Export the audit trail for a document.

    Returns a signed export containing:
    - Document metadata
    - All audit events (upload, extraction, corrections, queries)
    - HMAC signature for tamper detection

    Formats:
    - json: Full structured export with nested objects
    - csv: Tabular format for spreadsheet analysis
    - pdf: Formatted report for compliance documentation
    """
    validate_doc_id(doc_id)
    require_doc_access(doc_id, user)

    store = get_store()

    # Get audit entries
    audit_entries = store.get_audit_log(doc_id=doc_id, limit=limit)

    # Get document info
    doc_info = None
    try:
        docs = store.list_documents()
        for d in docs:
            if d.get("doc_id") == doc_id:
                doc_info = d
                break
    except Exception as e:
        logger.warning(f"Could not retrieve document info: {e}")

    if format == "json":
        export_data = _generate_json_export(doc_id, audit_entries, doc_info)
        return JSONResponse(content=export_data)

    elif format == "csv":
        csv_content = _generate_csv_export(doc_id, audit_entries)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_{doc_id}.csv",
            },
        )

    elif format == "pdf":
        pdf_content = _generate_pdf_export(doc_id, audit_entries, doc_info)
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=audit_{doc_id}.pdf",
            },
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


@router.get("/audit/verify")
async def verify_audit_signature(
    signature: str = Query(..., description="The HMAC signature to verify"),
    data: str = Query(..., description="The data that was signed (base64 encoded)"),
) -> JSONResponse:
    """
    Verify an audit export signature.

    Used to confirm that an exported audit trail has not been tampered with.
    """
    import base64

    if not AUDIT_SIGNING_KEY:
        raise HTTPException(
            status_code=501,
            detail="Audit signing not configured. Set AKILI_AUDIT_SIGNING_KEY.",
        )

    try:
        data_bytes = base64.b64decode(data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 data")

    expected_signature = _compute_hmac(data_bytes)
    is_valid = hmac.compare_digest(signature, expected_signature)

    return JSONResponse(
        content={
            "valid": is_valid,
            "message": "Signature verified" if is_valid else "Signature mismatch",
        }
    )

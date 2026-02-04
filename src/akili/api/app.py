"""
FastAPI app: ingest documents, submit queries, return coordinate-grounded answers or REFUSE.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from akili.ingest.pipeline import ingest_document
from akili.store import Store
from akili.verify import Refuse, verify_and_answer

app = FastAPI(
    title="Akili",
    description="The Reasoning Control Plane for Mission-Critical Engineering — deterministic verification for technical documentation",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Default store (SQLite in cwd); override via dependency if needed
_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        db_path = os.environ.get("AKILI_DB_PATH", "akili.db")
        _store = Store(Path(db_path))
    return _store


class QueryRequest(BaseModel):
    """Request body for POST /query."""

    doc_id: str = Field(..., description="Document id from ingest")
    question: str = Field(..., description="Question to answer from canonical facts")


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)) -> JSONResponse:
    """
    Upload a PDF; run ingestion pipeline; persist canonical objects.
    Returns doc_id and counts of units, bijections, grids.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    store = get_store()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        doc_id, canonical = ingest_document(tmp_path, store=store)
    finally:
        tmp_path.unlink(missing_ok=True)
    units = [o for o in canonical if o.__class__.__name__ == "Unit"]
    bijections = [o for o in canonical if o.__class__.__name__ == "Bijection"]
    grids = [o for o in canonical if o.__class__.__name__ == "Grid"]
    page_count = (max((getattr(o, "page", 0) for o in canonical), default=-1) + 1) if canonical else 0
    return JSONResponse(
        content={
            "doc_id": doc_id,
            "filename": file.filename or "upload.pdf",
            "page_count": page_count,
            "units_count": len(units),
            "bijections_count": len(bijections),
            "grids_count": len(grids),
        }
    )


@app.post("/query")
async def query(req: QueryRequest) -> JSONResponse:
    """
    Submit a question for a document. Returns coordinate-grounded answer + proof, or REFUSE.
    """
    store = get_store()
    units = store.get_units_by_doc(req.doc_id)
    bijections = store.get_bijections_by_doc(req.doc_id)
    grids = store.get_grids_by_doc(req.doc_id)
    result = verify_and_answer(req.question, units, bijections, grids)
    if isinstance(result, Refuse):
        return JSONResponse(content=result.model_dump())
    return JSONResponse(content=result.model_dump())


@app.get("/documents")
async def list_documents() -> JSONResponse:
    """List ingested documents with canonical object counts."""
    store = get_store()
    docs = store.list_documents()
    return JSONResponse(content={"documents": docs})


@app.get("/documents/{doc_id}/canonical")
async def get_canonical(doc_id: str) -> JSONResponse:
    """Return canonical objects (units, bijections, grids) for a document."""
    store = get_store()
    units = store.get_units_by_doc(doc_id)
    bijections = store.get_bijections_by_doc(doc_id)
    grids = store.get_grids_by_doc(doc_id)

    def ser_unit(u: object) -> dict:
        u = u  # type: ignore[assignment]
        return {
            "type": "unit",
            "id": getattr(u, "id", None),
            "label": getattr(u, "label", None),
            "value": getattr(u, "value", None),
            "unit_of_measure": getattr(u, "unit_of_measure", None),
            "origin": {"x": getattr(getattr(u, "origin", None), "x", 0), "y": getattr(getattr(u, "origin", None), "y", 0)},
            "page": getattr(u, "page", 0),
        }

    def ser_bijection(b: object) -> dict:
        return {
            "type": "bijection",
            "id": getattr(b, "id", None),
            "mapping": getattr(b, "mapping", {}),
            "origin": {"x": getattr(getattr(b, "origin", None), "x", 0), "y": getattr(getattr(b, "origin", None), "y", 0)},
            "page": getattr(b, "page", 0),
        }

    def ser_grid(g: object) -> dict:
        return {
            "type": "grid",
            "id": getattr(g, "id", None),
            "rows": getattr(g, "rows", 0),
            "cols": getattr(g, "cols", 0),
            "cells_count": len(getattr(g, "cells", [])),
            "origin": {"x": getattr(getattr(g, "origin", None), "x", 0), "y": getattr(getattr(g, "origin", None), "y", 0)},
            "page": getattr(g, "page", 0),
        }

    return JSONResponse(
        content={
            "doc_id": doc_id,
            "units": [ser_unit(u) for u in units],
            "bijections": [ser_bijection(b) for b in bijections],
            "grids": [ser_grid(g) for g in grids],
        }
    )


@app.get("/health")
async def health() -> dict:
    """Health check."""
    return {"status": "ok"}

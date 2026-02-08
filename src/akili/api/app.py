"""
FastAPI app: ingest documents, submit queries, return coordinate-grounded answers or REFUSE.
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import re
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from akili.api.auth import get_current_user
from akili.canonical import Bijection, Grid, Unit
from akili.ingest.gemini_format import format_answer
from akili.ingest.pipeline import ingest_document
from akili.store import Store
from akili.verify import AnswerWithProof, Refuse, verify_and_answer

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]


def _cors_origins() -> list[str]:
    raw = os.environ.get("AKILI_CORS_ORIGINS", "").strip()
    if not raw:
        return _DEFAULT_CORS_ORIGINS
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(
    title="Akili",
    description=(
        "The Reasoning Control Plane for Mission-Critical Engineering — "
        "deterministic verification for technical documentation"
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _log_env() -> None:
    import logging

    key = os.environ.get("GOOGLE_API_KEY")
    if key and key.strip():
        logging.getLogger("akili").info("GOOGLE_API_KEY is set (ingest will call Gemini)")
    else:
        logging.getLogger("akili").warning(
            "GOOGLE_API_KEY is missing or empty — ingest will return 500 until set in .env"
        )


@app.get("/status")
def status() -> JSONResponse:
    """
    Check API and env without running ingest. Call this to verify GOOGLE_API_KEY and DB.
    No restart needed — hit GET http://localhost:8000/status (or via proxy /api/status).
    """
    key = os.environ.get("GOOGLE_API_KEY")
    key_set = bool(key and key.strip())
    db_path = os.environ.get("AKILI_DB_PATH", "akili.db")
    db_exists = Path(db_path).parent.exists() if db_path else False
    return JSONResponse(
        content={
            "ok": True,
            "GOOGLE_API_KEY_set": key_set,
            "message": (
                "GOOGLE_API_KEY is set; ingest can call Gemini."
                if key_set
                else "GOOGLE_API_KEY is missing or empty. Set it in .env and ensure the API container uses env_file: .env"  # noqa: E501
            ),
            "AKILI_DB_PATH": db_path,
            "db_dir_exists": db_exists,
        }
    )


# Default store (SQLite in cwd); override via dependency if needed
_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        db_path = os.environ.get("AKILI_DB_PATH", "akili.db")
        _store = Store(Path(db_path))
    return _store


def _docs_dir() -> Path:
    """Directory where ingested PDFs are stored (next to DB)."""
    db_path = os.environ.get("AKILI_DB_PATH", "akili.db")
    return Path(db_path).resolve().parent / "docs"


def _validate_doc_id(doc_id: str) -> None:
    """Raise 400 if doc_id is invalid (path traversal)."""
    if not doc_id or not re.match(r"^[a-zA-Z0-9_-]+$", doc_id):
        raise HTTPException(status_code=400, detail="Invalid doc_id")


class QueryRequest(BaseModel):
    """Request body for POST /query."""

    doc_id: str = Field(..., description="Document id from ingest")
    question: str = Field(..., description="Question to answer from canonical facts")
    include_formatted_answer: bool = Field(
        False,
        description="If true, request 1-sentence phrasing from Gemini (best-effort).",
    )


@app.post("/ingest")
async def ingest(
    _user: dict[str, Any] | None = Depends(get_current_user),
    file: UploadFile = File(...),
) -> JSONResponse:
    """
    Upload a PDF; run ingestion pipeline; persist canonical objects.
    Returns doc_id and counts of units, bijections, grids.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    max_bytes = int(os.environ.get("AKILI_MAX_UPLOAD_BYTES", "104857600"))  # default 100 MB
    if max_bytes > 0 and len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large (max {max_bytes} bytes). Set AKILI_MAX_UPLOAD_BYTES to override."
            ),
        )
    store = get_store()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        doc_id, canonical, total_pages, pages_failed = ingest_document(tmp_path, store=store)
        _validate_doc_id(doc_id)
        docs_dir = _docs_dir()
        docs_dir.mkdir(parents=True, exist_ok=True)
        dest = docs_dir / f"{doc_id}.pdf"
        shutil.copy2(tmp_path, dest)
    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e)
        # Gemini/Vertex rate limit (429) — return 429 so the UI can show a clear message
        if "429" in err_msg or "Resource exhausted" in err_msg or "ResourceExhausted" in err_msg:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Gemini rate limit (429). Please wait a minute and try again. "
                    "See https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429"
                ),
            ) from e
        raise HTTPException(status_code=500, detail=err_msg) from e
    finally:
        tmp_path.unlink(missing_ok=True)
    units = [o for o in canonical if isinstance(o, Unit)]
    bijections = [o for o in canonical if isinstance(o, Bijection)]
    grids = [o for o in canonical if isinstance(o, Grid)]
    content = {
        "doc_id": doc_id,
        "filename": file.filename or "upload.pdf",
        "page_count": total_pages,
        "units_count": len(units),
        "bijections_count": len(bijections),
        "grids_count": len(grids),
        "pages_failed": pages_failed,
    }
    if len(units) == 0 and len(bijections) == 0 and len(grids) == 0:
        content["extraction_warning"] = (
            "No facts extracted from this document. "
            "Check GOOGLE_API_KEY in .env, Gemini model (AKILI_GEMINI_MODEL), and server logs for errors."
        )
    elif pages_failed > 0:
        content["extraction_note"] = (
            f"Extracted from {total_pages - pages_failed} of {total_pages} pages. "
            f"{pages_failed} page(s) were skipped (often due to rate limits). "
            "Try increasing AKILI_GEMINI_PAGE_DELAY_SECONDS in .env (e.g. 4) and re-upload."
        )
    return JSONResponse(content=content)


def _run_ingest_with_progress(
    tmp_path: Path,
    store: Store,
    progress_queue: queue.Queue,
    filename: str,
    docs_dir: Path,
) -> None:
    """Run ingest in a thread; put progress events into queue. Adds filename to final 'done'."""
    result_holder: list[dict] = []

    def callback(msg: dict) -> None:
        if msg.get("phase") != "done":
            progress_queue.put(msg)
        else:
            result_holder.append(msg)

    try:
        doc_id, canonical, total_pages, pages_failed = ingest_document(
            tmp_path, store=store, progress_callback=callback
        )
        _validate_doc_id(doc_id)
        docs_dir.mkdir(parents=True, exist_ok=True)
        dest = docs_dir / f"{doc_id}.pdf"
        shutil.copy2(tmp_path, dest)
        done = result_holder[0] if result_holder else {}
        done["filename"] = filename or "upload.pdf"
        progress_queue.put(done)
    except Exception as e:
        progress_queue.put({"phase": "error", "message": str(e)})


@app.post("/ingest/stream")
async def ingest_stream(
    _user: dict[str, Any] | None = Depends(get_current_user),
    file: UploadFile = File(...),
) -> StreamingResponse:
    """
    Upload a PDF and run ingestion with server-sent progress.
    Streams progress events: rendering, extracting (page/total), canonicalizing, storing, done.
    Final event is done with doc_id, filename, counts. On error, event has phase 'error'.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    max_bytes = int(os.environ.get("AKILI_MAX_UPLOAD_BYTES", "104857600"))
    if max_bytes > 0 and len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {max_bytes} bytes). Set AKILI_MAX_UPLOAD_BYTES to override.",
        )
    store = get_store()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    progress_queue: queue.Queue = queue.Queue()
    docs_dir = _docs_dir()
    filename = file.filename or "upload.pdf"
    thread = threading.Thread(
        target=_run_ingest_with_progress,
        args=(tmp_path, store, progress_queue, filename, docs_dir),
    )
    thread.start()

    async def cleanup_and_stream() -> Any:
        try:
            loop = asyncio.get_event_loop()
            async for chunk in _stream_sse(progress_queue, loop):
                yield chunk
        finally:
            tmp_path.unlink(missing_ok=True)
            thread.join(timeout=1.0)

    async def _stream_sse(q: queue.Queue, loop: asyncio.AbstractEventLoop) -> Any:
        while True:
            def get_msg() -> dict | None:
                try:
                    return q.get(timeout=0.5)
                except queue.Empty:
                    return None
            msg = await loop.run_in_executor(None, get_msg)
            if msg is None:
                continue
            phase = msg.get("phase")
            yield f"data: {json.dumps(msg)}\n\n"
            if phase in ("done", "error"):
                break

    return StreamingResponse(
        cleanup_and_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Thread pool for sync Gemini format call (short timeout; never blocks verified answer)
_FORMAT_EXECUTOR: ThreadPoolExecutor | None = None
_FORMAT_TIMEOUT = float(os.environ.get("AKILI_FORMAT_TIMEOUT_SEC", "2.5"))


def _get_format_executor() -> ThreadPoolExecutor:
    global _FORMAT_EXECUTOR
    if _FORMAT_EXECUTOR is None:
        _FORMAT_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="akili_format")
    return _FORMAT_EXECUTOR


def _proof_to_coordinates(proof: list[Any]) -> str:
    """Build a short coordinates summary for the format prompt."""
    if not proof:
        return "no coordinates"
    parts = []
    for p in proof:
        x = getattr(p, "x", 0)
        y = getattr(p, "y", 0)
        page = getattr(p, "page", 0)
        parts.append(f"page {page} (x={x:.2f}, y={y:.2f})")
    return "; ".join(parts)


@app.post("/query")
async def query(
    req: QueryRequest,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    Submit a question for a document. Returns coordinate-grounded answer + proof, or REFUSE.
    If include_formatted_answer is true and the answer is verified, also requests a 1-sentence
    natural-language phrasing from Gemini (best-effort; response still includes raw answer).
    """
    store = get_store()
    units = store.get_units_by_doc(req.doc_id)
    bijections = store.get_bijections_by_doc(req.doc_id)
    grids = store.get_grids_by_doc(req.doc_id)
    result = verify_and_answer(req.question, units, bijections, grids)
    if isinstance(result, Refuse):
        return JSONResponse(content=result.model_dump())
    # AnswerWithProof: always return answer + proof; optionally add formatted_answer
    content: dict[str, Any] = result.model_dump()
    if req.include_formatted_answer and isinstance(result, AnswerWithProof):
        coordinates = _proof_to_coordinates(result.proof)
        loop = asyncio.get_event_loop()
        try:
            formatted = await asyncio.wait_for(
                loop.run_in_executor(
                    _get_format_executor(),
                    lambda: format_answer(req.question, result.answer, coordinates),
                ),
                timeout=_FORMAT_TIMEOUT,
            )
            content["formatted_answer"] = formatted
        except (asyncio.TimeoutError, Exception):
            content["formatted_answer"] = None
    return JSONResponse(content=content)


@app.get("/documents")
async def list_documents(
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """List ingested documents with canonical object counts."""
    store = get_store()
    docs = store.list_documents()
    return JSONResponse(content={"documents": docs})


@app.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """Delete an ingested document (canonical store and PDF file)."""
    _validate_doc_id(doc_id)
    store = get_store()
    store.delete_document(doc_id)
    dest = _docs_dir() / f"{doc_id}.pdf"
    if dest.is_file():
        dest.unlink()
    return JSONResponse(content={"doc_id": doc_id, "deleted": True})


@app.get("/documents/{doc_id}/file")
async def get_document_file(
    doc_id: str,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> FileResponse:
    """Return the ingested PDF file for a document (for viewer / Show on document)."""
    _validate_doc_id(doc_id)
    dest = _docs_dir() / f"{doc_id}.pdf"
    if not dest.is_file():
        raise HTTPException(
            status_code=404,
            detail="Document file not found (ingested before PDF storage was added)",
        )
    return FileResponse(dest, media_type="application/pdf", filename=f"{doc_id}.pdf")


@app.get("/documents/{doc_id}/canonical")
async def get_canonical(
    doc_id: str,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
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
            "origin": {
                "x": getattr(getattr(u, "origin", None), "x", 0),
                "y": getattr(getattr(u, "origin", None), "y", 0),
            },
            "page": getattr(u, "page", 0),
        }

    def ser_bijection(b: object) -> dict:
        return {
            "type": "bijection",
            "id": getattr(b, "id", None),
            "mapping": getattr(b, "mapping", {}),
            "origin": {
                "x": getattr(getattr(b, "origin", None), "x", 0),
                "y": getattr(getattr(b, "origin", None), "y", 0),
            },
            "page": getattr(b, "page", 0),
        }

    def ser_grid(g: object) -> dict:
        return {
            "type": "grid",
            "id": getattr(g, "id", None),
            "rows": getattr(g, "rows", 0),
            "cols": getattr(g, "cols", 0),
            "cells_count": len(getattr(g, "cells", [])),
            "origin": {
                "x": getattr(getattr(g, "origin", None), "x", 0),
                "y": getattr(getattr(g, "origin", None), "y", 0),
            },
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

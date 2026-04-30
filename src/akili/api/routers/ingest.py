"""
Document ingestion endpoints: upload PDF, streaming ingest.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from akili import config
from akili.api.auth import get_current_user
from akili.api.deps import docs_dir, get_store, get_usage_store, is_debug, validate_doc_id
from akili.canonical import Bijection, Grid, Unit
from akili.ingest.pipeline import ingest_document
from akili.store import Store
from akili.store.usage import UsageStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


def _get_limiter():
    from akili.api.app import limiter
    return limiter


@router.post("/ingest")
async def ingest(
    request: Request,
    _user: dict[str, Any] | None = Depends(get_current_user),
    file: UploadFile = File(...),
) -> JSONResponse:
    """
    Upload a PDF; run ingestion pipeline; persist canonical objects.
    Returns doc_id and counts of units, bijections, grids.
    """
    user_id = (_user or {}).get("uid", request.client.host if request.client else "anonymous")
    usage = get_usage_store()
    allowed, used, limit = usage.check_limit(user_id, "ingest")
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Free tier limit reached: {used}/{limit} documents. Contact us to upgrade.",
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if not content[:5].startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF (bad magic bytes)")
    max_bytes = config.MAX_UPLOAD_BYTES
    if max_bytes > 0 and len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large (max {max_bytes} bytes). "
                "Set AKILI_MAX_UPLOAD_BYTES to override."
            ),
        )
    store = get_store()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        doc_id, canonical, total_pages, pages_failed = ingest_document(tmp_path, store=store, uploaded_by=user_id)
        validate_doc_id(doc_id)
        dd = docs_dir()
        dd.mkdir(parents=True, exist_ok=True)
        dest = dd / f"{doc_id}.pdf"
        shutil.copy2(tmp_path, dest)
    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e)
        logger.exception("Ingest failed: %s", err_msg)
        if "429" in err_msg or "Resource exhausted" in err_msg or "ResourceExhausted" in err_msg:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Gemini rate limit (429). Please wait a minute and try again. "
                    "See https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429"
                ),
            ) from e
        detail = "Internal server error"
        if is_debug():
            detail = f"Ingest error: {type(e).__name__}"
        raise HTTPException(status_code=500, detail=detail) from e
    finally:
        tmp_path.unlink(missing_ok=True)
    units = [o for o in canonical if isinstance(o, Unit)]
    bijections = [o for o in canonical if isinstance(o, Bijection)]
    grids = [o for o in canonical if isinstance(o, Grid)]
    resp: dict[str, Any] = {
        "doc_id": doc_id,
        "filename": file.filename or "upload.pdf",
        "page_count": total_pages,
        "units_count": len(units),
        "bijections_count": len(bijections),
        "grids_count": len(grids),
        "pages_failed": pages_failed,
    }
    if len(units) == 0 and len(bijections) == 0 and len(grids) == 0:
        resp["extraction_warning"] = (
            "No facts extracted from this document. "
            "Check GOOGLE_API_KEY in .env, Gemini model (AKILI_GEMINI_MODEL), "
            "and server logs for errors."
        )
    elif pages_failed > 0:
        resp["extraction_note"] = (
            f"Extracted from {total_pages - pages_failed} of {total_pages} pages. "
            f"{pages_failed} page(s) were skipped (often due to rate limits). "
            "Try increasing AKILI_GEMINI_PAGE_DELAY_SECONDS in .env (e.g. 4) and re-upload."
        )
    usage.record(user_id, "ingest")
    return JSONResponse(content=resp)


def _run_ingest_with_progress(
    tmp_path: Path,
    store: Store,
    progress_queue: queue.Queue,
    filename: str,
    dd: Path,
    usage_store: UsageStore | None = None,
    user_id: str | None = None,
    uploaded_by: str | None = None,
) -> None:
    """Run ingest in a thread; put progress events into queue."""
    result_holder: list[dict] = []

    def callback(msg: dict) -> None:
        if msg.get("phase") != "done":
            progress_queue.put(msg)
        else:
            result_holder.append(msg)

    try:
        doc_id, canonical, total_pages, pages_failed = ingest_document(
            tmp_path, store=store, progress_callback=callback, uploaded_by=uploaded_by
        )
        validate_doc_id(doc_id)
        dd.mkdir(parents=True, exist_ok=True)
        dest = dd / f"{doc_id}.pdf"
        shutil.copy2(tmp_path, dest)
        if usage_store and user_id:
            usage_store.record(user_id, "ingest")
        done = result_holder[0] if result_holder else {}
        done["filename"] = filename or "upload.pdf"
        progress_queue.put(done)
    except Exception as e:
        logger.exception("Ingest stream failed: %s", e)
        msg = str(e) if is_debug() else "An error occurred during ingest."
        progress_queue.put({"phase": "error", "message": msg})


@router.post("/ingest/stream")
async def ingest_stream(
    request: Request,
    _user: dict[str, Any] | None = Depends(get_current_user),
    file: UploadFile = File(...),
) -> StreamingResponse:
    """
    Upload a PDF and run ingestion with server-sent progress.
    """
    user_id = (_user or {}).get("uid", request.client.host if request.client else "anonymous")
    usage = get_usage_store()
    allowed, used, limit = usage.check_limit(user_id, "ingest")
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Free tier limit reached: {used}/{limit} documents. Contact us to upgrade.",
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if not content[:5].startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF (bad magic bytes)")
    max_bytes = config.MAX_UPLOAD_BYTES
    if max_bytes > 0 and len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large (max {max_bytes} bytes). "
                "Set AKILI_MAX_UPLOAD_BYTES to override."
            ),
        )
    store = get_store()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    progress_queue: queue.Queue = queue.Queue()
    dd = docs_dir()
    filename = file.filename or "upload.pdf"
    thread = threading.Thread(
        target=_run_ingest_with_progress,
        args=(tmp_path, store, progress_queue, filename, dd, usage, user_id, user_id),
    )
    thread.start()

    async def cleanup_and_stream() -> Any:
        try:
            loop = asyncio.get_event_loop()
            async for chunk in _stream_sse(progress_queue, loop):
                yield chunk
        finally:
            thread.join(timeout=30.0)
            tmp_path.unlink(missing_ok=True)

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

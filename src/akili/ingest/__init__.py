"""
Ingestion pipeline: PDF → chunks with coordinates → Gemini → canonicalize → store.

Rejects ambiguous or low-confidence extractions at the source.
"""

# Pipeline entrypoint to be implemented
# from akili.ingest.pipeline import ingest_document

__all__: list[str] = []

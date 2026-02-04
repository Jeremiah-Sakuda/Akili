"""
FastAPI app: ingest documents, submit queries, return coordinate-grounded answers or REFUSE.
"""

from akili.api.app import app

__all__ = ["app"]

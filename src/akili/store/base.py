"""
Abstract base class for the canonical object store.

Concrete implementations: SQLiteStore (repository.py), PostgresStore (postgres.py).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from akili.canonical import Bijection, ConditionalUnit, Grid, Range, Unit


class BaseStore(ABC):
    """Interface that all store backends must implement."""

    @abstractmethod
    def add_document(self, doc_id: str, filename: str | None = None, page_count: int = 0) -> None:
        ...

    @abstractmethod
    def store_canonical(
        self,
        doc_id: str,
        filename: str | None,
        page_count: int,
        units: list[Unit],
        bijections: list[Bijection],
        grids: list[Grid],
        ranges: list[Range] | None = None,
        conditional_units: list[ConditionalUnit] | None = None,
    ) -> None:
        ...

    @abstractmethod
    def get_units_by_doc(self, doc_id: str) -> list[Unit]:
        ...

    @abstractmethod
    def get_bijections_by_doc(self, doc_id: str) -> list[Bijection]:
        ...

    @abstractmethod
    def get_grids_by_doc(self, doc_id: str) -> list[Grid]:
        ...

    @abstractmethod
    def get_ranges_by_doc(self, doc_id: str) -> list[Range]:
        ...

    @abstractmethod
    def get_conditional_units_by_doc(self, doc_id: str) -> list[ConditionalUnit]:
        ...

    @abstractmethod
    def get_all_canonical_by_doc(
        self, doc_id: str
    ) -> list[Unit | Bijection | Grid | Range | ConditionalUnit]:
        ...

    @abstractmethod
    def delete_document(self, doc_id: str) -> None:
        ...

    @abstractmethod
    def list_documents(self) -> list[dict[str, Any]]:
        ...

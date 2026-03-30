"""
Migration helpers: SQLite -> PostgreSQL data transfer.

Usage:
    python -m akili.store.migrate --sqlite akili.db --pg-url postgresql://user:pass@host/akili
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logger = logging.getLogger(__name__)


def migrate_sqlite_to_postgres(sqlite_path: str, pg_url: str, org_id: str = "default") -> dict:
    """Copy all data from a SQLite store into a PostgreSQL store.

    Returns a summary dict with counts of migrated objects.
    """
    from akili.store.repository import Store as SQLiteStore
    from akili.store.postgres import PostgresStore

    src = SQLiteStore(db_path=sqlite_path)
    dst = PostgresStore(dsn=pg_url, org_id=org_id)

    docs = src.list_documents()
    summary = {"documents": 0, "units": 0, "bijections": 0, "grids": 0, "ranges": 0, "conditional_units": 0}

    for doc_info in docs:
        doc_id = doc_info["doc_id"]
        units = src.get_units_by_doc(doc_id)
        bijections = src.get_bijections_by_doc(doc_id)
        grids = src.get_grids_by_doc(doc_id)
        ranges = src.get_ranges_by_doc(doc_id)
        cunits = src.get_conditional_units_by_doc(doc_id)

        dst.store_canonical(
            doc_id=doc_id,
            filename=doc_info.get("filename"),
            page_count=doc_info.get("page_count", 0),
            units=units,
            bijections=bijections,
            grids=grids,
            ranges=ranges,
            conditional_units=cunits,
        )

        summary["documents"] += 1
        summary["units"] += len(units)
        summary["bijections"] += len(bijections)
        summary["grids"] += len(grids)
        summary["ranges"] += len(ranges)
        summary["conditional_units"] += len(cunits)

        logger.info("Migrated doc %s: %d units, %d bijections, %d grids, %d ranges, %d cunits",
                     doc_id, len(units), len(bijections), len(grids), len(ranges), len(cunits))

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Akili data from SQLite to PostgreSQL")
    parser.add_argument("--sqlite", required=True, help="Path to SQLite database file")
    parser.add_argument("--pg-url", required=True, help="PostgreSQL connection URL")
    parser.add_argument("--org-id", default="default", help="Organization ID for multi-tenancy")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    summary = migrate_sqlite_to_postgres(args.sqlite, args.pg_url, args.org_id)
    print(f"\nMigration complete: {json.dumps(summary, indent=2)}")


if __name__ == "__main__":
    main()

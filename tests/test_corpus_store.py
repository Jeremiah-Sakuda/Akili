"""Public corpus methods on the default SQLite store (FR-CORP)."""

from __future__ import annotations


def test_store_and_get_corpus_entry(tmp_store):
    data = {"units": [{"id": "u1"}], "bijections": [], "grids": []}
    tmp_store.store_corpus_entry("hash123", "NE555", "NE555 Timer", "http://x/ne555.pdf", data)

    by_hash = tmp_store.get_corpus_entry("hash123")
    assert by_hash is not None
    assert by_hash["mpn"] == "NE555"
    assert by_hash["canonical_data"]["units"][0]["id"] == "u1"

    by_mpn = tmp_store.get_corpus_by_mpn("NE555")
    assert by_mpn is not None and by_mpn["content_hash"] == "hash123"

    assert tmp_store.get_corpus_entry("missing") is None
    assert tmp_store.get_corpus_by_mpn("missing") is None


def test_list_corpus(tmp_store):
    tmp_store.store_corpus_entry("h1", "LM7805", "LM7805", None, {})
    tmp_store.store_corpus_entry("h2", "ATmega328P", "ATmega328P", None, {})
    entries = tmp_store.list_corpus()
    mpns = {e["mpn"] for e in entries}
    assert mpns == {"LM7805", "ATmega328P"}
    # list_corpus returns metadata only (no canonical_data blob).
    assert all("canonical_data" not in e for e in entries)


def test_store_corpus_entry_upserts(tmp_store):
    tmp_store.store_corpus_entry("h1", "LM7805", "old name", None, {})
    tmp_store.store_corpus_entry("h1", "LM7805", "new name", None, {})
    entry = tmp_store.get_corpus_entry("h1")
    assert entry["chip_name"] == "new name"
    assert len(tmp_store.list_corpus()) == 1

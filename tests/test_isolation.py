"""Per-user document isolation: one user must not see or own another user's documents."""

from __future__ import annotations

from akili.canonical import Point, Unit


def _unit(uid: str, doc_id: str) -> Unit:
    return Unit(
        id=uid,
        label="VCC",
        value=5.0,
        unit_of_measure="V",
        origin=Point(x=0.1, y=0.1),
        doc_id=doc_id,
        page=0,
    )


def test_list_documents_scoped_by_owner(tmp_store):
    tmp_store.store_canonical(
        "docA", "a.pdf", 1, [_unit("a1", "docA")], [], [], uploaded_by="userA"
    )
    tmp_store.store_canonical(
        "docB", "b.pdf", 1, [_unit("b1", "docB")], [], [], uploaded_by="userB"
    )

    a_docs = {d["doc_id"] for d in tmp_store.list_documents(uploaded_by="userA")}
    b_docs = {d["doc_id"] for d in tmp_store.list_documents(uploaded_by="userB")}
    all_docs = {d["doc_id"] for d in tmp_store.list_documents()}

    assert a_docs == {"docA"}
    assert b_docs == {"docB"}
    assert all_docs == {"docA", "docB"}  # unscoped (admin/dev) still sees both


def test_get_document_owner(tmp_store):
    tmp_store.store_canonical(
        "docA", "a.pdf", 1, [_unit("a1", "docA")], [], [], uploaded_by="userA"
    )
    assert tmp_store.get_document_owner("docA") == "userA"
    assert tmp_store.get_document_owner("nonexistent") is None

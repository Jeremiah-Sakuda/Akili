"""Tests for verification layer (proof + REFUSE)."""

from akili.canonical import Bijection, Grid, Point, Unit
from akili.canonical.models import GridCell
from akili.verify import Refuse, verify_and_answer


def test_refuse_when_empty():
    result = verify_and_answer("What is pin 5?", [], [], [])
    assert isinstance(result, Refuse)
    assert result.status == "refuse"
    assert "canonical" in result.reason.lower()


def test_pin_lookup_via_bijection():
    b = Bijection(
        id="pinout",
        left_set=["5", "6"],
        right_set=["VCC", "GND"],
        mapping={"5": "VCC", "6": "GND"},
        origin=Point(x=0.5, y=0.3),
        doc_id="doc1",
        page=0,
    )
    result = verify_and_answer("What is pin 5?", [], [b], [])
    assert result is not None
    assert not isinstance(result, Refuse)
    assert result.answer == "VCC"
    assert len(result.proof) == 1
    assert result.proof[0].x == 0.5 and result.proof[0].y == 0.3


def test_max_voltage_from_units():
    u1 = Unit(id="v1", value=3.3, unit_of_measure="V", origin=Point(x=0.1, y=0.1), doc_id="d", page=0)
    u2 = Unit(id="v2", value=5.0, unit_of_measure="V", origin=Point(x=0.2, y=0.2), doc_id="d", page=0)
    result = verify_and_answer("What is the maximum voltage?", [u1, u2], [], [])
    assert result is not None
    assert not isinstance(result, Refuse)
    assert "5" in result.answer
    assert len(result.proof) == 1


def test_pin_lookup_via_grid_returns_name():
    """Grid pin lookup returns pin name (same row, adjacent column), not the pin number."""
    g = Grid(
        id="pinout",
        rows=3,
        cols=2,
        cells=[
            GridCell(row=0, col=0, value="Pin", origin=Point(x=0.1, y=0.1)),
            GridCell(row=0, col=1, value="Name", origin=Point(x=0.5, y=0.1)),
            GridCell(row=1, col=0, value="5", origin=Point(x=0.1, y=0.2)),
            GridCell(row=1, col=1, value="VCC", origin=Point(x=0.5, y=0.2)),
            GridCell(row=2, col=0, value="6", origin=Point(x=0.1, y=0.3)),
            GridCell(row=2, col=1, value="GND", origin=Point(x=0.5, y=0.3)),
        ],
        origin=Point(x=0, y=0),
        doc_id="doc1",
        page=0,
    )
    result = verify_and_answer("What is pin 5?", [], [], [g])
    assert result is not None
    assert not isinstance(result, Refuse)
    assert result.answer == "VCC"
    assert len(result.proof) == 1
    assert result.proof[0].page == 0

"""Tests for canonical models (Unit, Bijection, Grid)."""

from akili.canonical import Bijection, Grid, Point, Unit


def test_point():
    p = Point(x=0.5, y=0.3)
    assert p.x == 0.5 and p.y == 0.3


def test_unit():
    u = Unit(
        id="pin_5",
        label="VCC",
        value=3.3,
        unit_of_measure="V",
        origin=Point(x=100, y=200),
        doc_id="doc1",
        page=0,
    )
    assert u.value == 3.3
    assert u.origin.x == 100


def test_bijection_get_right_left():
    b = Bijection(
        id="pinout",
        left_set=["VCC", "GND"],
        right_set=["5", "6"],
        mapping={"VCC": "5", "GND": "6"},
        origin=Point(x=0, y=0),
        doc_id="doc1",
        page=0,
    )
    assert b.get_right("VCC") == "5"
    assert b.get_left("6") == "GND"


def test_grid_get_cell():
    from akili.canonical.models import GridCell

    g = Grid(
        id="table1",
        rows=2,
        cols=2,
        cells=[
            GridCell(row=0, col=0, value="A"),
            GridCell(row=0, col=1, value="B"),
            GridCell(row=1, col=0, value="C"),
        ],
        origin=Point(x=0, y=0),
        doc_id="doc1",
        page=0,
    )
    assert g.get_cell(0, 0).value == "A"
    assert g.get_cell(1, 1) is None

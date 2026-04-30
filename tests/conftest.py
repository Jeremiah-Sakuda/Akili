"""Shared pytest fixtures for Akili tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from akili.canonical import Bijection, ConditionalUnit, Grid, Range, Unit
from akili.canonical.models import BBox, GridCell, Point
from akili.store.repository import Store


@pytest.fixture()
def tmp_store(tmp_path: Path) -> Store:
    """Return a Store backed by a temporary SQLite DB."""
    return Store(tmp_path / "test.db")


@pytest.fixture()
def sample_units() -> list[Unit]:
    """Realistic set of units covering electrical, thermal, timing, and physical specs."""
    return [
        Unit(id="u_vcc", label="VCC", value=3.3, unit_of_measure="V",
             context="supply voltage", origin=Point(x=0.1, y=0.1), doc_id="d1", page=0),
        Unit(id="u_vmax", label="VCC max", value=5.5, unit_of_measure="V",
             context="absolute maximum voltage", origin=Point(x=0.2, y=0.1), doc_id="d1", page=0),
        Unit(id="u_imax", label="ICC max", value=250, unit_of_measure="mA",
             context="maximum supply current", origin=Point(x=0.3, y=0.1), doc_id="d1", page=0),
        Unit(id="u_pd", label="PD", value=500, unit_of_measure="mW",
             context="power dissipation", origin=Point(x=0.4, y=0.1), doc_id="d1", page=0),
        Unit(id="u_esd_hbm", label="ESD HBM", value=2000, unit_of_measure="V",
             context="ESD Human Body Model", origin=Point(x=0.5, y=0.1), doc_id="d1", page=0),
        Unit(id="u_esd_cdm", label="ESD CDM", value=500, unit_of_measure="V",
             context="ESD Charged Device Model", origin=Point(x=0.5, y=0.15), doc_id="d1", page=0),
        Unit(id="u_ileak", label="IIL", value=1, unit_of_measure="µA",
             context="input leakage current", origin=Point(x=0.6, y=0.1), doc_id="d1", page=0),
        Unit(id="u_vth_l", label="VIL", value=0.8, unit_of_measure="V",
             context="input low threshold voltage", origin=Point(x=0.7, y=0.1), doc_id="d1", page=0),
        Unit(id="u_vth_h", label="VIH", value=2.0, unit_of_measure="V",
             context="input high threshold voltage", origin=Point(x=0.7, y=0.15), doc_id="d1", page=0),
        Unit(id="u_fmax", label="FCLK", value=100, unit_of_measure="MHz",
             context="maximum clock frequency", origin=Point(x=0.1, y=0.2), doc_id="d1", page=1),
        Unit(id="u_tpd", label="tPD", value=5.5, unit_of_measure="ns",
             context="propagation delay", origin=Point(x=0.2, y=0.2), doc_id="d1", page=1),
        Unit(id="u_tr", label="tR", value=2.0, unit_of_measure="ns",
             context="rise time", origin=Point(x=0.3, y=0.2), doc_id="d1", page=1),
        Unit(id="u_tf", label="tF", value=2.5, unit_of_measure="ns",
             context="fall time", origin=Point(x=0.3, y=0.25), doc_id="d1", page=1),
        Unit(id="u_tsu", label="tSU", value=3.0, unit_of_measure="ns",
             context="setup time", origin=Point(x=0.4, y=0.2), doc_id="d1", page=1),
        Unit(id="u_th", label="tH", value=1.0, unit_of_measure="ns",
             context="hold time", origin=Point(x=0.4, y=0.25), doc_id="d1", page=1),
        Unit(id="u_pkg", label="Package", value="TQFP-48", unit_of_measure=None,
             context="package type", origin=Point(x=0.1, y=0.3), doc_id="d1", page=2),
        Unit(id="u_dim_l", label="Length", value=7.0, unit_of_measure="mm",
             context="package dimension length", origin=Point(x=0.2, y=0.3), doc_id="d1", page=2),
        Unit(id="u_dim_w", label="Width", value=7.0, unit_of_measure="mm",
             context="package dimension width", origin=Point(x=0.3, y=0.3), doc_id="d1", page=2),
        Unit(id="u_theta_ja", label="θJA", value=45.0, unit_of_measure="°C/W",
             context="thermal resistance junction to ambient", origin=Point(x=0.4, y=0.3), doc_id="d1", page=2),
        Unit(id="u_weight", label="Weight", value=0.5, unit_of_measure="g",
             context="component weight", origin=Point(x=0.5, y=0.3), doc_id="d1", page=2),
        Unit(id="u_msl", label="MSL", value="3", unit_of_measure=None,
             context="moisture sensitivity level", origin=Point(x=0.6, y=0.3), doc_id="d1", page=2),
        Unit(id="u_top_min", label="TOPR min", value=-40, unit_of_measure="°C",
             context="operating temperature minimum", origin=Point(x=0.1, y=0.4), doc_id="d1", page=0),
        Unit(id="u_top_max", label="TOPR max", value=85, unit_of_measure="°C",
             context="operating temperature maximum", origin=Point(x=0.2, y=0.4), doc_id="d1", page=0),
        Unit(id="u_tsto_min", label="TSTO min", value=-65, unit_of_measure="°C",
             context="storage temperature minimum", origin=Point(x=0.3, y=0.4), doc_id="d1", page=0),
        Unit(id="u_tsto_max", label="TSTO max", value=150, unit_of_measure="°C",
             context="storage temperature maximum", origin=Point(x=0.4, y=0.4), doc_id="d1", page=0),
        Unit(id="u_tsolder", label="Tsolder", value=260, unit_of_measure="°C",
             context="reflow soldering temperature", origin=Point(x=0.5, y=0.4), doc_id="d1", page=0),
        Unit(id="u_absmax_i", label="Absolute max current", value=500, unit_of_measure="mA",
             context="absolute maximum current", origin=Point(x=0.6, y=0.4), doc_id="d1", page=0),
        Unit(id="u_partno", label="Part Number", value="AKILI-48Q", unit_of_measure=None,
             context="part number ordering information", origin=Point(x=0.1, y=0.5), doc_id="d1", page=0),
        Unit(id="u_desc", label="Description", value="High-speed 48-pin quad flat package logic IC",
             unit_of_measure=None, context="general description overview",
             origin=Point(x=0.2, y=0.5), doc_id="d1", page=0),
        Unit(id="u_vcc_min", label="VCC min", value=2.7, unit_of_measure="V",
             context="minimum supply voltage", origin=Point(x=0.1, y=0.05), doc_id="d1", page=0),
    ]


@pytest.fixture()
def sample_bijections() -> list[Bijection]:
    """Pinout bijection for testing pin lookup and pin count."""
    return [
        Bijection(
            id="pinout",
            left_set=["1", "2", "3", "4", "5", "6"],
            right_set=["VCC", "GND", "CLK", "DATA", "RST", "CS"],
            mapping={"1": "VCC", "2": "GND", "3": "CLK", "4": "DATA", "5": "RST", "6": "CS"},
            origin=Point(x=0.5, y=0.3),
            doc_id="d1",
            page=0,
        ),
    ]


@pytest.fixture()
def sample_grids() -> list[Grid]:
    """Grid with recommended operating conditions for table lookup tests."""
    return [
        Grid(
            id="rec_op",
            rows=4,
            cols=4,
            cells=[
                GridCell(row=0, col=0, value="Parameter", origin=Point(x=0.1, y=0.5)),
                GridCell(row=0, col=1, value="Min", origin=Point(x=0.3, y=0.5)),
                GridCell(row=0, col=2, value="Typ", origin=Point(x=0.5, y=0.5)),
                GridCell(row=0, col=3, value="Max", origin=Point(x=0.7, y=0.5)),
                GridCell(row=1, col=0, value="Supply Voltage", origin=Point(x=0.1, y=0.55)),
                GridCell(row=1, col=1, value="2.7", origin=Point(x=0.3, y=0.55)),
                GridCell(row=1, col=2, value="3.3", origin=Point(x=0.5, y=0.55)),
                GridCell(row=1, col=3, value="5.5", origin=Point(x=0.7, y=0.55)),
                GridCell(row=2, col=0, value="Operating Temperature", origin=Point(x=0.1, y=0.6)),
                GridCell(row=2, col=1, value="-40", origin=Point(x=0.3, y=0.6)),
                GridCell(row=2, col=2, value="25", origin=Point(x=0.5, y=0.6)),
                GridCell(row=2, col=3, value="85", origin=Point(x=0.7, y=0.6)),
                GridCell(row=3, col=0, value="Recommended Operating Conditions", origin=Point(x=0.1, y=0.65)),
                GridCell(row=3, col=1, value="See table", origin=Point(x=0.3, y=0.65)),
                GridCell(row=3, col=2, value="", origin=Point(x=0.5, y=0.65)),
                GridCell(row=3, col=3, value="", origin=Point(x=0.7, y=0.65)),
            ],
            origin=Point(x=0.1, y=0.5),
            doc_id="d1",
            page=0,
        ),
    ]

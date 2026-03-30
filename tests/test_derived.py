"""Tests for C1: Derived Query Engine (power, thermal, voltage margin, current budget)."""

from __future__ import annotations

import pytest

from akili.canonical import Unit
from akili.canonical.models import BBox, Point
from akili.verify.derived import (
    derive_current_budget,
    derive_power_dissipation,
    derive_thermal_check,
    derive_voltage_margin,
    try_derived_queries,
)
from akili.verify.models import AnswerWithProof, ProofChain


@pytest.fixture()
def power_units() -> list[Unit]:
    return [
        Unit(id="v1", label="VCC", value=3.3, unit_of_measure="V",
             context="supply voltage", origin=Point(x=0.1, y=0.1), doc_id="d1", page=0,
             bbox=BBox(x1=0.05, y1=0.05, x2=0.15, y2=0.15)),
        Unit(id="i1", label="ICC", value=50, unit_of_measure="mA",
             context="supply current", origin=Point(x=0.2, y=0.1), doc_id="d1", page=0,
             bbox=BBox(x1=0.15, y1=0.05, x2=0.25, y2=0.15)),
    ]


@pytest.fixture()
def thermal_units() -> list[Unit]:
    return [
        Unit(id="theta1", label="θJA", value=45.0, unit_of_measure="°C/W",
             context="thermal resistance junction to ambient", origin=Point(x=0.1, y=0.3), doc_id="d1", page=2),
        Unit(id="pd1", label="PD", value=200, unit_of_measure="mW",
             context="power dissipation", origin=Point(x=0.2, y=0.3), doc_id="d1", page=2),
        Unit(id="tjmax", label="TJ max", value=125, unit_of_measure="°C",
             context="maximum junction temperature", origin=Point(x=0.3, y=0.3), doc_id="d1", page=2),
    ]


@pytest.fixture()
def margin_units() -> list[Unit]:
    return [
        Unit(id="vop", label="VCC", value=3.3, unit_of_measure="V",
             context="supply voltage", origin=Point(x=0.1, y=0.1), doc_id="d1", page=0),
        Unit(id="vabs", label="Absolute max voltage", value=6.0, unit_of_measure="V",
             context="absolute maximum voltage", origin=Point(x=0.2, y=0.1), doc_id="d1", page=0),
    ]


@pytest.fixture()
def budget_units() -> list[Unit]:
    return [
        Unit(id="icc", label="ICC", value=100, unit_of_measure="mA",
             context="supply current", origin=Point(x=0.1, y=0.1), doc_id="d1", page=0),
        Unit(id="io1", label="IO1", value=20, unit_of_measure="mA",
             context="output current", origin=Point(x=0.2, y=0.1), doc_id="d1", page=0),
        Unit(id="io2", label="IO2", value=15, unit_of_measure="mA",
             context="output current", origin=Point(x=0.3, y=0.1), doc_id="d1", page=0),
    ]


class TestPowerDissipation:
    def test_basic_power(self, power_units: list[Unit]) -> None:
        result = derive_power_dissipation("What is the power dissipation?", power_units)
        assert result is not None
        assert isinstance(result, AnswerWithProof)
        assert "165" in result.answer  # 3.3V × 50mA = 165mW
        assert result.derivation is not None
        assert len(result.derivation.steps) == 3
        assert result.derivation.steps[2].formula == "P = V × I"

    def test_no_match_unrelated_question(self, power_units: list[Unit]) -> None:
        result = derive_power_dissipation("What is the pin count?", power_units)
        assert result is None

    def test_missing_current(self) -> None:
        units = [
            Unit(id="v1", label="VCC", value=3.3, unit_of_measure="V",
                 context="supply voltage", origin=Point(x=0.1, y=0.1), doc_id="d1", page=0),
        ]
        result = derive_power_dissipation("What is the power dissipation?", units)
        assert result is None

    def test_proof_chain_has_source_facts(self, power_units: list[Unit]) -> None:
        result = derive_power_dissipation("Calculate power dissipation", power_units)
        assert result is not None
        assert result.derivation is not None
        for step in result.derivation.steps:
            assert len(step.source_facts) > 0

    def test_derivation_type(self, power_units: list[Unit]) -> None:
        result = derive_power_dissipation("What is the power dissipation?", power_units)
        assert result is not None
        assert result.source_type == "derived"


class TestThermalCheck:
    def test_basic_thermal(self, thermal_units: list[Unit]) -> None:
        result = derive_thermal_check("Is the thermal check safe?", thermal_units)
        assert result is not None
        assert "T_junction" in result.answer
        # T_j = 25 + (0.2W × 45) = 25 + 9 = 34°C
        assert "34.0" in result.answer
        assert "SAFE" in result.answer

    def test_thermal_exceeds_limit(self) -> None:
        units = [
            Unit(id="theta1", label="θJA", value=200.0, unit_of_measure="°C/W",
                 context="thermal resistance junction to ambient", origin=Point(x=0.1, y=0.3), doc_id="d1", page=2),
            Unit(id="pd1", label="PD", value=1000, unit_of_measure="mW",
                 context="power dissipation", origin=Point(x=0.2, y=0.3), doc_id="d1", page=2),
            Unit(id="tjmax", label="TJ max", value=125, unit_of_measure="°C",
                 context="maximum junction temperature", origin=Point(x=0.3, y=0.3), doc_id="d1", page=2),
        ]
        result = derive_thermal_check("thermal check", units)
        assert result is not None
        # T_j = 25 + (1.0W × 200) = 225°C > 125°C
        assert "EXCEEDS" in result.answer

    def test_no_theta_returns_none(self) -> None:
        units = [
            Unit(id="pd1", label="PD", value=200, unit_of_measure="mW",
                 context="power dissipation", origin=Point(x=0.2, y=0.3), doc_id="d1", page=2),
        ]
        result = derive_thermal_check("thermal check", units)
        assert result is None

    def test_derives_power_from_vi(self) -> None:
        units = [
            Unit(id="theta1", label="θJA", value=45.0, unit_of_measure="°C/W",
                 context="thermal resistance junction to ambient", origin=Point(x=0.1, y=0.3), doc_id="d1", page=2),
            Unit(id="v1", label="VCC", value=3.3, unit_of_measure="V",
                 context="supply voltage", origin=Point(x=0.1, y=0.1), doc_id="d1", page=0),
            Unit(id="i1", label="ICC", value=50, unit_of_measure="mA",
                 context="supply current", origin=Point(x=0.2, y=0.1), doc_id="d1", page=0),
        ]
        result = derive_thermal_check("thermal margin check", units)
        assert result is not None
        assert "T_junction" in result.answer


class TestVoltageMargin:
    def test_basic_margin(self, margin_units: list[Unit]) -> None:
        result = derive_voltage_margin("What is the voltage margin?", margin_units)
        assert result is not None
        # margin = (6.0 - 3.3) / 6.0 × 100% = 45.0%
        assert "45.0%" in result.answer
        assert result.derivation is not None
        assert "margin" in result.derivation.formula_summary.lower()

    def test_no_match(self, margin_units: list[Unit]) -> None:
        result = derive_voltage_margin("What is the pin count?", margin_units)
        assert result is None

    def test_missing_abs_max(self) -> None:
        units = [
            Unit(id="vop", label="VCC", value=3.3, unit_of_measure="V",
                 context="supply voltage", origin=Point(x=0.1, y=0.1), doc_id="d1", page=0),
        ]
        result = derive_voltage_margin("voltage margin", units)
        assert result is None


class TestCurrentBudget:
    def test_basic_budget(self, budget_units: list[Unit]) -> None:
        result = derive_current_budget("What is the current budget?", budget_units)
        assert result is not None
        assert "100" in result.answer
        assert "remaining" in result.answer.lower()
        assert result.derivation is not None

    def test_no_supply(self) -> None:
        units = [
            Unit(id="io1", label="IO1", value=20, unit_of_measure="mA",
                 context="output current", origin=Point(x=0.2, y=0.1), doc_id="d1", page=0),
        ]
        result = derive_current_budget("current budget", units)
        assert result is None


class TestTryDerivedQueries:
    def test_dispatches_power(self, power_units: list[Unit]) -> None:
        result = try_derived_queries("power dissipation", power_units, [], [])
        assert result is not None
        assert "P = V × I" in result.answer or "165" in result.answer

    def test_dispatches_thermal(self, thermal_units: list[Unit]) -> None:
        result = try_derived_queries("thermal check", thermal_units, [], [])
        assert result is not None

    def test_dispatches_margin(self, margin_units: list[Unit]) -> None:
        result = try_derived_queries("voltage margin", margin_units, [], [])
        assert result is not None

    def test_none_for_unrelated(self) -> None:
        result = try_derived_queries("what is the weather?", [], [], [])
        assert result is None

    def test_proof_chain_structure(self, power_units: list[Unit]) -> None:
        result = try_derived_queries("compute power dissipation", power_units, [], [])
        assert result is not None
        assert result.derivation is not None
        assert isinstance(result.derivation, ProofChain)
        assert len(result.derivation.steps) > 0
        assert result.derivation.final_result
        assert result.derivation.formula_summary

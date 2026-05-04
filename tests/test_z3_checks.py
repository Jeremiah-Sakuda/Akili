"""Tests for B3: Z3 integration checks."""

from __future__ import annotations

import pytest

from akili.canonical import Range, Unit
from akili.canonical.models import Point


class TestZ3Available:
    def test_import(self):
        from akili.verify.z3_checks import Z3_AVAILABLE  # noqa: F401
        # Z3 may or may not be installed; test handles both cases


class TestUnitConversion:
    def test_to_base_known(self):
        from akili.verify.z3_checks import _to_base

        assert _to_base(4.2, "V") == (4.2, "V")
        val, base = _to_base(4200, "mV")
        assert abs(val - 4.2) < 1e-9
        assert base == "V"

    def test_to_base_unknown(self):
        from akili.verify.z3_checks import _to_base

        assert _to_base(1.0, "furlongs") is None

    def test_milliamp_conversion(self):
        from akili.verify.z3_checks import _to_base

        val, base = _to_base(250, "mA")
        assert abs(val - 0.25) < 1e-9
        assert base == "A"


class TestRangeConsistency:
    def test_valid_range(self):
        from akili.verify.z3_checks import _check_range_consistency

        r = Range(
            id="r1",
            label="VCC",
            min=2.7,
            typ=3.3,
            max=3.6,
            unit="V",
            origin=Point(x=0.5, y=0.3),
            doc_id="d1",
            page=0,
        )
        issues = _check_range_consistency([r])
        assert len(issues) == 0

    def test_invalid_range_min_gt_max(self):
        from akili.verify.z3_checks import _check_range_consistency, Z3_AVAILABLE

        if not Z3_AVAILABLE:
            pytest.skip("Z3 not installed")
        r = Range(
            id="r_bad",
            label="VCC",
            min=5.0,
            typ=3.3,
            max=2.7,
            unit="V",
            origin=Point(x=0.5, y=0.3),
            doc_id="d1",
            page=0,
        )
        issues = _check_range_consistency([r])
        assert len(issues) > 0
        assert issues[0].check_type == "range_consistency"
        assert issues[0].severity == "error"

    def test_range_with_only_min_max(self):
        from akili.verify.z3_checks import _check_range_consistency

        r = Range(
            id="r2",
            label="TOPR",
            min=-40,
            typ=None,
            max=85,
            unit="C",
            origin=Point(x=0.5, y=0.5),
            doc_id="d1",
            page=0,
        )
        issues = _check_range_consistency([r])
        assert len(issues) == 0


class TestContradictionDetection:
    def test_no_contradiction(self):
        from akili.verify.z3_checks import _check_contradictions

        units = [
            Unit(
                id="u1",
                label="VCC",
                value=3.3,
                unit_of_measure="V",
                context="supply voltage",
                origin=Point(x=0.1, y=0.1),
                doc_id="d1",
                page=0,
            ),
        ]
        issues = _check_contradictions(units)
        assert len(issues) == 0

    def test_contradiction_same_label_different_value(self):
        from akili.verify.z3_checks import _check_contradictions, Z3_AVAILABLE

        if not Z3_AVAILABLE:
            pytest.skip("Z3 not installed")
        units = [
            Unit(
                id="u1",
                label="VCC",
                value=5.5,
                unit_of_measure="V",
                context="maximum voltage",
                origin=Point(x=0.1, y=0.1),
                doc_id="d1",
                page=0,
            ),
            Unit(
                id="u2",
                label="VCC",
                value=5.0,
                unit_of_measure="V",
                context="maximum voltage",
                origin=Point(x=0.1, y=0.1),
                doc_id="d1",
                page=3,
            ),
        ]
        issues = _check_contradictions(units)
        assert len(issues) > 0
        assert issues[0].check_type == "contradiction"


class TestRunZ3Checks:
    def test_run_with_no_data(self):
        from akili.verify.z3_checks import run_z3_checks

        result = run_z3_checks()
        assert result.checks_run >= 0

    def test_run_with_valid_data(self):
        from akili.verify.z3_checks import run_z3_checks

        units = [
            Unit(
                id="u1",
                label="VCC",
                value=3.3,
                unit_of_measure="V",
                context="supply voltage",
                origin=Point(x=0.1, y=0.1),
                doc_id="d1",
                page=0,
            ),
        ]
        ranges = [
            Range(
                id="r1",
                label="VCC",
                min=2.7,
                typ=3.3,
                max=3.6,
                unit="V",
                origin=Point(x=0.5, y=0.3),
                doc_id="d1",
                page=0,
            ),
        ]
        result = run_z3_checks(units=units, ranges=ranges)
        assert not result.has_errors


# ---------------------------------------------------------------------------
# Cross-parameter Z3 checks (new in this release)
# ---------------------------------------------------------------------------


class TestPowerConstraint:
    """P_max should be >= V_max * I_max."""

    def test_power_constraint_violation(self):
        """V=5V, I=500mA => 2.5W but P_max=1W => should flag."""
        from akili.verify.z3_checks import _check_power_constraint, Z3_AVAILABLE

        if not Z3_AVAILABLE:
            pytest.skip("Z3 not installed")
        units = [
            Unit(
                id="v1",
                label="VCC",
                value=5.0,
                unit_of_measure="V",
                context="maximum voltage",
                origin=Point(x=0.1, y=0.1),
                doc_id="d1",
                page=0,
            ),
            Unit(
                id="i1",
                label="ICC",
                value=500,
                unit_of_measure="mA",
                context="maximum current",
                origin=Point(x=0.2, y=0.1),
                doc_id="d1",
                page=0,
            ),
            Unit(
                id="p1",
                label="PD",
                value=1.0,
                unit_of_measure="W",
                context="maximum power dissipation",
                origin=Point(x=0.3, y=0.1),
                doc_id="d1",
                page=0,
            ),
        ]
        issues = _check_power_constraint(units)
        assert len(issues) > 0
        assert issues[0].check_type == "power_constraint"
        assert issues[0].severity == "warning"

    def test_power_constraint_pass(self):
        """V=5V, I=200mA => 1W, P_max=2W => should pass."""
        from akili.verify.z3_checks import _check_power_constraint, Z3_AVAILABLE

        if not Z3_AVAILABLE:
            pytest.skip("Z3 not installed")
        units = [
            Unit(
                id="v1",
                label="VCC",
                value=5.0,
                unit_of_measure="V",
                context="maximum voltage",
                origin=Point(x=0.1, y=0.1),
                doc_id="d1",
                page=0,
            ),
            Unit(
                id="i1",
                label="ICC",
                value=200,
                unit_of_measure="mA",
                context="maximum current",
                origin=Point(x=0.2, y=0.1),
                doc_id="d1",
                page=0,
            ),
            Unit(
                id="p1",
                label="PD",
                value=2.0,
                unit_of_measure="W",
                context="maximum power dissipation",
                origin=Point(x=0.3, y=0.1),
                doc_id="d1",
                page=0,
            ),
        ]
        issues = _check_power_constraint(units)
        assert len(issues) == 0


class TestThermalViability:
    """T_j = T_ambient + P * theta_JA <= Tj_max."""

    def test_thermal_violation(self):
        """theta=100 C/W, P=2W, Tj_max=150 => Tj=225 > 150, should flag."""
        from akili.verify.z3_checks import _check_thermal_viability, Z3_AVAILABLE

        if not Z3_AVAILABLE:
            pytest.skip("Z3 not installed")
        units = [
            Unit(
                id="th1",
                label="θJA",
                value=100,
                unit_of_measure="°C/W",
                context="thermal resistance",
                origin=Point(x=0.1, y=0.1),
                doc_id="d1",
                page=0,
            ),
            Unit(
                id="p1",
                label="PD",
                value=2.0,
                unit_of_measure="W",
                context="power dissipation",
                origin=Point(x=0.2, y=0.1),
                doc_id="d1",
                page=0,
            ),
            Unit(
                id="tj1",
                label="TJ max",
                value=150,
                unit_of_measure="°C",
                context="maximum junction temperature",
                origin=Point(x=0.3, y=0.1),
                doc_id="d1",
                page=0,
            ),
        ]
        issues = _check_thermal_viability(units)
        assert len(issues) > 0
        assert issues[0].check_type == "thermal_viability"
        assert issues[0].severity == "error"

    def test_thermal_pass(self):
        """theta=30 C/W, P=1W, Tj_max=125 => Tj=55 < 125, should pass."""
        from akili.verify.z3_checks import _check_thermal_viability, Z3_AVAILABLE

        if not Z3_AVAILABLE:
            pytest.skip("Z3 not installed")
        units = [
            Unit(
                id="th1",
                label="θJA",
                value=30,
                unit_of_measure="°C/W",
                context="thermal resistance",
                origin=Point(x=0.1, y=0.1),
                doc_id="d1",
                page=0,
            ),
            Unit(
                id="p1",
                label="PD",
                value=1.0,
                unit_of_measure="W",
                context="power dissipation",
                origin=Point(x=0.2, y=0.1),
                doc_id="d1",
                page=0,
            ),
            Unit(
                id="tj1",
                label="TJ max",
                value=125,
                unit_of_measure="°C",
                context="maximum junction temperature",
                origin=Point(x=0.3, y=0.1),
                doc_id="d1",
                page=0,
            ),
        ]
        issues = _check_thermal_viability(units)
        assert len(issues) == 0

"""Tests for verification layer: all 30 rules + edge cases."""

import pytest

from akili.canonical import Bijection, Grid, Point, Unit
from akili.canonical.models import BBox, GridCell
from akili.verify import AnswerWithProof, Refuse, verify_and_answer


# ===================================================================
# Core behavior
# ===================================================================


class TestCoreBehavior:
    def test_refuse_when_empty(self):
        result = verify_and_answer("What is pin 5?", [], [], [])
        assert isinstance(result, Refuse)
        assert result.status == "refuse"

    def test_determinism(self, sample_units, sample_bijections, sample_grids):
        """Same inputs produce the same output every time."""
        r1 = verify_and_answer("What is the maximum voltage?", sample_units, sample_bijections, sample_grids)
        r2 = verify_and_answer("What is the maximum voltage?", sample_units, sample_bijections, sample_grids)
        assert r1 == r2


# ===================================================================
# 100: Pin lookup
# ===================================================================


class TestPinLookup:
    def test_pin_lookup_via_bijection(self, sample_bijections):
        result = verify_and_answer("What is pin 5?", [], sample_bijections, [])
        assert not isinstance(result, Refuse)
        assert result.answer == "RST"

    def test_pin_lookup_via_grid(self):
        g = Grid(
            id="pinout", rows=3, cols=2,
            cells=[
                GridCell(row=0, col=0, value="Pin", origin=Point(x=0.1, y=0.1)),
                GridCell(row=0, col=1, value="Name", origin=Point(x=0.5, y=0.1)),
                GridCell(row=1, col=0, value="5", origin=Point(x=0.1, y=0.2)),
                GridCell(row=1, col=1, value="VCC", origin=Point(x=0.5, y=0.2)),
                GridCell(row=2, col=0, value="6", origin=Point(x=0.1, y=0.3)),
                GridCell(row=2, col=1, value="GND", origin=Point(x=0.5, y=0.3)),
            ],
            origin=Point(x=0, y=0), doc_id="doc1", page=0,
        )
        result = verify_and_answer("What is pin 5?", [], [], [g])
        assert not isinstance(result, Refuse)
        assert result.answer == "VCC"

    def test_pin_not_found_refuses(self, sample_bijections):
        result = verify_and_answer("What is pin 99?", [], sample_bijections, [])
        assert isinstance(result, Refuse)


# ===================================================================
# 150: Part number
# ===================================================================


class TestPartNumber:
    def test_part_number(self, sample_units):
        result = verify_and_answer("What is the part number?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "AKILI-48Q" in result.answer

    def test_ordering_info(self, sample_units):
        result = verify_and_answer("What is the ordering information?", sample_units, [], [])
        assert not isinstance(result, Refuse)


# ===================================================================
# 160: Description
# ===================================================================


class TestDescription:
    def test_description(self, sample_units):
        result = verify_and_answer("What does this component do?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "logic IC" in result.answer

    def test_what_is_this(self, sample_units):
        result = verify_and_answer("What is this?", sample_units, [], [])
        assert not isinstance(result, Refuse)


# ===================================================================
# 200-210: Absolute maximum ratings
# ===================================================================


class TestAbsoluteMaximums:
    def test_absolute_max_voltage(self, sample_units):
        result = verify_and_answer("What is the absolute maximum voltage?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "5.5" in result.answer

    def test_absolute_max_current(self, sample_units):
        result = verify_and_answer("What is the absolute maximum current?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "500" in result.answer


# ===================================================================
# 300-320: Generic max (voltage, current, capacity)
# ===================================================================


class TestGenericMax:
    def test_max_voltage(self, sample_units):
        result = verify_and_answer("What is the maximum voltage?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "V" in result.answer

    def test_max_voltage_from_text_fallback(self):
        u = Unit(
            id="u1", value="Charge: CC-CV 4A, 4.2V, 100mA cut-off at 23℃",
            unit_of_measure=None, origin=Point(x=0.37, y=0.20), doc_id="d", page=5,
        )
        result = verify_and_answer("What is the max voltage?", [u], [], [])
        assert not isinstance(result, Refuse)
        assert "4.2" in result.answer

    def test_max_current(self, sample_units):
        result = verify_and_answer("What is the maximum current?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "mA" in result.answer

    def test_max_capacity(self):
        u = Unit(
            id="cap1", value=3000, unit_of_measure="mAh",
            context="nominal capacity", origin=Point(x=0.1, y=0.1), doc_id="d", page=0,
        )
        result = verify_and_answer("What is the maximum capacity?", [u], [], [])
        assert not isinstance(result, Refuse)
        assert "3000" in result.answer


# ===================================================================
# 400-430: Operating ranges and temperature
# ===================================================================


class TestOperatingRanges:
    def test_operating_voltage_range(self, sample_units):
        result = verify_and_answer("What is the operating voltage range?", sample_units, [], [])
        assert not isinstance(result, Refuse)

    def test_supply_voltage(self, sample_units):
        result = verify_and_answer("What is the supply voltage range?", sample_units, [], [])
        assert not isinstance(result, Refuse)

    def test_operating_temp_range(self, sample_units):
        result = verify_and_answer("What is the operating temperature range?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        answer = result.answer
        assert "-40" in answer or "85" in answer

    def test_junction_temp(self, sample_units):
        result = verify_and_answer("What is the junction temperature range?", sample_units, [], [])
        assert not isinstance(result, Refuse)

    def test_storage_temperature(self, sample_units):
        result = verify_and_answer("What is the storage temperature range?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "-65" in result.answer or "150" in result.answer

    def test_soldering_temperature(self, sample_units):
        result = verify_and_answer("What is the reflow soldering temperature?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "260" in result.answer


# ===================================================================
# 500-530: Electrical characteristics
# ===================================================================


class TestElectricalCharacteristics:
    def test_power_dissipation(self, sample_units):
        result = verify_and_answer("What is the max power dissipation?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "500" in result.answer or "mW" in result.answer

    def test_esd_ratings(self, sample_units):
        result = verify_and_answer("What are the ESD ratings?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "2000" in result.answer or "HBM" in result.answer

    def test_leakage_current(self, sample_units):
        result = verify_and_answer("What is the input leakage current?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "1" in result.answer

    def test_threshold_voltage(self, sample_units):
        result = verify_and_answer("What are the logic threshold levels?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "VIL" in result.answer or "VIH" in result.answer or "0.8" in result.answer


# ===================================================================
# 600-630: Timing & performance
# ===================================================================


class TestTimingPerformance:
    def test_clock_frequency(self, sample_units):
        result = verify_and_answer("What is the max clock speed?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "100" in result.answer or "MHz" in result.answer

    def test_propagation_delay(self, sample_units):
        result = verify_and_answer("What is the propagation delay?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "5.5" in result.answer or "ns" in result.answer

    def test_rise_fall_time(self, sample_units):
        result = verify_and_answer("What are the rise and fall times?", sample_units, [], [])
        assert not isinstance(result, Refuse)

    def test_setup_hold_time(self, sample_units):
        result = verify_and_answer("What are the setup and hold times?", sample_units, [], [])
        assert not isinstance(result, Refuse)


# ===================================================================
# 700-750: Physical / package
# ===================================================================


class TestPhysicalPackage:
    def test_package_type(self, sample_units):
        result = verify_and_answer("What package is this?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "TQFP-48" in result.answer

    def test_package_dimensions(self, sample_units):
        result = verify_and_answer("What are the package dimensions?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "7.0" in result.answer or "mm" in result.answer

    def test_thermal_resistance(self, sample_units):
        result = verify_and_answer("What is the thermal resistance (θJA)?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "45" in result.answer

    def test_weight(self, sample_units):
        result = verify_and_answer("What is the component weight?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "0.5" in result.answer

    def test_pin_count(self, sample_bijections):
        result = verify_and_answer("How many pins?", [], sample_bijections, [])
        assert not isinstance(result, Refuse)
        assert "6" in result.answer

    def test_moisture_sensitivity(self, sample_units):
        result = verify_and_answer("What is the MSL rating?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "3" in result.answer


# ===================================================================
# 800: Recommended operating conditions
# ===================================================================


class TestRecommendedOperating:
    def test_recommended_operating(self, sample_grids):
        result = verify_and_answer("What are the recommended operating conditions?", [], [], sample_grids)
        assert not isinstance(result, Refuse)
        assert "See table" in result.answer


# ===================================================================
# 900: Unit-by-intent fallback
# ===================================================================


class TestUnitByIntent:
    def test_charge_voltage(self):
        u = Unit(
            id="u1", value="Charge: CC-CV 4A, 4.2V, 100mA cut-off",
            label=None, unit_of_measure=None,
            origin=Point(x=0.37, y=0.20), doc_id="d", page=5,
        )
        result = verify_and_answer("What is the charge voltage?", [u], [], [])
        assert not isinstance(result, Refuse)
        assert "4.2" in result.answer

    def test_voltage_intent(self, sample_units):
        result = verify_and_answer("What is the voltage?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "V" in result.answer


# ===================================================================
# 950: Grid cell lookup
# ===================================================================


class TestGridCellLookup:
    def test_grid_supply_voltage_lookup(self, sample_grids):
        result = verify_and_answer("Supply Voltage range?", [], [], sample_grids)
        assert not isinstance(result, Refuse)

    def test_grid_temperature_lookup(self, sample_grids):
        result = verify_and_answer("Operating Temperature?", [], [], sample_grids)
        assert not isinstance(result, Refuse)


# ===================================================================
# 1000: Unit lookup by label
# ===================================================================


class TestUnitLookup:
    def test_label_match(self):
        u = Unit(
            id="u1", label="VBAT", value=4.2, unit_of_measure="V",
            origin=Point(x=0.1, y=0.1), doc_id="d", page=0,
        )
        result = verify_and_answer("What is VBAT?", [u], [], [])
        assert not isinstance(result, Refuse)
        assert "4.2" in result.answer


# ===================================================================
# Priority ordering
# ===================================================================


class TestPriorityOrdering:
    def test_absolute_max_before_generic_max(self, sample_units):
        """Absolute max voltage rule fires before generic max voltage."""
        result = verify_and_answer("What is the absolute maximum voltage?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert "5.5" in result.answer

    def test_pin_lookup_before_everything(self, sample_units, sample_bijections, sample_grids):
        """Pin lookup has highest priority."""
        result = verify_and_answer("What is pin 1?", sample_units, sample_bijections, sample_grids)
        assert not isinstance(result, Refuse)
        assert result.answer == "VCC"
        assert result.source_type == "bijection"


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_empty_question(self, sample_units, sample_bijections, sample_grids):
        result = verify_and_answer("", sample_units, sample_bijections, sample_grids)
        assert isinstance(result, Refuse)

    def test_unicode_question(self, sample_units):
        result = verify_and_answer("What is the θJA thermal resistance?", sample_units, [], [])
        assert not isinstance(result, Refuse)

    def test_very_long_question(self, sample_units, sample_bijections, sample_grids):
        q = "What is the maximum voltage? " * 100
        result = verify_and_answer(q, sample_units, sample_bijections, sample_grids)
        assert not isinstance(result, Refuse)

    def test_proof_has_page_number(self, sample_units):
        result = verify_and_answer("What is the propagation delay?", sample_units, [], [])
        assert not isinstance(result, Refuse)
        assert result.proof[0].page == 1

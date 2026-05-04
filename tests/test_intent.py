"""Tests for the intent classifier (B7)."""

from __future__ import annotations

import pytest

from akili.verify.intent import Intent, classify_intent, get_rule_intents, intent_allows_rule


class TestClassifyIntent:
    """Test intent classification."""

    def test_voltage_spec_questions(self):
        """Questions about voltage specs should classify as VOLTAGE_SPEC."""
        questions = [
            "What is the maximum voltage?",
            "What is the supply voltage range?",
            "What is VCC?",
            "What is the absolute maximum voltage rating?",
            "What is Vdd?",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.VOLTAGE_SPEC, f"Failed for: {q}"

    def test_current_spec_questions(self):
        """Questions about current specs should classify as CURRENT_SPEC."""
        questions = [
            "What is the maximum current?",
            "What is the supply current?",
            "What is Icc?",
            "What is the leakage current?",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.CURRENT_SPEC, f"Failed for: {q}"

    def test_power_spec_questions(self):
        """Questions about power specs should classify as POWER_SPEC."""
        questions = [
            "What is the power dissipation?",
            "What is the maximum power rating?",
            "What is Pd?",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.POWER_SPEC, f"Failed for: {q}"

    def test_temperature_spec_questions(self):
        """Questions about temperature specs should classify as TEMPERATURE_SPEC."""
        questions = [
            "What is the operating temperature range?",
            "What is the storage temperature?",
            "What is the junction temperature?",
            "What is the soldering temperature?",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.TEMPERATURE_SPEC, f"Failed for: {q}"

    def test_pin_lookup_questions(self):
        """Questions about pins should classify as PIN_LOOKUP."""
        questions = [
            "What is pin 5?",
            "What is pin number 3?",
            "What is the pinout?",
            "What is the function of pin 7?",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.PIN_LOOKUP, f"Failed for: {q}"

    def test_package_query_questions(self):
        """Questions about package should classify as PACKAGE_QUERY."""
        questions = [
            "What is the package type?",
            "What are the package dimensions?",
            "How many pins does this have?",
            "What is the footprint?",
            "What is the pin count?",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.PACKAGE_QUERY, f"Failed for: {q}"

    def test_thermal_query_questions(self):
        """Questions about thermal resistance should classify as THERMAL_QUERY."""
        questions = [
            "What is the thermal resistance?",
            "What is θJA?",
            "What is the junction-to-ambient thermal resistance?",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.THERMAL_QUERY, f"Failed for: {q}"

    def test_timing_spec_questions(self):
        """Questions about timing should classify as TIMING_SPEC."""
        questions = [
            "What is the propagation delay?",
            "What is the rise time?",
            "What is the setup time?",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.TIMING_SPEC, f"Failed for: {q}"

    def test_frequency_spec_questions(self):
        """Questions about frequency should classify as FREQUENCY_SPEC."""
        questions = [
            "What is the clock frequency?",
            "What is fmax?",
            "What is the bandwidth?",
            "What is the data rate?",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.FREQUENCY_SPEC, f"Failed for: {q}"

    def test_design_context_returns_general(self):
        """Questions with design context should return GENERAL_QUESTION."""
        questions = [
            "How do I design a voltage divider?",
            "Calculate the resistor value for this circuit",
            "Compare these two regulators",
            "How to choose a capacitor?",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.GENERAL_QUESTION, f"Failed for: {q}"

    def test_out_of_scope_questions(self):
        """Clearly out-of-scope questions should be classified as OUT_OF_SCOPE."""
        questions = [
            "What is the weather today?",
            "Who is the president?",
            "Tell me a recipe for cookies",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.OUT_OF_SCOPE, f"Failed for: {q}"

    def test_ambiguous_defaults_to_general(self):
        """Ambiguous questions should default to GENERAL_QUESTION."""
        questions = [
            "Tell me about this component",
            "What does this do?",
        ]
        for q in questions:
            assert classify_intent(q) == Intent.GENERAL_QUESTION, f"Failed for: {q}"


class TestIntentAllowsRule:
    """Test intent-rule filtering."""

    def test_matching_intent_allows_rule(self):
        """Rule should fire when intent matches."""
        assert intent_allows_rule(Intent.VOLTAGE_SPEC, {Intent.VOLTAGE_SPEC})
        assert intent_allows_rule(Intent.PIN_LOOKUP, {Intent.PIN_LOOKUP})

    def test_non_matching_intent_blocks_rule(self):
        """Rule should not fire when intent doesn't match."""
        assert not intent_allows_rule(Intent.VOLTAGE_SPEC, {Intent.CURRENT_SPEC})
        assert not intent_allows_rule(Intent.PIN_LOOKUP, {Intent.PACKAGE_QUERY})

    def test_none_intents_allows_all(self):
        """Rules with None intents should always fire."""
        assert intent_allows_rule(Intent.VOLTAGE_SPEC, None)
        assert intent_allows_rule(Intent.GENERAL_QUESTION, None)
        assert intent_allows_rule(Intent.OUT_OF_SCOPE, None) is False  # OUT_OF_SCOPE always refuses

    def test_general_question_allows_all(self):
        """GENERAL_QUESTION should allow all rules."""
        assert intent_allows_rule(Intent.GENERAL_QUESTION, {Intent.VOLTAGE_SPEC})
        assert intent_allows_rule(Intent.GENERAL_QUESTION, {Intent.PIN_LOOKUP})

    def test_out_of_scope_blocks_all(self):
        """OUT_OF_SCOPE should block all rules."""
        assert not intent_allows_rule(Intent.OUT_OF_SCOPE, {Intent.VOLTAGE_SPEC})
        assert not intent_allows_rule(Intent.OUT_OF_SCOPE, None)


class TestGetRuleIntents:
    """Test rule-to-intent mapping."""

    def test_known_rules_have_intents(self):
        """Known rules should return their intent sets."""
        assert get_rule_intents("pin_lookup") == {Intent.PIN_LOOKUP}
        assert get_rule_intents("max_voltage") == {Intent.VOLTAGE_SPEC}
        assert get_rule_intents("package_type") == {Intent.PACKAGE_QUERY}

    def test_unknown_rules_return_none(self):
        """Unknown rules should return None (allowing all intents)."""
        assert get_rule_intents("unknown_rule") is None
        assert get_rule_intents("unit_by_intent") is None  # Fallback rules have no filter

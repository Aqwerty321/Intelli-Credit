"""
Unit tests for rule_engine.py direction=either handling.

Covers Mode 2 (single-field thresholds) with direction="either".
"""
import pytest
from services.reasoning.rule_engine import RuleEngine


class TestDirectionEither:
    """Test that direction='either' in Mode 2 fires on both above and below."""

    @pytest.fixture(scope="class")
    def engine(self):
        return RuleEngine()

    def _make_rule(self, direction: str, thresholds: list[dict]) -> dict:
        """Helper: build a synthetic in-memory v2 rule dict."""
        return {
            "id": "rule_test_either",
            "slug": "test-direction-either",
            "name": "Test Direction Either",
            "version": "2.0",
            "condition": {
                "type": "threshold",
                "field": "test_field",
                "direction": direction,
                "thresholds": thresholds,
            },
            "action": {},
        }

    def _eval_rule(self, engine, rule_dict: dict, facts: dict):
        """Directly call _eval_threshold via the engine's private method."""
        condition = rule_dict["condition"]
        action = rule_dict.get("action", {})
        return engine._eval_threshold(condition, facts, action)

    # ------------------------------------------------------------------
    # direction="above" still works
    # ------------------------------------------------------------------

    def test_direction_above_fires_when_exceeded(self, engine):
        rule = self._make_rule("above", [
            {"value": 5, "risk_adjustment": 0.10, "level": "moderate"},
            {"value": 8, "risk_adjustment": 0.25, "level": "critical"},
        ])
        # val=9 should hit the "critical" threshold (highest crossed)
        fired, inputs, rationale, risk_adj, missing = self._eval_rule(engine, rule, {"test_field": 9})
        assert fired is True
        assert risk_adj == pytest.approx(0.25)

    def test_direction_above_silent_when_below(self, engine):
        rule = self._make_rule("above", [
            {"value": 5, "risk_adjustment": 0.10, "level": "moderate"},
        ])
        fired, *_ = self._eval_rule(engine, rule, {"test_field": 3})
        assert fired is False

    # ------------------------------------------------------------------
    # direction="below" still works
    # ------------------------------------------------------------------

    def test_direction_below_fires_when_low(self, engine):
        rule = self._make_rule("below", [
            {"value": 50, "risk_adjustment": 0.08, "level": "low"},
        ])
        fired, _, _, risk_adj, _ = self._eval_rule(engine, rule, {"test_field": 30})
        assert fired is True
        assert risk_adj == pytest.approx(0.08)

    def test_direction_below_silent_when_high(self, engine):
        rule = self._make_rule("below", [
            {"value": 50, "risk_adjustment": 0.08, "level": "low"},
        ])
        fired, *_ = self._eval_rule(engine, rule, {"test_field": 80})
        assert fired is False

    # ------------------------------------------------------------------
    # direction="either" — the Phase 3 fix
    # ------------------------------------------------------------------

    def test_direction_either_fires_when_above_threshold(self, engine):
        rule = self._make_rule("either", [
            {"value": 100, "risk_adjustment": 0.20, "level": "high_upper"},
        ])
        # val=150 is above 100 → should fire
        fired, _, _, risk_adj, _ = self._eval_rule(engine, rule, {"test_field": 150})
        assert fired is True
        assert risk_adj == pytest.approx(0.20)

    def test_direction_either_fires_when_below_threshold(self, engine):
        rule = self._make_rule("either", [
            {"value": 30, "risk_adjustment": 0.15, "level": "low_bound"},
        ])
        # val=20 is below 30 → should fire
        fired, _, _, risk_adj, _ = self._eval_rule(engine, rule, {"test_field": 20})
        assert fired is True
        assert risk_adj == pytest.approx(0.15)

    def test_direction_either_silent_in_middle(self, engine):
        rule = self._make_rule("either", [
            {"value": 80, "risk_adjustment": 0.20, "level": "high"},
            {"value": 20, "risk_adjustment": 0.15, "level": "low"},
        ])
        # val=50 is neither above 80 nor below 20
        fired, *_ = self._eval_rule(engine, rule, {"test_field": 50})
        assert fired is False

    def test_direction_either_upper_breach_picks_upper_threshold(self, engine):
        rule = self._make_rule("either", [
            {"value": 90, "risk_adjustment": 0.30, "level": "very_high"},  # upper bound (max)
            {"value": 20, "risk_adjustment": 0.15, "level": "low_bound"},  # lower bound (min)
        ])
        # val=95 exceeds the upper bound (90) → should fire with upper's risk_adj=0.30
        fired, _, _, risk_adj, _ = self._eval_rule(engine, rule, {"test_field": 95})
        assert fired is True
        assert risk_adj == pytest.approx(0.30)

    def test_direction_either_missing_field_returns_missing(self, engine):
        rule = self._make_rule("either", [
            {"value": 50, "risk_adjustment": 0.10, "level": "boundary"},
        ])
        fired, _, _, _, missing = self._eval_rule(engine, rule, {})
        assert fired is False
        assert "test_field" in missing

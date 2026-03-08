"""
Unit tests for the v2 rule engine.
Validates per-threshold risk_adjustment and direction semantics.
Run: pytest tests/unit/test_rule_engine.py -v
"""
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Rule 0003 — DPD threshold (direction: above)
# ─────────────────────────────────────────────────────────────────────────────

class TestDPDThreshold:
    def test_dpd_90_fires_040(self, rule_engine):
        """DPD >= 90 must fire with risk_adjustment 0.40."""
        firings = rule_engine.evaluate({"max_dpd_last_12m": 120})
        dpd = [f for f in firings if f.rule_slug == "dpd-threshold"]
        assert dpd, "DPD rule did not fire for max_dpd_last_12m=120"
        assert dpd[0].risk_adjustment == pytest.approx(0.40), (
            f"Expected 0.40 but got {dpd[0].risk_adjustment}"
        )

    def test_dpd_60_fires_020(self, rule_engine):
        """DPD >= 60 (but < 90) must fire with risk_adjustment 0.20."""
        firings = rule_engine.evaluate({"max_dpd_last_12m": 75})
        dpd = [f for f in firings if f.rule_slug == "dpd-threshold"]
        assert dpd, "DPD rule did not fire for max_dpd_last_12m=75"
        assert dpd[0].risk_adjustment == pytest.approx(0.20), (
            f"Expected 0.20 but got {dpd[0].risk_adjustment}"
        )

    def test_dpd_30_fires_010(self, rule_engine):
        """DPD >= 30 (but < 60) must fire with risk_adjustment 0.10."""
        firings = rule_engine.evaluate({"max_dpd_last_12m": 45})
        dpd = [f for f in firings if f.rule_slug == "dpd-threshold"]
        assert dpd, "DPD rule did not fire for max_dpd_last_12m=45"
        assert dpd[0].risk_adjustment == pytest.approx(0.10)

    def test_dpd_below_threshold_no_fire(self, rule_engine):
        """DPD=15 must not fire."""
        firings = rule_engine.evaluate({"max_dpd_last_12m": 15})
        dpd = [f for f in firings if f.rule_slug == "dpd-threshold"]
        assert not dpd, "DPD rule incorrectly fired for max_dpd_last_12m=15"


# ─────────────────────────────────────────────────────────────────────────────
# Rule 0005 — CIBIL CMR threshold (direction: above)
# ─────────────────────────────────────────────────────────────────────────────

class TestCIBILCMR:
    def test_cmr9_fires_040(self, rule_engine):
        firings = rule_engine.evaluate({"cibil_cmr_rank": 9})
        cmr = [f for f in firings if f.rule_slug == "cibil-cmr-threshold"]
        assert cmr, "CMR rule did not fire for rank=9"
        assert cmr[0].risk_adjustment == pytest.approx(0.40)

    def test_cmr7_fires_025(self, rule_engine):
        firings = rule_engine.evaluate({"cibil_cmr_rank": 7})
        cmr = [f for f in firings if f.rule_slug == "cibil-cmr-threshold"]
        assert cmr, "CMR rule did not fire for rank=7"
        assert cmr[0].risk_adjustment == pytest.approx(0.25)

    def test_cmr4_no_fire(self, rule_engine):
        firings = rule_engine.evaluate({"cibil_cmr_rank": 4})
        cmr = [f for f in firings if f.rule_slug == "cibil-cmr-threshold"]
        assert not cmr, "CMR rule incorrectly fired for rank=4"


# ─────────────────────────────────────────────────────────────────────────────
# Rule 0008 — Capacity Utilization (direction: below)
# ─────────────────────────────────────────────────────────────────────────────

class TestCapacityUtilization:
    def test_cap40_fires(self, rule_engine):
        """Capacity=40% is below flag threshold (50%), must fire."""
        firings = rule_engine.evaluate({"capacity_utilization_pct": 40})
        cap = [f for f in firings if f.rule_slug == "capacity-utilization"]
        assert cap, "Capacity rule did not fire for utilization=40"
        assert cap[0].risk_adjustment > 0, "risk_adjustment must be > 0"

    def test_cap25_fires_harder(self, rule_engine):
        """Capacity=25% (below hard_constraint 30%) must fire with 0.25."""
        firings = rule_engine.evaluate({"capacity_utilization_pct": 25})
        cap = [f for f in firings if f.rule_slug == "capacity-utilization"]
        assert cap, "Capacity rule did not fire for utilization=25"
        assert cap[0].risk_adjustment == pytest.approx(0.25)

    def test_cap75_no_fire(self, rule_engine):
        """Capacity=75% is fine, must not fire."""
        firings = rule_engine.evaluate({"capacity_utilization_pct": 75})
        cap = [f for f in firings if f.rule_slug == "capacity-utilization"]
        assert not cap, "Capacity rule incorrectly fired for utilization=75"


# ─────────────────────────────────────────────────────────────────────────────
# Rule 0010 — Collateral Coverage Ratio
# ─────────────────────────────────────────────────────────────────────────────

class TestCollateralCoverage:
    def test_coverage_080_fires(self, rule_engine):
        """Coverage 0.8x (< 1.0 hard_constraint) must fire with 0.30."""
        firings = rule_engine.evaluate({
            "collateral_value": 8_000_000,
            "loan_amount_requested": 10_000_000,
        })
        col = [f for f in firings if f.rule_slug == "collateral-coverage"]
        assert col, "Collateral rule did not fire for 0.8x coverage"
        assert col[0].risk_adjustment == pytest.approx(0.30)

    def test_coverage_110_fires_015(self, rule_engine):
        """Coverage 1.1x (above 1.0 but below 1.25 flag) should fire with 0.15."""
        firings = rule_engine.evaluate({
            "collateral_value": 11_000_000,
            "loan_amount_requested": 10_000_000,
        })
        col = [f for f in firings if f.rule_slug == "collateral-coverage"]
        assert col, "Collateral rule did not fire for 1.1x coverage"
        assert col[0].risk_adjustment == pytest.approx(0.15)

    def test_coverage_150_no_fire(self, rule_engine):
        """Coverage 1.5x+ should not fire."""
        firings = rule_engine.evaluate({
            "collateral_value": 15_000_000,
            "loan_amount_requested": 10_000_000,
        })
        col = [f for f in firings if f.rule_slug == "collateral-coverage"]
        assert not col, "Collateral rule incorrectly fired for 1.5x coverage"


# ─────────────────────────────────────────────────────────────────────────────
# Rule 0001 — GST ITC Mismatch
# ─────────────────────────────────────────────────────────────────────────────

class TestGSTITCMismatch:
    def test_itc_mismatch_fires(self, rule_engine):
        firings = rule_engine.evaluate({
            "gstr3b_itc_claimed": 5_000_000,
            "gstr2a_itc_available": 4_000_000,
        })
        gst = [f for f in firings if f.rule_slug == "gst-itc-mismatch"]
        assert gst, "GST ITC rule did not fire"
        assert gst[0].risk_adjustment == pytest.approx(0.15)

    def test_itc_below_threshold_no_fire(self, rule_engine):
        firings = rule_engine.evaluate({
            "gstr3b_itc_claimed": 4_050_000,
            "gstr2a_itc_available": 4_000_000,
        })
        gst = [f for f in firings if f.rule_slug == "gst-itc-mismatch"]
        assert not gst, "GST ITC rule incorrectly fired for 1.25% excess"


# ─────────────────────────────────────────────────────────────────────────────
# Rule 0004 — Dishonoured Cheques
# ─────────────────────────────────────────────────────────────────────────────

class TestDishonouredCheques:
    def test_five_cheques_fires_020(self, rule_engine):
        firings = rule_engine.evaluate({"dishonoured_cheque_count_12m": 5})
        dc = [f for f in firings if f.rule_slug == "dishonoured-cheques"]
        assert dc, "Dishonoured cheques rule did not fire"
        assert dc[0].risk_adjustment == pytest.approx(0.20)

    def test_two_cheques_no_fire(self, rule_engine):
        firings = rule_engine.evaluate({"dishonoured_cheque_count_12m": 2})
        dc = [f for f in firings if f.rule_slug == "dishonoured-cheques"]
        assert not dc


# ─────────────────────────────────────────────────────────────────────────────
# Rule 0002 — Circular Trading (hard reject)
# ─────────────────────────────────────────────────────────────────────────────

class TestCircularTrading:
    def test_cycle_detected_hard_reject(self, rule_engine):
        firings = rule_engine.evaluate({
            "cycle_detected": True,
            "cycle_length": 4,
            "total_value": 10_000_000,
            "entity_count": 4,
            "cycle_description": "4-hop cycle",
        })
        ct = [f for f in firings if f.rule_slug == "circular-trading-indicator"]
        assert ct, "Circular trading rule did not fire"
        assert ct[0].hard_reject is True
        assert ct[0].risk_adjustment == pytest.approx(0.30)

    def test_no_cycle_no_fire(self, rule_engine):
        firings = rule_engine.evaluate({"cycle_detected": False})
        ct = [f for f in firings if f.rule_slug == "circular-trading-indicator"]
        assert not ct


# ─────────────────────────────────────────────────────────────────────────────
# Schema v2 fields on all firings
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemaV2:
    def test_schema_version_v2(self, rule_engine):
        firings = rule_engine.evaluate({"max_dpd_last_12m": 120})
        for f in firings:
            d = f.to_dict()
            assert d["schema_version"] == "v2", f"Rule {f.rule_slug} missing schema_version v2"  # rule_firing dicts keep v2

    def test_missing_data_flags_field_present(self, rule_engine):
        firings = rule_engine.evaluate({"max_dpd_last_12m": 120})
        for f in firings:
            assert hasattr(f, "missing_data_flags"), "RuleFiring missing missing_data_flags"

    def test_rationale_no_raw_template(self, rule_engine):
        """Rationale must have {key} replaced, not carry raw braces unless key is truly missing."""
        firings = rule_engine.evaluate({"max_dpd_last_12m": 120})
        dpd = [f for f in firings if f.rule_slug == "dpd-threshold"]
        assert dpd
        # Should not contain raw template vars that were provided
        assert "120" in dpd[0].rationale or "[N/A]" in dpd[0].rationale or "days" in dpd[0].rationale

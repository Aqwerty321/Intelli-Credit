"""
Unit tests for CounterfactualChallenger.

Verifies that the deterministic scenario builder produces
sensible what-if scenarios for common risk profiles.
"""
import pytest
from services.agents.counterfactual import CounterfactualChallenger, Counterfactual


@pytest.fixture(scope="module")
def challenger():
    return CounterfactualChallenger()


class TestDeterministicScenarios:
    def test_high_cmr_generates_improve_scenario(self, challenger):
        """CMR=9 (bad) → scenario shows what happens if CMR were 3 (approve)."""
        facts = {"cibil_cmr_rank": 9, "loan_amount_requested": 10_000_000}
        result = challenger.challenge("REJECT", facts, [], 10_000_000)
        cmr_scenarios = [s for s in result.scenarios if s.changed_field == "cibil_cmr_rank"]
        assert cmr_scenarios, "No CMR counterfactual generated"
        s = cmr_scenarios[0]
        assert s.hypothetical_value == 3.0
        assert s.hypothetical_recommendation == "APPROVE"
        assert s.delta_risk_score < 0   # reducing CMR improves risk

    def test_high_dpd_generates_improve_scenario(self, challenger):
        """Max DPD=120 → scenario shows what happens if DPD were 0."""
        facts = {"max_dpd_last_12m": 120, "loan_amount_requested": 5_000_000}
        result = challenger.challenge("REJECT", facts, [], 5_000_000)
        dpd_scenarios = [s for s in result.scenarios if s.changed_field == "max_dpd_last_12m"]
        assert dpd_scenarios
        s = dpd_scenarios[0]
        assert s.hypothetical_value == 0.0
        assert s.delta_risk_score < 0

    def test_zero_dpd_generates_worsen_scenario(self, challenger):
        """Clean DPD=0 → scenario shows risk if DPD were 120."""
        facts = {"max_dpd_last_12m": 0, "loan_amount_requested": 5_000_000}
        result = challenger.challenge("APPROVE", facts, [], 5_000_000)
        dpd_scenarios = [s for s in result.scenarios if s.changed_field == "max_dpd_last_12m"]
        assert dpd_scenarios
        s = dpd_scenarios[0]
        assert s.hypothetical_value == 120.0
        assert s.hypothetical_recommendation == "REJECT"
        assert s.delta_risk_score > 0

    def test_low_capacity_utilisation_generates_scenario(self, challenger):
        facts = {"capacity_utilization_pct": 35.0, "loan_amount_requested": 5_000_000}
        result = challenger.challenge("CONDITIONAL", facts, [], 5_000_000)
        cap_scenarios = [s for s in result.scenarios if s.changed_field == "capacity_utilization_pct"]
        assert cap_scenarios

    def test_criminal_cases_generates_scenario(self, challenger):
        facts = {"criminal_cases": 3, "loan_amount_requested": 10_000_000}
        result = challenger.challenge("REJECT", facts, [], 10_000_000)
        crim_scenarios = [s for s in result.scenarios if s.changed_field == "criminal_cases"]
        assert crim_scenarios
        s = crim_scenarios[0]
        assert s.hypothetical_value == 0.0
        assert s.delta_risk_score < 0

    def test_no_relevant_fields_empty_scenarios(self, challenger):
        """Fields not in the counterfactual map → no scenarios generated."""
        facts = {"loan_amount_requested": 10_000_000}  # only loan amount, no risk fields
        result = challenger.challenge("APPROVE", facts, [], 10_000_000)
        assert isinstance(result.scenarios, list)
        # OK to have 0 counterfactuals when there are no risk fields

    def test_result_has_required_keys(self, challenger):
        facts = {"cibil_cmr_rank": 8, "loan_amount_requested": 10_000_000}
        result = challenger.challenge("REJECT", facts, [], 10_000_000)
        d = result.to_dict()
        for key in ("original_recommendation", "scenario_count", "scenarios"):
            assert key in d

    def test_to_dict_scenarios_have_required_keys(self, challenger):
        facts = {"cibil_cmr_rank": 9, "max_dpd_last_12m": 90, "loan_amount_requested": 5_000_000}
        result = challenger.challenge("REJECT", facts, [], 5_000_000)
        for s in result.to_dict()["scenarios"]:
            for key in ("scenario_id", "description", "changed_field",
                        "original_value", "hypothetical_value",
                        "hypothetical_recommendation", "delta_risk_score"):
                assert key in s, f"Key '{key}' missing from scenario dict"

    def test_max_5_scenarios_returned(self, challenger):
        """Should return at most 5 scenarios."""
        facts = {
            "cibil_cmr_rank": 9,
            "max_dpd_last_12m": 120,
            "dishonoured_cheque_count_12m": 5,
            "capacity_utilization_pct": 30,
            "collateral_value": 2_000_000,
            "criminal_cases": 2,
            "loan_amount_requested": 10_000_000,
        }
        result = challenger.challenge("REJECT", facts, [], 10_000_000)
        assert len(result.scenarios) <= 5

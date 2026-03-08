"""
Counterfactual Challenger Agent for Intelli-Credit (Phase 3).

Given a decided risk assessment, generates "what-if" scenarios that would
change the recommendation — enabling judges to stress-test the decision.

Uses LIGHT_MODEL (qwen2.5:3b). Falls back to deterministic rule-delta scenarios.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Counterfactual:
    scenario_id: str
    description: str              # "What if CMR were 3 instead of 8?"
    changed_field: str            # e.g. "cibil_cmr_rank"
    original_value: object
    hypothetical_value: object
    hypothetical_recommendation: str   # "APPROVE" | "CONDITIONAL" | "REJECT"
    delta_risk_score: float            # positive = increased risk, negative = decreased risk
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "description": self.description,
            "changed_field": self.changed_field,
            "original_value": self.original_value,
            "hypothetical_value": self.hypothetical_value,
            "hypothetical_recommendation": self.hypothetical_recommendation,
            "delta_risk_score": round(self.delta_risk_score, 4),
            "rationale": self.rationale,
        }


@dataclass
class CounterfactualResult:
    original_recommendation: str
    scenarios: list[Counterfactual] = field(default_factory=list)
    top_scenario: Optional[Counterfactual] = None
    fallback: bool = False

    def to_dict(self) -> dict:
        return {
            "original_recommendation": self.original_recommendation,
            "scenario_count": len(self.scenarios),
            "top_scenario": self.top_scenario.description if self.top_scenario else None,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "fallback": self.fallback,
        }


class CounterfactualChallenger:
    """Generates actionable what-if scenarios for a credit decision."""

    # Fields that can be cheaply counter-factualised with rule deltas
    _COUNTERFACTUAL_FIELDS = [
        ("cibil_cmr_rank", "CIBIL CMR rank"),
        ("max_dpd_last_12m", "maximum days past due"),
        ("dishonoured_cheque_count_12m", "dishonoured cheque count"),
        ("capacity_utilization_pct", "capacity utilisation"),
        ("collateral_value", "collateral value"),
        ("criminal_cases", "criminal case count"),
    ]

    def __init__(self, ollama_base: str = None):
        from services.cognitive.engine import CognitiveEngine, OLLAMA_BASE, LIGHT_MODEL
        base = ollama_base or OLLAMA_BASE
        self.engine = CognitiveEngine(base_url=base, model=LIGHT_MODEL)
        self._light_model = LIGHT_MODEL
        self.llm_available = self._check_light_model_available()

    def _check_light_model_available(self) -> bool:
        if not self.engine.is_alive():
            return False
        return any(self._light_model in m for m in self.engine.list_models())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def challenge(
        self,
        recommendation: str,
        facts: dict,
        rule_firings: list,
        loan_amount: float = 0,
    ) -> CounterfactualResult:
        """Generate counterfactual scenarios for the current recommendation."""
        scenarios = self._deterministic_scenarios(recommendation, facts, rule_firings, loan_amount)

        if self.llm_available and scenarios:
            # Optionally enrich top scenario with LLM rationale
            top = scenarios[0]
            enriched = self._llm_enrich(top, recommendation, facts)
            if enriched:
                scenarios[0] = enriched

        result = CounterfactualResult(
            original_recommendation=recommendation,
            scenarios=scenarios,
            top_scenario=scenarios[0] if scenarios else None,
            fallback=not self.llm_available,
        )
        return result

    # ------------------------------------------------------------------
    # Deterministic scenario generation
    # ------------------------------------------------------------------

    def _deterministic_scenarios(
        self,
        recommendation: str,
        facts: dict,
        rule_firings: list,
        loan_amount: float,
    ) -> list[Counterfactual]:
        scenarios: list[Counterfactual] = []

        fired_fields: set[str] = set()
        for rf in rule_firings:
            inputs = getattr(rf, "inputs", {}) if hasattr(rf, "inputs") else rf.get("inputs", {})
            fired_fields.update(inputs.keys())

        for field_key, field_label in self._COUNTERFACTUAL_FIELDS:
            current = facts.get(field_key)
            if current is None:
                continue

            scenario = self._build_scenario(
                field_key, field_label, current, recommendation, facts, len(scenarios)
            )
            if scenario:
                scenarios.append(scenario)

        # Sort by absolute delta (biggest impact first)
        scenarios.sort(key=lambda s: abs(s.delta_risk_score), reverse=True)
        return scenarios[:5]   # top 5

    def _build_scenario(
        self,
        field_key: str,
        field_label: str,
        current_val,
        recommendation: str,
        facts: dict,
        idx: int,
    ) -> Optional[Counterfactual]:
        """Construct a what-if for a single field."""
        current = float(current_val)

        if field_key == "cibil_cmr_rank":
            if current >= 7:
                hyp = 3.0
                hyp_rec = "APPROVE"
                delta = -(current - hyp) * 0.05
                desc = f"If {field_label} were {hyp:.0f} (currently {current:.0f})"
            elif current <= 3:
                hyp = 8.0
                hyp_rec = "REJECT"
                delta = (hyp - current) * 0.05
                desc = f"If {field_label} were {hyp:.0f} (currently {current:.0f})"
            else:
                return None

        elif field_key == "max_dpd_last_12m":
            if current >= 90:
                hyp = 0.0
                hyp_rec = "CONDITIONAL"
                delta = -0.30
                desc = f"If {field_label} were 0 (currently {current:.0f} days)"
            elif current == 0:
                hyp = 120.0
                hyp_rec = "REJECT"
                delta = +0.40
                desc = f"If {field_label} were 120 days (currently 0)"
            else:
                return None

        elif field_key == "dishonoured_cheque_count_12m":
            if current > 3:
                hyp = 0.0
                hyp_rec = "CONDITIONAL"
                delta = -0.10
                desc = f"If {field_label} were 0 (currently {current:.0f})"
            else:
                return None

        elif field_key == "capacity_utilization_pct":
            if current < 50:
                hyp = 75.0
                hyp_rec = "CONDITIONAL"
                delta = -0.05
                desc = f"If {field_label} were 75% (currently {current:.0f}%)"
            else:
                return None

        elif field_key == "collateral_value":
            loan_amount = facts.get("loan_amount_requested", 1.0)
            coverage = current / loan_amount if loan_amount > 0 else 0
            if coverage < 1.0:
                hyp = loan_amount * 1.5
                hyp_rec = "CONDITIONAL"
                delta = -0.10
                desc = f"If collateral coverage were 150% (currently {coverage*100:.0f}%)"
            else:
                return None

        elif field_key == "criminal_cases":
            if current > 0:
                hyp = 0.0
                hyp_rec = "CONDITIONAL"
                delta = -0.25
                desc = f"If no criminal cases (currently {current:.0f})"
            else:
                return None

        else:
            return None

        return Counterfactual(
            scenario_id=f"cf_{idx:02d}",
            description=desc,
            changed_field=field_key,
            original_value=current,
            hypothetical_value=hyp,
            hypothetical_recommendation=hyp_rec,
            delta_risk_score=delta,
            rationale="",
        )

    # ------------------------------------------------------------------
    # LLM enrichment
    # ------------------------------------------------------------------

    def _llm_enrich(self, scenario: Counterfactual, recommendation: str, facts: dict) -> Optional[Counterfactual]:
        """Use LIGHT_MODEL to generate a one-sentence rationale for the top scenario."""
        prompt = (
            f"A credit application is currently recommended as '{recommendation}'.\n"
            f"Counterfactual: {scenario.description}\n"
            f"Hypothetical outcome: {scenario.hypothetical_recommendation}\n\n"
            "In one sentence, explain why changing this input would alter the recommendation. "
            "Be direct and specific."
        )
        try:
            resp = self.engine.generate(prompt, max_tokens=100, temperature=0.3)
            rationale = (resp.answer or resp.raw_text).strip().split("\n")[0]
            if rationale and len(rationale) > 10:
                scenario.rationale = rationale
                return scenario
        except Exception:
            pass
        return None

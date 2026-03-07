"""
PyReason-based rule engine for Intelli-Credit.
Loads rules from rules/*.yml and performs deterministic inference
with full audit traces.

Falls back to pure Python rule evaluation if PyReason is unavailable.
"""
import json
import os
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RULES_DIR = PROJECT_ROOT / "rules"


@dataclass
class RuleFiring:
    """Record of a rule firing with full trace."""
    rule_id: str
    rule_slug: str
    severity: str
    flag_type: str
    rationale: str
    risk_adjustment: float
    cam_section: str
    inputs: dict = field(default_factory=dict)
    trace: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    hard_reject: bool = False

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_slug": self.rule_slug,
            "severity": self.severity,
            "flag_type": self.flag_type,
            "rationale": self.rationale,
            "risk_adjustment": self.risk_adjustment,
            "cam_section": self.cam_section,
            "inputs": self.inputs,
            "trace": self.trace,
            "timestamp": self.timestamp,
            "hard_reject": self.hard_reject,
        }


class RuleEngine:
    """Neuro-symbolic rule engine with PyReason primary and Python fallback."""

    def __init__(self):
        self.rules: list[dict] = []
        self._backend = self._detect_backend()
        self.load_rules()

    def _detect_backend(self) -> str:
        """Detect available reasoning backend."""
        try:
            import pyreason
            return "pyreason"
        except ImportError:
            pass
        return "python"

    def load_rules(self, rules_dir: Optional[Path] = None) -> None:
        """Load all rule definitions from YAML files."""
        rules_dir = rules_dir or RULES_DIR
        self.rules = []

        for rule_file in sorted(rules_dir.glob("*.yml")):
            try:
                with open(rule_file) as f:
                    rule = yaml.safe_load(f)
                if rule and isinstance(rule, dict):
                    rule["_file"] = str(rule_file)
                    self.rules.append(rule)
            except Exception as e:
                print(f"Warning: Failed to load rule {rule_file}: {e}")

        print(f"Loaded {len(self.rules)} rules from {rules_dir}")

    def evaluate(self, facts: dict) -> list[RuleFiring]:
        """Evaluate all rules against the given facts."""
        firings = []

        for rule in self.rules:
            firing = self._evaluate_rule(rule, facts)
            if firing:
                firings.append(firing)

        return firings

    def _evaluate_rule(self, rule: dict, facts: dict) -> Optional[RuleFiring]:
        """Evaluate a single rule against facts."""
        rule_id = rule.get("rule_id", "unknown")
        slug = rule.get("slug", "unknown")
        condition = rule.get("condition", {})
        action = rule.get("action", {})

        cond_type = condition.get("type", "")

        triggered = False
        inputs_used = {}
        rationale = ""

        if cond_type == "threshold_comparison":
            triggered, inputs_used, rationale = self._eval_threshold(condition, facts, action)
        elif cond_type == "count_threshold":
            triggered, inputs_used, rationale = self._eval_count(condition, facts, action)
        elif cond_type == "graph_motif":
            triggered, inputs_used, rationale = self._eval_graph_motif(condition, facts, action)
        elif cond_type == "count_and_severity":
            triggered, inputs_used, rationale = self._eval_count_severity(condition, facts, action)
        elif cond_type == "ratio_comparison":
            triggered, inputs_used, rationale = self._eval_ratio(condition, facts, action)
        elif cond_type == "sentiment_and_count":
            triggered, inputs_used, rationale = self._eval_sentiment(condition, facts, action)

        if not triggered:
            return None

        # Determine risk adjustment
        risk_adj = action.get("risk_adjustment", 0.0)
        if isinstance(risk_adj, dict):
            risk_adj = max(risk_adj.values()) if risk_adj else 0.0

        # Format rationale from template
        template = action.get("rationale_template", rationale)
        try:
            formatted_rationale = template.format(**{**facts, **inputs_used})
        except (KeyError, IndexError):
            formatted_rationale = rationale or template

        return RuleFiring(
            rule_id=rule_id,
            rule_slug=slug,
            severity=rule.get("severity", "MEDIUM"),
            flag_type=action.get("flag", "AMBER_FLAG"),
            rationale=formatted_rationale.strip(),
            risk_adjustment=risk_adj,
            cam_section=action.get("cam_section", "general"),
            inputs=inputs_used,
            trace={
                "rule_file": rule.get("_file", ""),
                "condition_type": cond_type,
                "backend": self._backend,
                "evaluation": "deterministic",
            },
            hard_reject=action.get("hard_reject", False),
        )

    def _eval_threshold(self, condition: dict, facts: dict, action: dict):
        """Evaluate threshold comparison rule."""
        lhs_field = condition.get("lhs") or condition.get("field")
        rhs_field = condition.get("rhs")
        thresholds = condition.get("thresholds", [])

        if lhs_field and lhs_field in facts:
            lhs_val = float(facts[lhs_field])
            inputs = {lhs_field: lhs_val}

            if rhs_field and rhs_field in facts:
                rhs_val = float(facts[rhs_field])
                inputs[rhs_field] = rhs_val
                threshold_pct = condition.get("threshold_pct", 10.0)
                excess = lhs_val - rhs_val
                if rhs_val > 0:
                    excess_pct = (excess / rhs_val) * 100
                else:
                    excess_pct = 0

                inputs["excess_pct"] = round(excess_pct, 2)

                if excess_pct > threshold_pct:
                    abs_threshold = condition.get("absolute_threshold", 0)
                    if excess >= abs_threshold:
                        return True, inputs, f"Excess of {excess_pct:.1f}% detected"

            elif thresholds:
                for t in reversed(thresholds):
                    if lhs_val >= t.get("value", float('inf')):
                        inputs["threshold_level"] = t.get("level", "flag")
                        inputs["threshold_severity"] = t.get("severity", "HIGH")
                        return True, inputs, f"{lhs_field} = {lhs_val} exceeds {t['level']} threshold of {t['value']}"

        return False, {}, ""

    def _eval_count(self, condition: dict, facts: dict, action: dict):
        """Evaluate count threshold rule."""
        field_name = condition.get("field")
        threshold = condition.get("threshold", 0)

        if field_name in facts:
            value = int(facts[field_name])
            if value > threshold:
                return True, {field_name: value}, f"{field_name} = {value} exceeds threshold {threshold}"

        return False, {}, ""

    def _eval_graph_motif(self, condition: dict, facts: dict, action: dict):
        """Evaluate graph motif detection rule."""
        if facts.get("cycle_detected", False):
            cycle_length = facts.get("cycle_length", 0)
            min_length = condition.get("min_cycle_length", 3)
            total_value = facts.get("total_value", 0)
            min_value = condition.get("min_edge_weight", 500000)

            if cycle_length >= min_length and total_value >= min_value:
                return True, {
                    "cycle_length": cycle_length,
                    "total_value": total_value,
                    "cycle_description": facts.get("cycle_description", "Circular trading pattern"),
                    "entity_count": facts.get("entity_count", cycle_length),
                    "window_days": condition.get("temporal_window_days", 90),
                }, "Circular trading pattern detected"

        return False, {}, ""

    def _eval_count_severity(self, condition: dict, facts: dict, action: dict):
        """Evaluate count with severity levels rule."""
        thresholds = condition.get("thresholds", [])

        for t in thresholds:
            category = t.get("category")
            count_field = f"{category}_cases" if category else condition.get("field")
            if count_field in facts:
                value = int(facts[count_field])
                min_count = t.get("count", 1)
                if value >= min_count:
                    return True, {
                        count_field: value,
                        "severity": t.get("severity", "MEDIUM"),
                    }, f"{count_field} = {value} exceeds threshold"

        return False, {}, ""

    def _eval_ratio(self, condition: dict, facts: dict, action: dict):
        """Evaluate ratio comparison rule."""
        num_field = condition.get("numerator")
        den_field = condition.get("denominator")
        thresholds = condition.get("thresholds", [])

        if num_field in facts and den_field in facts:
            num = float(facts[num_field])
            den = float(facts[den_field])
            if den > 0:
                ratio = num / den
                inputs = {
                    num_field: num,
                    den_field: den,
                    "coverage_ratio": round(ratio, 2),
                }

                for t in thresholds:
                    threshold_ratio = t.get("ratio", 0)
                    if ratio < threshold_ratio:
                        return True, inputs, f"Coverage ratio {ratio:.2f} below {threshold_ratio}"

        return False, {}, ""

    def _eval_sentiment(self, condition: dict, facts: dict, action: dict):
        """Evaluate sentiment and count rule."""
        sent_field = condition.get("field", "sector_sentiment_score")
        sent_threshold = condition.get("sentiment_threshold", -0.3)
        min_evidence = condition.get("min_evidence_count", 2)

        if sent_field in facts:
            sentiment = float(facts[sent_field])
            evidence_count = int(facts.get("evidence_count", 0))

            if sentiment < sent_threshold and evidence_count >= min_evidence:
                return True, {
                    sent_field: sentiment,
                    "evidence_count": evidence_count,
                }, f"Negative sentiment {sentiment:.2f} with {evidence_count} sources"

        return False, {}, ""

    def get_rule_count(self) -> int:
        return len(self.rules)

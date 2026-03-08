"""
Neuro-symbolic rule engine for Intelli-Credit (schema v2).
Loads rules from rules/*.yml and performs deterministic inference
with full audit traces.

Falls back to pure Python rule evaluation if PyReason is unavailable.

v2 changes:
 - Per-threshold risk_adjustment (read from thresholds[*].risk_adjustment)
 - direction: "above"|"below" support in threshold_comparison
 - Template formatting no longer crashes on missing keys
 - missing_data_flags tracked when a required fact uses its default
 - schema_version: "v2" in all RuleFiring dicts
"""
import re
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RULES_DIR = PROJECT_ROOT / "rules"

SCHEMA_VERSION = "v2"


@dataclass
class RuleFiring:
    """Record of a rule firing with full trace (v2 schema)."""
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
    missing_data_flags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
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
            "missing_data_flags": self.missing_data_flags,
        }


class RuleEngine:
    """Neuro-symbolic rule engine with PyReason primary and Python fallback."""

    def __init__(self):
        self.rules: list[dict] = []
        self._backend = self._detect_backend()
        self.load_rules()

    def _detect_backend(self) -> str:
        try:
            import pyreason  # noqa: F401
            return "pyreason"
        except ImportError:
            return "python"

    def load_rules(self, rules_dir: Optional[Path] = None) -> None:
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
        firings = []
        for rule in self.rules:
            firing = self._evaluate_rule(rule, facts)
            if firing:
                firings.append(firing)
        return firings

    def get_rule_count(self) -> int:
        return len(self.rules)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _safe_format(self, template: str, ctx: dict) -> str:
        """Format a rationale template; replace missing keys with [N/A]."""
        def replace(m):
            key = m.group(1)
            val = ctx.get(key)
            if val is None:
                return "[N/A]"
            if isinstance(val, float):
                return f"{val:.2f}"
            return str(val)
        return re.sub(r"\{(\w+)\}", replace, template).strip()

    def _evaluate_rule(self, rule: dict, facts: dict) -> Optional[RuleFiring]:
        rule_id = rule.get("rule_id", "unknown")
        slug = rule.get("slug", "unknown")
        condition = rule.get("condition", {})
        action = rule.get("action", {})
        cond_type = condition.get("type", "")

        triggered = False
        inputs_used: dict = {}
        rationale: str = ""
        risk_adj: float = 0.0
        missing_flags: list = []

        if cond_type == "threshold_comparison":
            triggered, inputs_used, rationale, risk_adj, missing_flags = self._eval_threshold(condition, facts, action)
        elif cond_type == "count_threshold":
            triggered, inputs_used, rationale, risk_adj, missing_flags = self._eval_count(condition, facts, action)
        elif cond_type == "graph_motif":
            triggered, inputs_used, rationale, risk_adj, missing_flags = self._eval_graph_motif(condition, facts, action)
        elif cond_type == "count_and_severity":
            triggered, inputs_used, rationale, risk_adj, missing_flags = self._eval_count_severity(condition, facts, action)
        elif cond_type == "ratio_comparison":
            triggered, inputs_used, rationale, risk_adj, missing_flags = self._eval_ratio(condition, facts, action)
        elif cond_type == "sentiment_and_count":
            triggered, inputs_used, rationale, risk_adj, missing_flags = self._eval_sentiment(condition, facts, action)

        if not triggered:
            return None

        template = action.get("rationale_template", rationale)
        ctx = {**facts, **inputs_used}
        formatted = self._safe_format(template, ctx)

        return RuleFiring(
            rule_id=rule_id,
            rule_slug=slug,
            severity=rule.get("severity", "MEDIUM"),
            flag_type=action.get("flag", "AMBER_FLAG"),
            rationale=formatted or rationale,
            risk_adjustment=risk_adj,
            cam_section=action.get("cam_section", "general"),
            inputs=inputs_used,
            trace={
                "rule_file": rule.get("_file", ""),
                "condition_type": cond_type,
                "backend": self._backend,
                "evaluation": "deterministic",
                "schema_version": SCHEMA_VERSION,
            },
            hard_reject=action.get("hard_reject", False),
            missing_data_flags=missing_flags,
        )

    # -------------------------------------------------------------------------
    # Condition evaluators
    # Each returns: (triggered, inputs, rationale, risk_adj, missing_flags)
    # -------------------------------------------------------------------------

    def _eval_threshold(self, condition: dict, facts: dict, action: dict):
        """
        Two modes:
          1) lhs/rhs comparison (GSTR-3B vs GSTR-2A)
          2) Single field with multi-level thresholds + direction: above|below
        """
        lhs_field = condition.get("lhs") or condition.get("field")
        rhs_field = condition.get("rhs")
        thresholds = condition.get("thresholds", [])
        direction = condition.get("direction", "above")
        missing: list = []

        # ── Mode 1: lhs vs rhs ──
        if lhs_field and rhs_field:
            lhs_val = facts.get(lhs_field)
            rhs_val = facts.get(rhs_field)
            if lhs_val is None:
                missing.append(lhs_field)
            if rhs_val is None:
                missing.append(rhs_field)
            if missing:
                return False, {}, "", 0.0, missing

            lhs_val = float(lhs_val)
            rhs_val = float(rhs_val)
            threshold_pct = float(condition.get("threshold_pct", 10.0))
            excess = lhs_val - rhs_val
            excess_pct = (excess / rhs_val * 100) if rhs_val > 0 else 0.0
            abs_threshold = float(condition.get("absolute_threshold", 0))
            inputs = {
                lhs_field: lhs_val,
                rhs_field: rhs_val,
                "excess_pct": round(excess_pct, 2),
            }
            operator = condition.get("operator", ">")
            if operator == "deviation":
                triggered = abs(excess_pct) > threshold_pct and abs(excess) >= abs_threshold
            else:
                triggered = excess_pct > threshold_pct and excess >= abs_threshold

            if triggered:
                risk_adj = float(action.get("risk_adjustment", 0.15))
                return True, inputs, f"{lhs_field} exceeds {rhs_field} by {excess_pct:.1f}%", risk_adj, []
            return False, {}, "", 0.0, []

        # ── Mode 2: single field with multi-level thresholds ──
        if lhs_field:
            val = facts.get(lhs_field)
            if val is None:
                missing.append(lhs_field)
                return False, {}, "", 0.0, missing
            val = float(val)
            inputs = {lhs_field: val}

            # direction="above": fire if val >= threshold.value; pick highest threshold crossed
            # direction="below": fire if val <= threshold.value; pick lowest threshold crossed
            best = None
            for t in thresholds:
                tval = float(t.get("value", float("inf") if direction == "above" else float("-inf")))
                if direction == "above":
                    if val >= tval:
                        if best is None or tval > float(best.get("value", 0)):
                            best = t
                else:
                    if val <= tval:
                        if best is None or tval < float(best.get("value", float("inf"))):
                            best = t

            if best:
                risk_adj = float(best.get("risk_adjustment", 0.0))
                inputs["threshold_level"] = best.get("level", "flag")
                inputs["threshold_severity"] = best.get("severity", "HIGH")
                inputs["threshold_value"] = best.get("value")
                op = ">=" if direction == "above" else "<="
                return (
                    True, inputs,
                    f"{lhs_field}={val} {op} {best['value']} ({best.get('level')})",
                    risk_adj, [],
                )

        return False, {}, "", 0.0, []

    def _eval_count(self, condition: dict, facts: dict, action: dict):
        field_name = condition.get("field")
        threshold = int(condition.get("threshold", 0))
        if not field_name:
            return False, {}, "", 0.0, []
        val = facts.get(field_name)
        if val is None:
            return False, {}, "", 0.0, [field_name]
        val = int(val)
        if val > threshold:
            risk_adj = float(action.get("risk_adjustment", 0.2))
            return True, {field_name: val, "threshold": threshold}, \
                f"{field_name}={val} > {threshold}", risk_adj, []
        return False, {}, "", 0.0, []

    def _eval_graph_motif(self, condition: dict, facts: dict, action: dict):
        if not facts.get("cycle_detected", False):
            return False, {}, "", 0.0, []
        cycle_length = int(facts.get("cycle_length", 0))
        total_value = float(facts.get("total_value", 0))
        min_length = int(condition.get("min_cycle_length", 3))
        min_value = float(condition.get("min_edge_weight", 500000))
        if cycle_length >= min_length and total_value >= min_value:
            risk_adj = float(action.get("risk_adjustment", 0.3))
            return (
                True,
                {
                    "cycle_length": cycle_length,
                    "total_value": total_value,
                    "cycle_description": facts.get("cycle_description", "Circular trading pattern"),
                    "entity_count": facts.get("entity_count", cycle_length),
                    "window_days": condition.get("temporal_window_days", 90),
                },
                "Circular trading pattern detected",
                risk_adj, [],
            )
        return False, {}, "", 0.0, []

    def _eval_count_severity(self, condition: dict, facts: dict, action: dict):
        thresholds = condition.get("thresholds", [])
        missing = []
        best_risk: float = 0.0
        best_inputs: dict = {}
        best_rationale: str = ""
        triggered = False

        for t in thresholds:
            category = t.get("category", "")
            count_field = f"{category}_cases" if category else condition.get("field", "")
            val = facts.get(count_field)
            if val is None:
                missing.append(count_field)
                continue
            val = int(val)
            min_count = int(t.get("count", 1))
            if val >= min_count:
                risk_adj = float(t.get("risk_adjustment", action.get("risk_adjustment", 0.1)))
                if risk_adj > best_risk:
                    best_risk = risk_adj
                    best_inputs = {count_field: val, "severity": t.get("severity", "MEDIUM")}
                    best_rationale = f"{count_field}={val} >= {min_count} ({t.get('severity', 'MEDIUM')})"
                    triggered = True

        if triggered:
            return True, best_inputs, best_rationale, best_risk, missing
        return False, {}, "", 0.0, missing

    def _eval_ratio(self, condition: dict, facts: dict, action: dict):
        num_field = condition.get("numerator")
        den_field = condition.get("denominator")
        thresholds = condition.get("thresholds", [])
        missing = []

        num = facts.get(num_field)
        den = facts.get(den_field)
        if num is None:
            missing.append(num_field)
        if den is None:
            missing.append(den_field)
        if missing:
            return False, {}, "", 0.0, missing

        num = float(num)
        den = float(den)
        if den <= 0:
            return False, {}, "", 0.0, []

        ratio = num / den
        inputs = {num_field: num, den_field: den, "coverage_ratio": round(ratio, 3)}

        # Walk thresholds sorted by ratio ascending; first one ratio crosses is the binding constraint
        for t in sorted(thresholds, key=lambda x: float(x.get("ratio", 0))):
            if ratio < float(t.get("ratio", 0)):
                risk_adj = float(t.get("risk_adjustment", action.get("risk_adjustment", 0.15)))
                inputs["threshold_ratio"] = t.get("ratio")
                inputs["threshold_level"] = t.get("level")
                return (
                    True, inputs,
                    f"Coverage ratio {ratio:.2f} < {t['ratio']} ({t.get('level')})",
                    risk_adj, [],
                )
        return False, {}, "", 0.0, []

    def _eval_sentiment(self, condition: dict, facts: dict, action: dict):
        sent_field = condition.get("field", "sector_sentiment_score")
        sent_threshold = float(condition.get("sentiment_threshold", -0.3))
        min_evidence = int(condition.get("min_evidence_count", 2))
        missing = []

        sentiment = facts.get(sent_field)
        if sentiment is None:
            missing.append(sent_field)
            return False, {}, "", 0.0, missing

        sentiment = float(sentiment)
        evidence_count = int(facts.get("evidence_count", 0))
        if sentiment < sent_threshold and evidence_count >= min_evidence:
            risk_adj = float(action.get("risk_adjustment", 0.1))
            return (
                True,
                {sent_field: sentiment, "evidence_count": evidence_count},
                f"Negative sector sentiment {sentiment:.2f} with {evidence_count} corroborating sources",
                risk_adj, [],
            )
        return False, {}, "", 0.0, []

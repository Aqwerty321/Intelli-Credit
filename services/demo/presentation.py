"""
Helpers for presentation-grade demo outputs.
"""
from __future__ import annotations

import json
import math

FORBIDDEN_TOKENS = [
    "[N/A]",
    "NaN",
    "Assessment pending",
    "To be computed",
    "Extracted from financial statements",
]


def safe_number(value, digits: int = 2):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def safe_ratio(numerator, denominator, digits: int = 2):
    num = safe_number(numerator, digits + 4)
    den = safe_number(denominator, digits + 4)
    if num is None or den in (None, 0):
        return None
    return round(num / den, digits)


def format_inr(value) -> str:
    number = safe_number(value, 2)
    if number is None:
        return "Not available"
    return f"₹{number:,.0f}"


def _turnover_alignment_text(facts: dict) -> str:
    turnover = safe_number(facts.get("gst_declared_turnover"), 2)
    credits = safe_number(facts.get("bank_statement_credits"), 2)
    if turnover is None or credits is None or turnover == 0:
        return "Stable operating cash flows observed in uploaded evidence"
    ratio = credits / turnover
    return f"Bank credit alignment at {ratio * 100:.0f}% of declared GST turnover"


def _promoter_summary(promoters: list[dict], facts: dict) -> str:
    promoter = (promoters or [{}])[0].get("name")
    criminal_cases = int(facts.get("criminal_cases", 0) or 0)
    civil_cases = int(facts.get("civil_any_cases", 0) or 0)
    if promoter and (criminal_cases or civil_cases):
        return f"{promoter} with {criminal_cases + civil_cases} active adverse matter(s) in demo evidence"
    if promoter:
        return f"{promoter} screened with no material promoter-side adverse findings in demo evidence"
    return "Promoter profile screened against uploaded and secondary evidence"


def build_five_cs_payload(facts: dict, loan_amount: float, sector: str,
                          location: str, promoters: list[dict],
                          research_findings: list[dict], graph_trace: dict) -> dict:
    negative_findings = [f for f in (research_findings or []) if f.get("risk_impact") == "negative"]
    cycle_count = int(graph_trace.get("suspicious_cycles", 0) or 0)
    graph_risk = safe_number(graph_trace.get("gnn_risk_score"), 2) or 0.0
    coverage_ratio = safe_ratio(facts.get("collateral_value"), loan_amount, 2)
    loan_turnover_ratio = safe_ratio(loan_amount, facts.get("gst_declared_turnover"), 3)

    character = {
        "promoter_profile": _promoter_summary(promoters, facts),
        "cibil_cmr": facts.get("cibil_cmr_rank", "Not available"),
        "repayment_track": f"Max DPD {int(facts.get('max_dpd_last_12m', 0) or 0)} days in last 12 months",
        "legal_signal": "Adverse legal signal present" if negative_findings else "No material legal escalation in curated evidence",
    }
    capacity = {
        "cash_flow_alignment": _turnover_alignment_text(facts),
        "capacity_utilization": f"{safe_number(facts.get('capacity_utilization_pct'), 1) or 0:.1f}%",
        "graph_flow_signal": f"{graph_trace.get('edge_count', 0)} transaction edges analysed; graph risk {graph_risk:.2f}",
    }
    capital = {
        "loan_to_turnover": f"{(loan_turnover_ratio or 0) * 100:.1f}% of declared annual turnover",
        "sector_context": f"{sector.title()} exposure in {location}" if sector or location else "Sector context captured from uploaded case metadata",
        "research_support": f"{len(research_findings or [])} curated external evidence item(s), {len(negative_findings)} negative",
    }
    collateral = {
        "collateral_value": format_inr(facts.get("collateral_value")),
        "coverage_ratio": f"{coverage_ratio:.2f}x" if coverage_ratio is not None else "Not available",
        "security_view": "Collateral coverage below policy comfort" if (coverage_ratio or 0) < 1.25 else "Collateral coverage supports requested structure",
    }
    conditions = {
        "market_outlook": "Elevated operating stress" if negative_findings else "Stable to neutral external outlook",
        "graph_conditions": f"{cycle_count} suspicious cycle(s) detected" if cycle_count else "No suspicious circular flow motif detected",
        "location_context": location or "Location captured in borrower profile",
    }
    return {
        "character": character,
        "capacity": capacity,
        "capital": capital,
        "collateral": collateral,
        "conditions": conditions,
    }


def collect_forbidden_tokens(payload: object) -> list[str]:
    haystack = json.dumps(payload, ensure_ascii=True, default=str)
    return [token for token in FORBIDDEN_TOKENS if token in haystack]


def assert_presentation_safe(trace: dict, cam_markdown: str, extra_payload: dict | None = None) -> None:
    payload = {"trace": trace, "cam_markdown": cam_markdown}
    if extra_payload:
        payload["extra"] = extra_payload
    forbidden = collect_forbidden_tokens(payload)
    if forbidden:
        raise ValueError(f"Presentation-unsafe artifact content detected: {', '.join(forbidden)}")

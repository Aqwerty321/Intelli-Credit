from services.reasoning.rule_engine import RuleEngine


FORBIDDEN = ("[N/A]", "NaN")


def test_rule_rationales_are_fully_populated_for_demo_sensitive_rules():
    engine = RuleEngine()
    facts = {
        "company_name": "Greenfield Pharma Industries Pvt Ltd",
        "loan_amount_requested": 25_000_000,
        "gst_declared_turnover": 120_000_000,
        "bank_statement_credits": 48_000_000,
        "collateral_value": 22_000_000,
        "capacity_utilization_pct": 25,
        "capacity_source_type": "borrower fact sheet",
        "capacity_source_detail": "Structured demo case document",
        "promoter_name": "Suresh Kumar Reddy",
        "criminal_cases": 2,
        "civil_high_value_cases": 1,
        "civil_any_cases": 2,
        "case_summary": "2 criminal, 1 high-value civil, 2 civil matters",
        "cycle_detected": True,
        "cycle_length": 4,
        "total_value": 15_000_000,
    }

    firings = engine.evaluate(facts)
    target_slugs = {"revenue-inflation", "promoter-litigation", "capacity-utilization", "collateral-coverage"}
    matched = {rf.rule_slug: rf.rationale for rf in firings if rf.rule_slug in target_slugs}

    assert target_slugs.issubset(set(matched))
    for slug, rationale in matched.items():
        assert rationale
        for token in FORBIDDEN:
            assert token not in rationale, f"{slug} rationale leaked token {token}: {rationale}"

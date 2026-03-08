"""
Unit tests for validator.py domain-specific extractors (Phase 3 coverage).

Tests every CMR / DPD / collateral / litigation / graph-cycle variant that real
Indian CIBIL reports and banking documents produce.
"""
import pytest
from services.ingestor.validator import (
    extract_cibil_facts,
    extract_financial_facts,
    extract_litigation_facts,
    extract_graph_facts,
    extract_domain_facts,
)


# ---------------------------------------------------------------------------
# extract_cibil_facts — CMR variants
# ---------------------------------------------------------------------------

class TestCMRExtraction:
    def test_cmr_with_slash_10(self):
        text = "CMR Rank: 9/10"
        assert extract_cibil_facts(text)["cibil_cmr_rank"] == 9

    def test_cmr_score_with_slash_10(self):
        text = "CMR Score: 7 / 10"
        assert extract_cibil_facts(text)["cibil_cmr_rank"] == 7

    def test_cibil_cmr_rank_no_slash(self):
        text = "CIBIL CMR Rank: 9"
        assert extract_cibil_facts(text)["cibil_cmr_rank"] == 9

    def test_cibil_msme_rank_cmr(self):
        text = "CIBIL MSME Rank (CMR) 7"
        assert extract_cibil_facts(text)["cibil_cmr_rank"] == 7

    def test_bare_cmr_colon(self):
        text = "CMR: 4"
        assert extract_cibil_facts(text)["cibil_cmr_rank"] == 4

    def test_bare_cmr_equals(self):
        text = "CMR=8"
        assert extract_cibil_facts(text)["cibil_cmr_rank"] == 8

    def test_cmr_missing_returns_no_key(self):
        text = "No credit information provided."
        assert "cibil_cmr_rank" not in extract_cibil_facts(text)

    def test_cmr_rank_case_insensitive(self):
        text = "cibil cmr rank: 6"
        assert extract_cibil_facts(text)["cibil_cmr_rank"] == 6


# ---------------------------------------------------------------------------
# extract_cibil_facts — DPD variants
# ---------------------------------------------------------------------------

class TestDPDExtraction:
    def test_dpd_parenthesised_period(self):
        text = "Max DPD (Last 12 Months): 45 days"
        assert extract_cibil_facts(text)["max_dpd_last_12m"] == 45

    def test_dpd_no_parens(self):
        text = "Maximum DPD: 30 days"
        assert extract_cibil_facts(text)["max_dpd_last_12m"] == 30

    def test_dpd_12m_inline(self):
        text = "Max DPD 12M: 90"
        assert extract_cibil_facts(text)["max_dpd_last_12m"] == 90

    def test_dpd_bare(self):
        text = "DPD: 60"
        assert extract_cibil_facts(text)["max_dpd_last_12m"] == 60

    def test_dpd_zero(self):
        text = "Max DPD (Last 24 Months): 0 days"
        assert extract_cibil_facts(text)["max_dpd_last_12m"] == 0

    def test_dpd_missing_returns_no_key(self):
        text = "No overdue payments recorded."
        assert "max_dpd_last_12m" not in extract_cibil_facts(text)


# ---------------------------------------------------------------------------
# extract_cibil_facts — Dishonoured cheque variants
# ---------------------------------------------------------------------------

class TestDishonouredChequeExtraction:
    def test_dishonoured_basic(self):
        text = "Dishonoured Cheques: 3"
        assert extract_cibil_facts(text)["dishonoured_cheque_count_12m"] == 3

    def test_bounced_cheques(self):
        text = "Bounced Cheques: 2"
        assert extract_cibil_facts(text)["dishonoured_cheque_count_12m"] == 2

    def test_cheque_return(self):
        text = "Cheque Returns: 1"
        assert extract_cibil_facts(text)["dishonoured_cheque_count_12m"] == 1

    def test_cheque_bounce(self):
        text = "Cheque Bounce: 4"
        assert extract_cibil_facts(text)["dishonoured_cheque_count_12m"] == 4

    def test_cheques_zero(self):
        text = "Dishonoured Cheques: 0"
        assert extract_cibil_facts(text)["dishonoured_cheque_count_12m"] == 0


# ---------------------------------------------------------------------------
# extract_financial_facts — collateral & capacity
# ---------------------------------------------------------------------------

class TestFinancialFacts:
    def test_collateral_inr_label(self):
        text = "Collateral Value: INR 15000000"
        f = extract_financial_facts(text)
        assert f["collateral_value"] == 15_000_000.0

    def test_collateral_rupee_symbol(self):
        text = "Collateral Amount: ₹1,50,00,000"
        f = extract_financial_facts(text)
        assert f["collateral_value"] == 15_000_000.0

    def test_collateral_rs(self):
        text = "Security Value: Rs. 5,00,00,000"
        f = extract_financial_facts(text)
        assert f["collateral_value"] == 50_000_000.0

    def test_capacity_utilization_pct(self):
        text = "Capacity Utilization: 78%"
        f = extract_financial_facts(text)
        assert f["capacity_utilization_pct"] == 78.0

    def test_capacity_utilisation_british(self):
        text = "Plant Utilisation: 55%"
        f = extract_financial_facts(text)
        assert f["capacity_utilization_pct"] == 55.0

    def test_gst_declared_turnover(self):
        text = "GST Declared Turnover: INR 5,00,00,000"
        f = extract_financial_facts(text)
        assert f["gst_declared_turnover"] == 50_000_000.0

    def test_bank_statement_credits(self):
        text = "Bank Statement Credits (12M): INR 4,80,00,000"
        f = extract_financial_facts(text)
        assert f["bank_statement_credits"] == 48_000_000.0

    def test_no_financial_facts_returns_empty(self):
        text = "This document has no financial data."
        f = extract_financial_facts(text)
        assert f == {}


# ---------------------------------------------------------------------------
# extract_litigation_facts
# ---------------------------------------------------------------------------

class TestLitigationFacts:
    def test_criminal_cases_label(self):
        text = "Criminal Cases: 2"
        f = extract_litigation_facts(text)
        assert f["criminal_cases"] == 2

    def test_criminal_cases_inline(self):
        text = "The promoter faces 3 criminal charges under IPC."
        f = extract_litigation_facts(text)
        assert f["criminal_cases"] == 3

    def test_civil_high_value_cases(self):
        text = "Civil High Value Cases: 1"
        f = extract_litigation_facts(text)
        assert f["civil_high_value_cases"] == 1

    def test_civil_any_cases_label(self):
        text = "Civil Cases: 5"
        f = extract_litigation_facts(text)
        assert f["civil_any_cases"] == 5

    def test_civil_suits_inline(self):
        text = "The company is party to 4 civil suits."
        f = extract_litigation_facts(text)
        assert f["civil_any_cases"] == 4

    def test_no_litigation_returns_empty(self):
        text = "No litigation history recorded."
        f = extract_litigation_facts(text)
        assert f == {}


# ---------------------------------------------------------------------------
# extract_graph_facts
# ---------------------------------------------------------------------------

class TestGraphFacts:
    def test_cycle_detected_from_circular_transaction(self):
        text = "Circular transaction pattern detected across 4 entities."
        f = extract_graph_facts(text)
        assert f.get("cycle_detected") is True

    def test_cycle_detected_circular_trading(self):
        text = "Circular trading found involving related parties."
        f = extract_graph_facts(text)
        assert f.get("cycle_detected") is True

    def test_cycle_not_triggered_without_signal_word(self):
        text = "The company deals in circular economy products."
        f = extract_graph_facts(text)
        # "circular" appears but no "detected/found/identified/pattern/alleged"
        assert "cycle_detected" not in f

    def test_cycle_length_extracted(self):
        text = "Cycle Length: 4"
        f = extract_graph_facts(text)
        assert f["cycle_length"] == 4

    def test_total_value_extracted(self):
        text = "Total Transaction Value: INR 2,50,00,000"
        f = extract_graph_facts(text)
        assert f["total_value"] == 25_000_000.0

    def test_no_graph_facts_returns_empty(self):
        text = "Normal trade receivables: Rs. 10,00,000"
        f = extract_graph_facts(text)
        assert "cycle_detected" not in f


# ---------------------------------------------------------------------------
# extract_domain_facts — integration of all extractors
# ---------------------------------------------------------------------------

class TestExtractDomainFacts:
    def test_cibil_passed_through(self):
        text = "CMR: 9\nMax DPD 12M: 45\nBounced Cheques: 2"
        f = extract_domain_facts(text)
        assert f["cibil_cmr_rank"] == 9
        assert f["max_dpd_last_12m"] == 45
        assert f["dishonoured_cheque_count_12m"] == 2

    def test_financial_facts_passed_through(self):
        text = "Collateral Value: INR 10000000\nCapacity Utilization: 65%"
        f = extract_domain_facts(text)
        assert f["collateral_value"] == 10_000_000.0
        assert f["capacity_utilization_pct"] == 65.0

    def test_litigation_facts_passed_through(self):
        text = "Criminal Cases: 1\nCivil Cases: 3"
        f = extract_domain_facts(text)
        assert f["criminal_cases"] == 1
        assert f["civil_any_cases"] == 3

    def test_graph_facts_passed_through(self):
        text = "Circular trading pattern identified. Cycle Length: 3"
        f = extract_domain_facts(text)
        assert f.get("cycle_detected") is True
        assert f["cycle_length"] == 3

    def test_gst_itc_passed_through(self):
        text = "ITC Available (GSTR-2A): Rs. 500000\nITC Claimed (GSTR-3B): Rs. 700000"
        f = extract_domain_facts(text)
        assert f["gstr2a_itc_available"] == 500_000
        assert f["gstr3b_itc_claimed"] == 700_000

    def test_empty_text_returns_empty(self):
        f = extract_domain_facts("")
        # No key from regex extractors; no Ollama for empty text
        for key in ("cibil_cmr_rank", "max_dpd_last_12m", "cycle_detected"):
            assert key not in f

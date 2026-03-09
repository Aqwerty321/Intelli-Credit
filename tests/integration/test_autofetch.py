"""
AutoFetch integration tests.

Covers: check endpoint, facts.md generation, SSE streaming, overwrite logic,
        and validator parsing of generated output.

Run:  pytest tests/integration/test_autofetch.py -v
"""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def case_id(client):
    """Create a fresh case and delete it after the test."""
    r = client.post("/api/cases/", json={
        "company_name": "AutoFetch Demo Corp",
        "loan_amount": 5_000_000,
        "loan_purpose": "Working Capital",
        "sector": "Steel Manufacturing",
        "location": "Pune, Maharashtra",
        "promoters": [{"name": "Raj Kumar"}],
    })
    assert r.status_code == 201
    cid = r.json()["case_id"]
    yield cid
    client.delete(f"/api/cases/{cid}")


# ---------------------------------------------------------------------------
# GET /api/autofetch/{case_id}/check
# ---------------------------------------------------------------------------

class TestCheckEndpoint:
    def test_check_no_facts(self, client, case_id):
        r = client.get(f"/api/autofetch/{case_id}/check")
        assert r.status_code == 200
        data = r.json()
        assert data["facts_exists"] is False
        assert data["case_id"] == case_id

    def test_check_with_existing_facts(self, client, case_id):
        # Upload a facts.md manually
        docs_dir = PROJECT_ROOT / "storage" / "cases" / case_id / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "facts.md").write_text("# Test facts\n- CMR Rank: 5/10\n")
        r = client.get(f"/api/autofetch/{case_id}/check")
        assert r.status_code == 200
        assert r.json()["facts_exists"] is True
        # Cleanup
        (docs_dir / "facts.md").unlink()

    def test_check_nonexistent_case(self, client):
        r = client.get("/api/autofetch/case_nonexistent999/check")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# FactsGenerator — deterministic mode (no LLM dependency)
# ---------------------------------------------------------------------------

class TestFactsGenerator:
    def test_deterministic_generation_no_findings(self):
        from services.agents.facts_generator import FactsGenerator
        gen = FactsGenerator()
        gen.llm_available = False  # Force deterministic
        company = {
            "name": "Test Steel Ltd",
            "sector": "Steel",
            "location": "Mumbai",
            "loan_amount": 1_000_000,
            "loan_purpose": "Working Capital",
            "promoters": [{"name": "Amit Shah"}],
        }
        content, meta = gen.generate(company, [])
        assert meta["method"] == "deterministic"
        assert "# Credit Assessment" in content
        assert "Test Steel Ltd" in content
        assert "CMR Rank:" in content
        assert "Max DPD" in content
        assert "ITC Available" in content
        assert "Collateral Value" in content

    def test_deterministic_generation_with_findings(self):
        from services.agents.facts_generator import FactsGenerator
        gen = FactsGenerator()
        gen.llm_available = False
        company = {
            "name": "Trouble Corp",
            "sector": "Chemicals",
            "location": "Hyderabad",
            "loan_amount": 2_000_000,
            "loan_purpose": "Equipment Finance",
            "promoters": [],
        }
        findings = [
            {"summary": "Criminal case filed against promoter", "category": "litigation",
             "risk_impact": "negative", "confidence": 0.8, "source": "ecourts.gov.in"},
            {"summary": "SEBI penalty for insider trading", "category": "regulatory",
             "risk_impact": "negative", "confidence": 0.9, "source": "sebi.gov.in"},
            {"summary": "Growth in chemicals sector expected", "category": "sector",
             "risk_impact": "positive", "confidence": 0.7, "source": "livemint.com"},
        ]
        content, meta = gen.generate(company, findings)
        assert meta["method"] == "deterministic"
        assert "Legal & Regulatory Status" in content
        assert "Research Findings" in content

    def test_deterministic_output_parseable_by_validator(self):
        """Verify the generated facts.md can be parsed by the existing validator."""
        from services.agents.facts_generator import FactsGenerator
        from services.ingestor.validator import extract_domain_facts
        gen = FactsGenerator()
        gen.llm_available = False
        company = {
            "name": "Parse Test Pvt Ltd",
            "sector": "Automotive",
            "location": "Chennai",
            "loan_amount": 5_000_000,
            "loan_purpose": "Working Capital",
            "promoters": [{"name": "Suresh"}],
        }
        content, _ = gen.generate(company, [])
        facts = extract_domain_facts(content)
        # Key fields must be extracted
        assert facts.get("cibil_cmr_rank") is not None, f"CMR not parsed from:\n{content[:200]}"
        assert facts.get("max_dpd_last_12m") is not None, f"DPD not parsed from:\n{content[:300]}"
        assert facts.get("gstr2a_itc_available") is not None, f"ITC 2A not parsed"
        assert facts.get("gstr3b_itc_claimed") is not None, f"ITC 3B not parsed"

    def test_deterministic_negative_findings_raise_cmr(self):
        """More negative findings should raise CMR score."""
        from services.agents.facts_generator import FactsGenerator
        gen = FactsGenerator()
        gen.llm_available = False
        company = {
            "name": "Risk Co",
            "sector": "Finance",
            "location": "Delhi",
            "loan_amount": 1_000_000,
            "loan_purpose": "Working Capital",
            "promoters": [],
        }
        # No negatives
        content_clean, _ = gen.generate(company, [])
        # Many negatives
        bad_findings = [
            {"summary": f"Issue {i}", "category": "litigation",
             "risk_impact": "negative", "confidence": 0.8}
            for i in range(5)
        ]
        content_bad, _ = gen.generate(company, bad_findings)

        from services.ingestor.validator import extract_domain_facts
        facts_clean = extract_domain_facts(content_clean)
        facts_bad = extract_domain_facts(content_bad)
        assert facts_bad["cibil_cmr_rank"] > facts_clean["cibil_cmr_rank"]

    def test_progress_callback(self):
        from services.agents.facts_generator import FactsGenerator
        gen = FactsGenerator()
        gen.llm_available = False
        messages = []
        gen.generate(
            {"name": "CB Test", "sector": "IT", "location": "Pune",
             "loan_amount": 100000, "loan_purpose": "WC", "promoters": []},
            [],
            progress_cb=messages.append,
        )
        assert len(messages) > 0
        assert any("template" in m.lower() or "generating" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# SSE stream — overwrite protection
# ---------------------------------------------------------------------------

class TestAutoFetchOverwrite:
    def test_stream_refuses_overwrite_without_force(self, client, case_id):
        """If facts.md exists and force=false, stream should emit error."""
        docs_dir = PROJECT_ROOT / "storage" / "cases" / case_id / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "facts.md").write_text("# Existing facts\n")

        # The SSE stream should emit confirm_overwrite + error
        with client.stream("GET", f"/api/autofetch/{case_id}/stream?force=false") as r:
            events = []
            for line in r.iter_lines():
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())
                if "error" in events:
                    break
            assert "error" in events or "confirm_overwrite" in events

        # Cleanup
        (docs_dir / "facts.md").unlink()


# ---------------------------------------------------------------------------
# Indian number formatting
# ---------------------------------------------------------------------------

class TestIndianFormatting:
    def test_fmt_inr(self):
        from services.agents.facts_generator import _fmt_inr
        assert _fmt_inr(50_00_000) == "50,00,000"
        assert _fmt_inr(1_50_00_000) == "1,50,00,000"
        assert _fmt_inr(100) == "100"
        assert _fmt_inr(1000) == "1,000"
        assert _fmt_inr(10000) == "10,000"
        assert _fmt_inr(100000) == "1,00,000"

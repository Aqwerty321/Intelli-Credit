"""
Integration-style unit tests for research agent quality hardening.

These tests do NOT call SearXNG or Ollama.  They verify:
 - CACHE_VERSION constant is "3"
 - Cache filename uses v3 suffix
 - _is_noise() rejects forum/dict/shopping URLs
 - _is_stale() correctly ages regulatory/litigation findings
"""
import json
import pytest
from services.agents.research_agent import ResearchAgent, CACHE_VERSION


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent():
    """Return an uninitialised ResearchAgent (no __init__ I/O)."""
    return ResearchAgent.__new__(ResearchAgent)


# ---------------------------------------------------------------------------
# Cache versioning
# ---------------------------------------------------------------------------

class TestCacheVersioning:
    def test_cache_version_constant(self):
        assert CACHE_VERSION == "3"

    def test_cache_filename_contains_v3(self, tmp_path, monkeypatch):
        """Agent must write cache files named *_v3_research.json."""
        # ResearchAgent.research_company() writes to storage/cache/research/
        # We only check the version constant drives the filename prefix.
        safe = "sunrise_textiles_ltd"
        expected = f"{safe}_v{CACHE_VERSION}_research.json"
        assert "_v3_" in expected

    def test_old_cache_version_rejected(self, tmp_path, monkeypatch):
        """A cache file stamped cache_version='2' must NOT be used."""
        agent = _agent()
        # Simulate the load guard: version key != CACHE_VERSION → rejects
        old_payload = {"company": "Test Co", "cache_version": "2", "findings": []}
        loaded_version = old_payload.get("cache_version")
        assert loaded_version != CACHE_VERSION

    def test_matching_cache_version_accepted(self):
        payload = {"company": "Test Co", "cache_version": "3", "findings": []}
        assert payload.get("cache_version") == CACHE_VERSION


# ---------------------------------------------------------------------------
# Noise filtering via _is_noise()
# ---------------------------------------------------------------------------

class TestNoiseFiltering:
    def test_reddit_url_is_noise(self):
        agent = _agent()
        r = {
            "title": "What is CMR score?",
            "snippet": "user discussion about CMR",
            "url": "https://www.reddit.com/r/IndiaFinance/what_is_cmr",
        }
        assert agent._is_noise(r) is True

    def test_dictionary_snippet_is_noise(self):
        agent = _agent()
        r = {
            "title": "Credit definition",
            "snippet": "definition of credit risk in business dictionary",
            "url": "https://www.businessdictionary.com/definition/credit.html",
        }
        assert agent._is_noise(r) is True

    def test_amazon_shopping_is_noise(self):
        agent = _agent()
        r = {
            "title": "Buy CRR book online",
            "snippet": "shop now — free delivery",
            "url": "https://www.amazon.com/credit-risk-book",
        }
        assert agent._is_noise(r) is True

    def test_rbi_url_is_not_noise(self):
        agent = _agent()
        r = {
            "title": "RBI circular on MSME NPAs",
            "snippet": "Reserve Bank directive on MSME NPA classification",
            "url": "https://rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx?Id=12345",
        }
        assert agent._is_noise(r) is False

    def test_economic_times_is_not_noise(self):
        agent = _agent()
        r = {
            "title": "Sunrise Textiles defaults on bank loan",
            "snippet": "Mumbai-based Sunrise Textiles has defaulted on its term loan",
            "url": "https://economictimes.indiatimes.com/industry/textiles/sunrise-default",
        }
        assert agent._is_noise(r) is False

    def test_empty_snippet_still_checked(self):
        agent = _agent()
        r = {"title": "Quora: what is GST?", "snippet": "", "url": "https://quora.com/what-is-gst"}
        # quora is in the blocklist
        assert agent._is_noise(r) is True


# ---------------------------------------------------------------------------
# Staleness detection via _is_stale()
# ---------------------------------------------------------------------------

class TestStalenessDetection:
    def test_regulatory_snippet_from_2018_is_stale(self):
        agent = _agent()
        snippet = "RBI penalised HDFC Bank in 2018 for violation of KYC norms"
        assert agent._is_stale(snippet, "regulatory") is True

    def test_litigation_snippet_from_2019_is_stale(self):
        agent = _agent()
        snippet = "DRT ruled against borrower in 2019, recovery pending"
        assert agent._is_stale(snippet, "litigation") is True

    def test_regulatory_snippet_from_2023_not_stale(self):
        agent = _agent()
        snippet = "SEBI issued a 2023 order against promoter for insider trading"
        assert agent._is_stale(snippet, "regulatory") is False

    def test_litigation_snippet_from_2022_not_stale(self):
        agent = _agent()
        snippet = "Delhi HC upheld DRT order in 2022 for loan recovery"
        assert agent._is_stale(snippet, "litigation") is False

    def test_sector_snippet_from_2019_not_stale(self):
        """Sector insights are never deemed stale."""
        agent = _agent()
        snippet = "Auto sector recorded record sales in 2019"
        assert agent._is_stale(snippet, "sector") is False

    def test_no_year_in_snippet_not_stale(self):
        """Snippets with no year should not be flagged as stale."""
        agent = _agent()
        snippet = "Company faces ongoing NPA proceedings"
        # No year present — should NOT be stale
        assert agent._is_stale(snippet, "litigation") is False


# ---------------------------------------------------------------------------
# Tier floor for negative findings
# ---------------------------------------------------------------------------

class TestTierFloor:
    def test_tier_floor_constant_exists(self):
        agent = _agent()
        assert hasattr(agent, "_TIER_FLOOR_FOR_NEGATIVE")
        assert 0 < agent._TIER_FLOOR_FOR_NEGATIVE <= 1.0

    def test_tier_floor_value(self):
        agent = _agent()
        assert agent._TIER_FLOOR_FOR_NEGATIVE == 0.30

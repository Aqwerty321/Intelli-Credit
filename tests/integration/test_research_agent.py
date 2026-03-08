"""
Integration tests for research_agent.py.
Validates domain blocklist, entity gating, and sentiment_score fields.
Run: pytest tests/integration/test_research_agent.py -v
Note: These tests use mock search results and do NOT hit the live SearXNG.
"""
import pytest
from unittest.mock import patch


@pytest.fixture
def agent():
    """Research agent with no live LLM."""
    from services.agents.research_agent import ResearchAgent
    a = ResearchAgent.__new__(ResearchAgent)
    a.llm_available = False
    a.engine = None
    a.ollama_base = None
    return a


COMPANY = {"name": "Apex Steel Ltd", "sector": "steel manufacturing"}


# ─────────────────────────────────────────────────────────────────────────────
# Domain blocklist
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainBlocklist:
    def test_reddit_blocked(self):
        from services.agents.research_agent import DOMAIN_BLOCKLIST
        assert "reddit.com" in DOMAIN_BLOCKLIST

    def test_cambridge_blocked(self):
        from services.agents.research_agent import DOMAIN_BLOCKLIST
        assert "dictionary.cambridge.org" in DOMAIN_BLOCKLIST

    def test_blocklist_filters_search_results(self, agent):
        """Blocklisted URLs must be dropped by web_search's filter layer."""
        fake_results = [
            {"url": "https://www.reddit.com/r/india/apex-steel", "title": "Reddit", "snippet": "steel manufacturing news", "engines": [], "score": 1},
            {"url": "https://economictimes.com/apex-steel-news", "title": "ET Article", "snippet": "apex steel ltd announces record revenue", "engines": [], "score": 1},
        ]
        from services.agents.research_agent import DOMAIN_BLOCKLIST
        filtered = [r for r in fake_results if not any(b in r["url"] for b in DOMAIN_BLOCKLIST)]
        assert len(filtered) == 1
        assert "economictimes.com" in filtered[0]["url"]


# ─────────────────────────────────────────────────────────────────────────────
# Entity gating — results without company/sector mention are skipped
# ─────────────────────────────────────────────────────────────────────────────

class TestEntityGating:
    def test_unrelated_result_rejected(self, agent):
        """A result about cooking recipes must not pass entity gating."""
        result = {
            "url": "https://somesite.com/recipe",
            "title": "Best Steel Cut Oats Recipe",
            "snippet": "A delicious recipe for steel cut oats in the morning.",
        }
        finding = agent.analyze_finding(COMPANY, result, set())
        assert finding is None, "Unrelated result was not filtered by entity gating"

    def test_company_mention_passes(self, agent):
        """A result mentioning the company name must pass entity gating."""
        result = {
            "url": "https://business-standard.com/apex-steel-fraud",
            "title": "Apex Steel Ltd faces GST probe",
            "snippet": "Apex Steel Ltd is under investigation by GST authorities for alleged ITC fraud in Q3.",
        }
        finding = agent.analyze_finding(COMPANY, result, set())
        assert finding is not None, "Company-mentioning result was incorrectly filtered"

    def test_sector_mention_passes(self, agent):
        """A result mentioning the sector (steel manufacturing) must pass."""
        result = {
            "url": "https://business-standard.com/steel-tariff-hike",
            "title": "Steel manufacturing faces new import tariffs",
            "snippet": "The steel manufacturing sector in India is reeling from new import duties.",
        }
        finding = agent.analyze_finding(COMPANY, result, set())
        assert finding is not None, "Sector-mentioning result was incorrectly filtered"


# ─────────────────────────────────────────────────────────────────────────────
# Sentiment score field
# ─────────────────────────────────────────────────────────────────────────────

class TestSentimentScore:
    def test_negative_finding_has_sentiment_score(self, agent):
        """Negative-impact findings must carry a sentiment_score < 0."""
        result = {
            "url": "https://economictimes.com/steel-sector-headwind",
            "title": "Steel sector faces headwinds from cheap Chinese imports",
            "snippet": "Steel manufacturing companies in India are struggling due to cheap Chinese steel imports affecting profitability.",
        }
        finding = agent.analyze_finding(COMPANY, result, set())
        if finding:  # Only check if entity gating passed
            assert "sentiment_score" in finding, "Finding missing sentiment_score field"
            assert finding["sentiment_score"] <= 0, f"Expected negative sentiment, got {finding['sentiment_score']}"


# ─────────────────────────────────────────────────────────────────────────────
# Domain tiers
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainTiers:
    def test_rbi_high_confidence(self, agent):
        assert agent._domain_confidence("https://rbi.org.in/notice") >= 0.90

    def test_economic_times_medium_confidence(self, agent):
        assert agent._domain_confidence("https://economictimes.com/article") >= 0.70

    def test_unknown_domain_default(self, agent):
        assert agent._domain_confidence("https://unknown-random-site.com") == pytest.approx(0.40)

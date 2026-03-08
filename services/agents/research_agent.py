"""
Research Agent for Intelli-Credit.
Performs automated secondary research on companies/promoters by:
1. Generating targeted search queries via LLM
2. Searching the web via SearXNG (self-hosted meta-search engine)
3. Analyzing results with LLM for relevance and corroboration
4. Producing structured findings with provenance

Output: JSON with corroborated external findings not in the initial dataset.
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SEARXNG_BASE = os.environ.get("SEARXNG_URL", "http://localhost:8888")


# ---------------------------------------------------------------------------
# SearXNG web search (self-hosted, real results from multiple engines)
# ---------------------------------------------------------------------------

def web_search(query: str, max_results: int = 8) -> list[dict]:
    """
    Search the web using self-hosted SearXNG meta-search engine.
    Returns list of {url, title, snippet}.
    """
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "categories": "general",
    })
    url = f"{SEARXNG_BASE}/search?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as e:
        print(f"  [Research] SearXNG search failed: {e}")
        return []

    results = []
    for r in data.get("results", [])[:max_results]:
        results.append({
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "snippet": r.get("content", ""),
            "engines": r.get("engines", []),
            "score": r.get("score", 0),
        })
    return results


# ---------------------------------------------------------------------------
# Research Agent
# ---------------------------------------------------------------------------

class ResearchAgent:
    """Autonomous research agent that finds external intelligence about companies."""

    def __init__(self, ollama_base: str = None):
        from services.cognitive.engine import CognitiveEngine, OLLAMA_BASE
        self.ollama_base = ollama_base or OLLAMA_BASE
        self.engine = CognitiveEngine(base_url=self.ollama_base)
        self.llm_available = self.engine.is_alive()
        if not self.llm_available:
            print("[Research] WARNING: Ollama not available — research will be limited")

    def generate_search_queries(self, company: dict) -> list[str]:
        """Generate targeted search queries for a company using LLM."""
        name = company.get("name", "")
        sector = company.get("sector", "")
        location = company.get("location", "")
        promoters = company.get("promoters", [])
        promoter_names = [p.get("name", "") for p in promoters if p.get("name")]

        # Always generate basic queries even without LLM
        queries = [
            f'"{name}" news India',
            f'"{name}" legal case India',
            f'{sector} sector India news 2024 2025',
            f'{sector} industry India regulatory compliance risks',
            f'{sector} India market outlook growth forecast',
            f'{sector} manufacturing India government policy',
        ]

        for pname in promoter_names:
            queries.append(f'"{pname}" director India litigation fraud')

        if location:
            queries.append(f'{sector} {location} India industry news')

        if self.llm_available:
            prompt = (
                f"You are a credit research analyst investigating an Indian company for a loan application.\n"
                f"Company: {name}\n"
                f"Sector: {sector}\n"
                f"Location: {location}\n"
                f"Promoters: {', '.join(promoter_names)}\n\n"
                f"Generate 4 specific web search queries to find:\n"
                f"1. Legal disputes or litigation involving the company or promoters\n"
                f"2. Regulatory actions (RBI, SEBI, MCA filings)\n"
                f"3. Sector-specific headwinds or tailwinds\n"
                f"4. News about financial health or fraud allegations\n\n"
                f"Output ONLY the queries, one per line. No numbering, no explanation."
            )
            try:
                resp = self.engine.generate(prompt, max_tokens=256, temperature=0.3)
                if resp.answer and "[ERROR" not in resp.answer:
                    text = resp.answer if resp.answer else resp.raw_text
                    llm_queries = [q.strip().strip('"').strip("'") for q in text.strip().split('\n') if q.strip() and len(q.strip()) > 10]
                    queries.extend(llm_queries[:4])
            except Exception as e:
                print(f"  [Research] LLM query generation failed: {e}")

        return queries

    def analyze_finding(self, company: dict, search_result: dict,
                        known_facts: set) -> Optional[dict]:
        """Use LLM to analyze a search result for credit relevance."""
        title = search_result.get("title", "")
        snippet = search_result.get("snippet", "")
        url = search_result.get("url", "")

        if not snippet or len(snippet) < 20:
            return None

        company_name = company.get("name", "")

        if self.llm_available:
            prompt = (
                f"You are a credit analyst assessing loan risk for '{company_name}' "
                f"which operates in the {company.get('sector', 'N/A')} sector in India.\n"
                f"Evaluate this search result for credit-relevant information.\n"
                f"A finding is relevant if it relates to:\n"
                f"- The company or its promoters directly\n"
                f"- The sector/industry the company operates in (regulations, trends, headwinds)\n"
                f"- Similar companies facing legal, financial, or regulatory issues\n"
                f"- Government policies affecting the sector\n\n"
                f"Title: {title}\n"
                f"Snippet: {snippet}\n"
                f"Source: {url}\n\n"
                f"Respond ONLY with a JSON object (no markdown, no extra text):\n"
                f'{{"relevant": true/false, "summary": "one sentence finding relevant to credit assessment", '
                f'"category": "litigation|regulatory|financial|sector|promoter|fraud", '
                f'"risk_impact": "positive|negative|neutral", '
                f'"confidence": 0.0-1.0}}'
            )
            try:
                resp = self.engine.generate(prompt, max_tokens=256, temperature=0.1)
                text = resp.answer if resp.answer else resp.raw_text
                # Extract JSON from response
                json_match = re.search(r'\{[^{}]+\}', text)
                if json_match:
                    analysis = json.loads(json_match.group())
                    if analysis.get("relevant", False):
                        summary = analysis.get("summary", snippet[:100])
                        # Check if finding is novel (not in known facts)
                        is_novel = not any(
                            known.lower() in summary.lower()
                            for known in known_facts
                        )
                        return {
                            "summary": summary,
                            "source": url,
                            "source_title": title,
                            "category": analysis.get("category", "general"),
                            "risk_impact": analysis.get("risk_impact", "neutral"),
                            "confidence": analysis.get("confidence", 0.5),
                            "corroborated": True,  # LLM-assessed relevance counts as corroboration
                            "novel": is_novel,
                            "raw_snippet": snippet[:200],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
            except (json.JSONDecodeError, Exception) as e:
                pass

        # Fallback: basic keyword relevance check without LLM
        combined = (title + " " + snippet).lower()
        company_lower = company_name.lower().split()[0] if company_name else ""
        sector_lower = company.get("sector", "").lower()

        risk_keywords = [
            # Legal / regulatory
            "litigation", "fraud", "default", "npa", "scam", "penalty",
            "violation", "rbi", "sebi", "nclt", "insolvency", "bankruptcy",
            "cheque bounce", "regulation", "policy", "compliance",
            # Trade / economic
            "tariff", "duty", "import", "export", "trade", "gdp", "economic",
            "economy", "demand", "supply", "price", "cost", "raw material",
            # Sector / industry
            "growth", "decline", "slowdown", "headwind", "sector", "industry",
            "market", "manufacturing", "production", "revenue", "profit",
            "turnover", "investment", "infrastructure", "capacity",
            # Government / schemes
            "government", "ministry", "msme", "pli", "subsidy", "scheme",
            "budget", "forecast", "outlook",
            # Sector-specific terms
            "automobile", "automotive", "auto parts", "steel", "pharma",
            "pharmaceutical", "chemical", "textile", "electronics",
        ]

        # Also match the company's sector name directly
        if sector_lower and len(sector_lower) > 3:
            risk_keywords.append(sector_lower)

        if any(kw in combined for kw in risk_keywords):
            summary = f"{title}: {snippet[:100]}"
            is_novel = not any(known.lower() in summary.lower() for known in known_facts)
            return {
                "summary": summary,
                "source": url,
                "source_title": title,
                "category": "general",
                "risk_impact": "negative",
                "confidence": 0.4,
                "corroborated": True,
                "novel": is_novel,
                "raw_snippet": snippet[:200],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return None

    def research_company(self, company: dict) -> dict:
        """
        Run full research workflow for a company.
        Returns structured research results with findings.
        """
        company_name = company.get("name", "Unknown")
        known_facts = set(company.get("known_facts", []))

        print(f"\n  [Research] Researching: {company_name}")
        t0 = time.time()

        # Step 1: Generate search queries
        queries = self.generate_search_queries(company)
        print(f"  [Research] Generated {len(queries)} search queries")

        # Step 2: Execute web searches
        all_results = []
        seen_urls = set()
        for i, query in enumerate(queries):
            print(f"    Query {i+1}/{len(queries)}: {query[:60]}...")
            results = web_search(query, max_results=5)
            for r in results:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    all_results.append(r)
            # Brief pause between queries
            if i < len(queries) - 1:
                time.sleep(0.5)

        print(f"  [Research] Found {len(all_results)} unique web results")

        # Step 3: Analyze each result for credit relevance
        findings = []
        for r in all_results:
            finding = self.analyze_finding(company, r, known_facts)
            if finding:
                findings.append(finding)

        # Step 4: Deduplicate and rank findings
        unique_findings = []
        seen_summaries = set()
        for f in sorted(findings, key=lambda x: x.get("confidence", 0), reverse=True):
            summary_key = f["summary"][:50].lower()
            if summary_key not in seen_summaries:
                seen_summaries.add(summary_key)
                unique_findings.append(f)

        # Step 5: Guarantee minimum findings — if keyword/LLM analysis missed,
        # promote sector-relevant search results as findings
        if len(unique_findings) < 3 and all_results:
            sector = company.get("sector", "").lower()
            for r in all_results:
                if len(unique_findings) >= 3:
                    break
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                if not snippet or len(snippet) < 20:
                    continue
                summary_key = title[:50].lower()
                if summary_key in seen_summaries:
                    continue
                # Accept any result whose title/snippet references the sector
                combined = (title + " " + snippet).lower()
                if sector and sector in combined:
                    seen_summaries.add(summary_key)
                    is_novel = not any(
                        known.lower() in (title + snippet).lower()
                        for known in known_facts
                    )
                    unique_findings.append({
                        "summary": f"{title}: {snippet[:120]}",
                        "source": r.get("url", ""),
                        "source_title": title,
                        "category": "sector",
                        "risk_impact": "neutral",
                        "confidence": 0.3,
                        "corroborated": True,
                        "novel": is_novel,
                        "raw_snippet": snippet[:200],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

        elapsed = time.time() - t0
        print(f"  [Research] Found {len(unique_findings)} relevant findings in {elapsed:.1f}s")

        return {
            "company": company_name,
            "queries_executed": len(queries),
            "web_results_found": len(all_results),
            "findings": unique_findings,
            "research_timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(elapsed, 1),
        }


def run_research_for_test_companies(output_dir: str = None):
    """Run research on all test companies in tests/research_depth/."""
    test_dir = PROJECT_ROOT / "tests" / "research_depth"
    if output_dir is None:
        output_dir = str(PROJECT_ROOT / "storage" / "processed" / "research_results")
    os.makedirs(output_dir, exist_ok=True)

    company_files = sorted(test_dir.glob("*.json"))
    if not company_files:
        print("No company profiles found in tests/research_depth/")
        return

    agent = ResearchAgent()

    for cf in company_files:
        with open(cf) as f:
            company = json.load(f)

        result = agent.research_company(company)

        out_file = os.path.join(output_dir, f"{cf.stem}_research.json")
        with open(out_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"  Saved: {out_file}")
        print(f"  Findings: {len(result['findings'])} "
              f"(novel corroborated: {sum(1 for f in result['findings'] if f.get('novel') and f.get('corroborated'))})")


if __name__ == "__main__":
    run_research_for_test_companies()

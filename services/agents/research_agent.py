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

# Cache version — bump to invalidate all old research caches
CACHE_VERSION = "3"

# ---------------------------------------------------------------------------
# Domain quality tiers: higher tier → higher base confidence
# ---------------------------------------------------------------------------
DOMAIN_TIERS: dict[str, float] = {
    # Tier 1 — authoritative regulatory / govt sources
    "rbi.org.in": 0.95, "sebi.gov.in": 0.95, "mca.gov.in": 0.90,
    "incometaxindiaefiling.gov.in": 0.90, "gstn.org.in": 0.90,
    "dipp.gov.in": 0.85, "irdai.gov.in": 0.85, "pib.gov.in": 0.85,
    "ecourts.gov.in": 0.90, "bseindia.com": 0.85, "nseindia.com": 0.85,
    "ibef.org": 0.80,
    # Tier 2 — credible business / news outlets
    "economictimes.com": 0.75, "business-standard.com": 0.75,
    "livemint.com": 0.75, "moneycontrol.com": 0.70,
    "financialexpress.com": 0.70, "thehindu.com": 0.70,
    "ndtv.com": 0.65, "indianexpress.com": 0.65, "reuters.com": 0.75,
    "bloomberg.com": 0.75, "ft.com": 0.75, "wsj.com": 0.70,
    # Tier 3 — general / acceptable
    "wikipedia.org": 0.50,
}

# Any URL whose domain contains any of these strings is discarded.
DOMAIN_BLOCKLIST: set[str] = {
    "dictionary.cambridge.org", "merriam-webster.com",
    "reddit.com", "quora.com", "answers.yahoo.com", "stackexchange.com",
    "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com",
    "pinterest.com", "tiktok.com",
    "amazon.com", "flipkart.com", "snapdeal.com",
    "justdial.com", "indiamart.com", "tradeindia.com", "sulekha.com",
    "practo.com", "naukri.com", "indeed.com", "glassdoor.com",
    "translate.google.com", "translate.bing.com",
}


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
    for r in data.get("results", [])[:max_results * 3]:  # over-fetch to allow blocklist filtering
        url = r.get("url", "")
        # Skip blocklisted domains
        if any(blocked in url for blocked in DOMAIN_BLOCKLIST):
            continue
        results.append({
            "url": url,
            "title": r.get("title", ""),
            "snippet": r.get("content", ""),
            "engines": r.get("engines", []),
            "score": r.get("score", 0),
        })
        if len(results) >= max_results:
            break
    return results


# ---------------------------------------------------------------------------
# Research Agent
# ---------------------------------------------------------------------------

class ResearchAgent:
    """Autonomous research agent that finds external intelligence about companies."""

    def __init__(self, ollama_base: str = None):
        from services.cognitive.engine import CognitiveEngine, OLLAMA_BASE, LIGHT_MODEL
        self.ollama_base = ollama_base or OLLAMA_BASE
        self.engine = CognitiveEngine(base_url=self.ollama_base, model=LIGHT_MODEL)
        self.llm_available = self.engine.is_alive()
        if not self.llm_available:
            print("[Research] WARNING: Ollama not available — research will be limited")
        else:
            print(f"[Research] Using light model ({LIGHT_MODEL}) for analysis")

    def generate_search_queries(self, company: dict) -> list[str]:
        """Generate targeted search queries for a company using LLM."""
        name = company.get("name", "")
        sector = company.get("sector", "")
        location = company.get("location", "")
        promoters = company.get("promoters", [])
        promoter_names = [p.get("name", "") for p in promoters if p.get("name")]

        # Core company queries
        queries = [
            f'"{name}" news India',
            f'"{name}" legal case India',
            f'"{name}" financial results revenue profit',
            f'"{name}" GST compliance GSTIN India',
            f'"{name}" CIBIL credit history India',
            f'"{name}" fraud allegation investigation India',
        ]

        # Sector queries
        queries += [
            f'{sector} sector India news 2024 2025',
            f'{sector} industry India regulatory compliance risks',
            f'{sector} India market outlook growth forecast',
            f'{sector} manufacturing India government policy',
            f'{sector} India supply chain disruption risk 2024',
        ]

        # Promoter queries
        for pname in promoter_names:
            queries.append(f'"{pname}" director India litigation fraud')
            queries.append(f'"{pname}" India company board MCA filings')

        if location:
            queries.append(f'{sector} {location} India industry news')

        if self.llm_available:
            prompt = (
                f"You are a credit research analyst investigating an Indian company for a loan application.\n"
                f"Company: {name}\n"
                f"Sector: {sector}\n"
                f"Location: {location}\n"
                f"Promoters: {', '.join(promoter_names)}\n\n"
                f"Generate 8 specific web search queries to find:\n"
                f"1. Legal disputes or litigation involving the company or promoters\n"
                f"2. Regulatory actions (RBI, SEBI, MCA filings, NCLT cases)\n"
                f"3. Sector-specific headwinds or tailwinds\n"
                f"4. News about financial health or fraud allegations\n"
                f"5. Bank NPA or wilful defaulter listings\n"
                f"6. Related party transactions or circular trading\n"
                f"7. Environmental or labour compliance issues\n"
                f"8. Competitor landscape or market share changes\n\n"
                f"Output ONLY the queries, one per line. No numbering, no explanation."
            )
            try:
                resp = self.engine.generate(prompt, max_tokens=400, temperature=0.3)
                if resp.answer and "[ERROR" not in resp.answer:
                    text = resp.answer if resp.answer else resp.raw_text
                    llm_queries = [q.strip().strip('"').strip("'") for q in text.strip().split('\n') if q.strip() and len(q.strip()) > 10]
                    queries.extend(llm_queries[:8])
            except Exception as e:
                print(f"  [Research] LLM query generation failed: {e}")

        return queries

    def _domain_confidence(self, url: str) -> float:
        """Return base confidence for a URL based on its domain tier."""
        for domain, score in DOMAIN_TIERS.items():
            if domain in url:
                return score
        return 0.40  # default for unlisted domains

    def _source_tier(self, domain_confidence: float) -> str:
        """Map a domain confidence score to a human-readable tier label."""
        if domain_confidence >= 0.90:
            return "authoritative"
        elif domain_confidence >= 0.70:
            return "credible"
        elif domain_confidence >= 0.50:
            return "general"
        else:
            return "low"

    # Minimum domain confidence required for a negative finding to be included:
    # Very-low tier negative findings are silently dropped to reduce noise.
    _TIER_FLOOR_FOR_NEGATIVE = 0.30

    # Noise patterns: if snippet/title contains these, treat as dictionary/wiki/forum noise
    _NOISE_PATTERNS: list[str] = [
        "definition of", "what is ", "meaning of", "how to ", "tutorial",
        "recipe", "cooking", "shopping", "buy now", "add to cart",
        "forum", "reddit.com", "quora.com", "answers.yahoo",
        "wikipedia.org/wiki/",
    ]

    def _is_noise(self, search_result: dict) -> bool:
        """Return True if the result looks like dictionary/wiki/forum content."""
        combined = (search_result.get("title", "") + " " + search_result.get("snippet", "")).lower()
        url = search_result.get("url", "").lower()
        if any(blocked in url for blocked in DOMAIN_BLOCKLIST):
            return True
        return any(p in combined or p in url for p in self._NOISE_PATTERNS)

    def _is_stale(self, snippet: str, category: str) -> bool:
        """Return True if regulatory/litigation signal appears to predate 2021."""
        if category not in ("regulatory", "litigation", "fraud"):
            return False
        # Look for a 4-digit year in the snippet; if earliest year < 2021 and no recent year, flag stale
        years = [int(y) for y in re.findall(r'\b(20(?:1[0-9]|2[0-9]))\b', snippet)]
        if years and max(years) < 2021:
            return True
        return False

    def _entity_matches(self, company: dict, text: str) -> bool:
        """
        Return True if text references the company or its sector.
        Uses conservative matching to prevent common-word false positives:
        - Full company name as substring, OR
        - Full sector phrase as substring, OR
        - At least 2 distinct significant words from company name both appear
        """
        name = company.get("name", "").lower()
        sector = company.get("sector", "").lower()
        text_lower = text.lower()

        # Full name phrase match
        if name and len(name) > 4 and name in text_lower:
            return True

        # Full sector phrase match (only if sector phrase is >= 6 chars)
        if sector and len(sector) >= 6 and sector in text_lower:
            return True

        # Multi-word name match: require 1+ significant words (>3 chars) to match
        significant = [w for w in name.split() if len(w) > 3 and w not in {"india", "pvt", "ltd", "limited", "private", "corp", "the"}]
        if significant and sum(1 for w in significant if w in text_lower) >= min(2, len(significant)):
            return True

        return False

    def analyze_finding(self, company: dict, search_result: dict,
                        known_facts: set) -> Optional[dict]:
        """Use LLM to analyze a search result for credit relevance."""
        title = search_result.get("title", "")
        snippet = search_result.get("snippet", "")
        url = search_result.get("url", "")

        if not snippet or len(snippet) < 20:
            return None

        # Entity / topic gating — reject results with no company or sector mention
        combined = title + " " + snippet
        if not self._entity_matches(company, combined):
            return None

        domain_conf = self._domain_confidence(url)
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
                if "[ERROR" in text:
                    print(f"  [Research] LLM error for {url[:60]}: {text[:100]}")
                    return None
                # Strip markdown fences if present
                text = re.sub(r'```(?:json)?\s*', '', text).strip()
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
                            "confidence": max(analysis.get("confidence", 0.5), domain_conf),
                            "relevance_score": max(analysis.get("confidence", 0.5), domain_conf),
                            "source_tier": self._source_tier(domain_conf),
                            "sentiment_score": -0.6 if analysis.get("risk_impact") == "negative" else
                                               0.4 if analysis.get("risk_impact") == "positive" else 0.0,
                            "corroborated": True,
                            "novel": is_novel,
                            "raw_snippet": snippet[:200],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
            except (json.JSONDecodeError, Exception) as e:
                print(f"  [Research] LLM analysis failed for {url}: {e}")

        # No fallback — LLM is required for proper sentiment classification
        return None

    def research_company(self, company: dict, use_cache: bool = False,
                          planned_queries: list[str] = None) -> dict:
        """
        Run full research workflow for a company.
        Returns structured research results with findings.

        Args:
            use_cache: Ignored (caching disabled). Kept for API compatibility.
            planned_queries: Optional pre-built query list from ResearchRouterAgent.
                             When supplied, step 1 (generate_search_queries) is skipped.
        """
        company_name = company.get("name", "Unknown")
        known_facts = set(company.get("known_facts", []))

        print(f"\n  [Research] Researching: {company_name}")
        t0 = time.time()

        # Step 1: Generate search queries (or use pre-built plan from ResearchRouterAgent)
        if planned_queries:
            queries = planned_queries
            print(f"  [Research] Using {len(queries)} pre-planned queries from ResearchRouterAgent")
        else:
            queries = self.generate_search_queries(company)
            print(f"  [Research] Generated {len(queries)} search queries")

        # Step 2: Execute web searches
        all_results = []
        seen_urls = set()
        for i, query in enumerate(queries):
            print(f"    Query {i+1}/{len(queries)}: {query[:60]}...")
            results = web_search(query, max_results=10)
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
            # Pre-filter noise (dictionary / forum / shopping pages)
            if self._is_noise(r):
                continue
            finding = self.analyze_finding(company, r, known_facts)
            if finding:
                # Drop "low" tier negative findings (B-list sources making unverified claims)
                tier = finding.get("source_tier", "low")
                impact = finding.get("risk_impact", "neutral")
                domain_conf = finding.get("confidence", 0.0)
                if impact == "negative" and domain_conf < self._TIER_FLOOR_FOR_NEGATIVE:
                    continue
                # Flag stale regulatory/litigation signals
                if self._is_stale(finding.get("raw_snippet", ""), finding.get("category", "")):
                    finding["stale"] = True
                    finding["risk_impact"] = "stale_" + impact
                findings.append(finding)

        # Step 4: Deduplicate and rank findings
        unique_findings = []
        seen_summaries = set()
        for f in sorted(findings, key=lambda x: x.get("confidence", 0), reverse=True):
            summary_key = f["summary"][:120].lower()
            if summary_key not in seen_summaries:
                seen_summaries.add(summary_key)
                unique_findings.append(f)

        # Step 5: Corroboration — downgrade unverified single-source high-impact claims
        category_counts: dict[str, int] = {}
        for f in unique_findings:
            cat = f.get("category", "general")
            category_counts[cat] = category_counts.get(cat, 0) + 1
        for f in unique_findings:
            cat = f.get("category", "general")
            count = category_counts.get(cat, 1)
            f["corroboration_count"] = count
            if cat in ("litigation", "fraud") and count < 2:
                f["insufficient_corroboration"] = True
                if f.get("risk_impact") == "negative":
                    f["risk_impact"] = "unverified"
            else:
                f["insufficient_corroboration"] = False

        elapsed = time.time() - t0
        print(f"  [Research] Found {len(unique_findings)} relevant findings in {elapsed:.1f}s")

        result = {
            "company": company_name,
            "cache_version": CACHE_VERSION,
            "queries_executed": len(queries),
            "web_results_found": len(all_results),
            "findings": unique_findings,
            "corroborated_findings": sum(1 for f in unique_findings if not f.get("insufficient_corroboration")),
            "stale_findings_marked": sum(1 for f in unique_findings if f.get("stale")),
            "stale_findings_dropped": sum(1 for f in unique_findings if f.get("stale")),
            "research_timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(elapsed, 1),
        }

        return result


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

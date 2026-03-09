"""
Research Router Agent for Intelli-Credit (Phase 3).

Produces a structured SearchPlan: an optimised, deduplicated set of search queries
with focus areas tailored to the borrower's risk profile.

Uses LIGHT_MODEL (qwen2.5:3b) for fast orchestration.
Falls back to deterministic query construction when LLM is unavailable.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchQuery:
    query: str
    focus_area: str        # e.g. "litigation", "sector", "promoter", "regulatory"
    priority: int = 1      # 1=high, 2=medium, 3=low
    rationale: str = ""


@dataclass
class SearchPlan:
    company_name: str
    queries: list[SearchQuery] = field(default_factory=list)
    focus_areas: list[str] = field(default_factory=list)
    fallback: bool = False   # True if LLM was unavailable and plan is deterministic

    def to_dict(self) -> dict:
        return {
            "company_name": self.company_name,
            "queries": [
                {"query": q.query, "focus_area": q.focus_area,
                 "priority": q.priority, "rationale": q.rationale}
                for q in self.queries
            ],
            "focus_areas": self.focus_areas,
            "fallback": self.fallback,
            "query_count": len(self.queries),
        }


class ResearchRouterAgent:
    """Builds an optimised SearchPlan for a borrower, using LLM or deterministic fallback."""

    def __init__(self, ollama_base: str = None):
        from services.cognitive.engine import CognitiveEngine, OLLAMA_BASE, LIGHT_MODEL
        base = ollama_base or OLLAMA_BASE
        self.engine = CognitiveEngine(base_url=base, model=LIGHT_MODEL)
        self._light_model = LIGHT_MODEL
        self.llm_available = self._check_light_model_available()

    def _check_light_model_available(self) -> bool:
        if not self.engine.is_alive():
            return False
        models = self.engine.list_models()
        return any(self._light_model in m for m in models)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, company: dict, risk_hints: list[str] = None) -> SearchPlan:
        """Build a SearchPlan from company profile + optional risk hints from rule firings."""
        name = company.get("name", "")
        sector = company.get("sector", "")
        location = company.get("location", "")
        promoters = [p.get("name", "") for p in company.get("promoters", []) if p.get("name")]
        loan_amount = str(company.get("loan_amount", ""))
        loan_purpose = company.get("loan_purpose", "")
        risk_hints = risk_hints or []

        if self.llm_available:
            plan = self._llm_plan(name, sector, location, promoters, risk_hints,
                                  loan_amount, loan_purpose)
            if plan:
                return plan

        return self._deterministic_plan(name, sector, location, promoters, risk_hints)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_plan(self, name: str, sector: str, location: str,
                  promoters: list[str], risk_hints: list[str],
                  loan_amount: str = "", loan_purpose: str = "") -> Optional[SearchPlan]:
        hints_text = "\n".join(f"- {h}" for h in risk_hints) if risk_hints else "None"
        financial_ctx = ""
        if loan_amount:
            financial_ctx += f"Loan Amount: ₹{loan_amount}\n"
        if loan_purpose:
            financial_ctx += f"Loan Purpose: {loan_purpose}\n"
        prompt = (
            "You are a senior credit research analyst. Produce a JSON search plan to investigate "
            f"'{name}' ({sector}, {location}) for a loan application.\n\n"
            f"{financial_ctx}"
            f"Rule-engine risk hints fired:\n{hints_text}\n\n"
            "Return ONLY valid JSON with this structure:\n"
            '{"queries": [{"query": "...", "focus_area": "litigation|sector|promoter|regulatory|financial", '
            '"priority": 1, "rationale": "one short sentence"}], '
            '"focus_areas": ["litigation", ...]}\n\n'
            "Generate 8–12 targeted, non-redundant queries covering:\n"
            "- NCLT/DRT proceedings, court cases\n"
            "- RBI/SEBI/MCA regulatory actions\n"
            "- Wilful defaulter or NPA listings\n"
            "- Promoter background and criminal records\n"
            "- Sector-specific risks and policy changes\n"
            "- Financial health indicators\n"
            "Priority 1=critical, 2=important, 3=nice-to-have."
        )
        try:
            resp = self.engine.generate(prompt, max_tokens=512, temperature=0.2)
            text = resp.answer if resp.answer else resp.raw_text
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if not m:
                return None
            data = json.loads(m.group())
            queries = [
                SearchQuery(
                    query=q["query"],
                    focus_area=q.get("focus_area", "general"),
                    priority=int(q.get("priority", 2)),
                    rationale=q.get("rationale", ""),
                )
                for q in data.get("queries", [])
                if q.get("query")
            ]
            if not queries:
                return None
            return SearchPlan(
                company_name=name,
                queries=queries,
                focus_areas=data.get("focus_areas", list({q.focus_area for q in queries})),
                fallback=False,
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Deterministic fallback
    # ------------------------------------------------------------------

    def _deterministic_plan(self, name: str, sector: str, location: str,
                             promoters: list[str], risk_hints: list[str]) -> SearchPlan:
        queries: list[SearchQuery] = []

        # Always: company news + legal + regulatory
        queries.append(SearchQuery(f'"{name}" India news 2024 2025', "sector", 1))
        queries.append(SearchQuery(f'"{name}" legal case India', "litigation", 1))
        queries.append(SearchQuery(f'"{name}" NCLT insolvency India', "litigation", 1))
        queries.append(SearchQuery(f'"{name}" wilful defaulter NPA India', "financial", 1))
        queries.append(SearchQuery(f'"{name}" MCA filings ROC India', "regulatory", 2))
        queries.append(SearchQuery(f'"{name}" credit rating India', "financial", 2))

        # Sector signals
        if sector:
            queries.append(SearchQuery(f'{sector} India regulatory news 2024', "regulatory", 2))
            queries.append(SearchQuery(f'{sector} India market outlook headwinds', "sector", 2))
            queries.append(SearchQuery(f'{sector} India NPA stressed sector RBI', "sector", 2))

        # Promoter background
        for pname in promoters[:3]:
            queries.append(SearchQuery(
                f'"{pname}" director India fraud litigation', "promoter", 1,
                "Background check on promoter"
            ))
            queries.append(SearchQuery(
                f'"{pname}" disqualified director wilful defaulter India', "promoter", 1,
                "Defaulter check on promoter"
            ))

        # Risk-hint driven
        hint_lower = " ".join(risk_hints).lower()
        if "dpd" in hint_lower or "overdue" in hint_lower:
            queries.append(SearchQuery(f'"{name}" non-performing asset NPA default', "financial", 1))
        if "gst" in hint_lower or "itc" in hint_lower:
            queries.append(SearchQuery(f'"{name}" GST violation ITC fraud', "regulatory", 1))
        if "circular" in hint_lower or "cycle" in hint_lower:
            queries.append(SearchQuery(f'"{name}" circular trading round-trip', "fraud", 1))

        focus_areas = list(dict.fromkeys(q.focus_area for q in queries))
        return SearchPlan(
            company_name=name,
            queries=queries,
            focus_areas=focus_areas,
            fallback=True,
        )

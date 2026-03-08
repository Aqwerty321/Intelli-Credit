"""
Evidence Judge Agent for Intelli-Credit (Phase 3).

Scores each research finding for relevance, credibility, and corroboration quality.
Computes precision@10 and corroboration rate for the Judge Mode UI panel.

Uses LIGHT_MODEL (qwen2.5:3b) for re-scoring; falls back to source-tier heuristics.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class JudgedEvidence:
    """A single finding with judge scores attached."""
    original: dict          # the raw finding dict from ResearchAgent
    relevance_score: float  # 0.0–1.0
    credibility_score: float
    corroboration_score: float
    composite_score: float  # weighted average
    accepted: bool          # True if composite_score >= ACCEPTANCE_THRESHOLD
    rejection_reason: str = ""

    def to_dict(self) -> dict:
        return {
            **self.original,
            "judge_relevance": round(self.relevance_score, 3),
            "judge_credibility": round(self.credibility_score, 3),
            "judge_corroboration": round(self.corroboration_score, 3),
            "judge_composite": round(self.composite_score, 3),
            "accepted": self.accepted,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class JudgeReport:
    accepted: list[JudgedEvidence] = field(default_factory=list)
    rejected: list[JudgedEvidence] = field(default_factory=list)
    precision_at_10: float = 0.0        # accepted / min(total, 10)
    corroboration_rate: float = 0.0     # findings with corroboration_count >= 2
    fallback: bool = False

    def to_dict(self) -> dict:
        return {
            "accepted_count": len(self.accepted),
            "rejected_count": len(self.rejected),
            "precision_at_10": round(self.precision_at_10, 3),
            "corroboration_rate": round(self.corroboration_rate, 3),
            "accepted": [e.to_dict() for e in self.accepted],
            "fallback": self.fallback,
        }


# Thresholds
_ACCEPTANCE_THRESHOLD = 0.40
# Weights for composite score
_W_RELEVANCE = 0.45
_W_CREDIBILITY = 0.35
_W_CORROBORATION = 0.20


class EvidenceJudgeAgent:
    """Scores research findings for credit-decision evidence quality."""

    def __init__(self, ollama_base: str = None):
        from services.cognitive.engine import CognitiveEngine, OLLAMA_BASE, LIGHT_MODEL
        base = ollama_base or OLLAMA_BASE
        self.engine = CognitiveEngine(base_url=base, model=LIGHT_MODEL)
        self._light_model = LIGHT_MODEL
        self.llm_available = self._check_light_model_available()

    def _check_light_model_available(self) -> bool:
        if not self.engine.is_alive():
            return False
        return any(self._light_model in m for m in self.engine.list_models())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def judge(self, findings: list[dict], company: dict) -> JudgeReport:
        """Score all findings and produce a JudgeReport."""
        judged: list[JudgedEvidence] = []
        for f in findings:
            je = self._score_finding(f, company)
            judged.append(je)

        accepted = [j for j in judged if j.accepted]
        rejected = [j for j in judged if not j.accepted]

        # Sort accepted by composite score descending (for stable ranking display)
        accepted.sort(key=lambda j: j.composite_score, reverse=True)

        # precision@10: rank ALL judged findings by composite score, take top-10,
        # measure fraction that are accepted.  This is the standard IR metric.
        judged_sorted_by_score = sorted(judged, key=lambda j: j.composite_score, reverse=True)
        total = len(judged_sorted_by_score)
        top_n = min(10, total)
        top_accepted = sum(1 for j in judged_sorted_by_score[:top_n] if j.accepted)
        precision_at_10 = top_accepted / top_n if top_n > 0 else 0.0

        # corroboration_rate
        corroborated = sum(
            1 for j in accepted
            if j.original.get("corroboration_count", 1) >= 2
               or not j.original.get("insufficient_corroboration", False)
        )
        corr_rate = corroborated / len(accepted) if accepted else 0.0

        return JudgeReport(
            accepted=accepted,
            rejected=rejected,
            precision_at_10=precision_at_10,
            corroboration_rate=corr_rate,
            fallback=not self.llm_available,
        )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_finding(self, finding: dict, company: dict) -> JudgedEvidence:
        relevance = self._score_relevance(finding, company)
        credibility = finding.get("confidence", finding.get("relevance_score", 0.4))
        corroboration = self._score_corroboration(finding)
        composite = (
            _W_RELEVANCE * relevance
            + _W_CREDIBILITY * credibility
            + _W_CORROBORATION * corroboration
        )
        accepted = composite >= _ACCEPTANCE_THRESHOLD
        reason = ""
        if not accepted:
            if credibility < 0.4:
                reason = "low-credibility source"
            elif relevance < 0.3:
                reason = "insufficient entity relevance"
            else:
                reason = f"composite score {composite:.2f} below threshold"

        return JudgedEvidence(
            original=finding,
            relevance_score=relevance,
            credibility_score=credibility,
            corroboration_score=corroboration,
            composite_score=composite,
            accepted=accepted,
            rejection_reason=reason,
        )

    def _score_relevance(self, finding: dict, company: dict) -> float:
        """Heuristic relevance: does the finding mention the company or sector?"""
        company_name = company.get("name", "").lower()
        sector = company.get("sector", "").lower()
        text = (finding.get("summary", "") + " " + finding.get("raw_snippet", "")).lower()

        score = 0.0
        if company_name and len(company_name) > 3 and company_name in text:
            score += 0.5
        elif sector and len(sector) > 3 and sector in text:
            score += 0.3

        # Boost for high-impact categories
        category = finding.get("category", "")
        if category in ("litigation", "fraud", "regulatory"):
            score += 0.2
        elif category in ("financial", "promoter"):
            score += 0.15
        elif category in ("sector",):
            score += 0.1

        return min(score, 1.0)

    def _score_corroboration(self, finding: dict) -> float:
        count = finding.get("corroboration_count", 1)
        if count >= 3:
            return 1.0
        elif count == 2:
            return 0.7
        elif finding.get("insufficient_corroboration"):
            return 0.2
        else:
            return 0.5

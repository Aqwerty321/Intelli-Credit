"""
Claim Graph Agent for Intelli-Credit (Phase 3).

Builds a structured graph of claims extracted from research findings and
document/rule signals. Each node is a Claim with a status (corroborated,
contradicted, unverified) and a list of sources.

This feeds the Judge Mode UI "Claim Graph" table.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClaimSource:
    url: str
    title: str
    tier: str   # "authoritative" | "credible" | "general" | "low" | "rule"


@dataclass
class Claim:
    claim_id: str
    text: str
    category: str       # "litigation" | "regulatory" | "financial" | "sector" | "fraud" | "rule"
    status: str         # "corroborated" | "contradicted" | "unverified"
    sources: list[ClaimSource] = field(default_factory=list)
    risk_impact: str = "neutral"   # "negative" | "positive" | "neutral"
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "category": self.category,
            "status": self.status,
            "risk_impact": self.risk_impact,
            "confidence": round(self.confidence, 3),
            "sources": [
                {"url": s.url, "title": s.title, "tier": s.tier}
                for s in self.sources
            ],
        }


@dataclass
class ClaimGraphResult:
    claims: list[Claim] = field(default_factory=list)
    contradictions: list[tuple[str, str]] = field(default_factory=list)  # (claim_id, claim_id)
    fallback: bool = False

    @property
    def corroborated_count(self) -> int:
        return sum(1 for c in self.claims if c.status == "corroborated")

    @property
    def contradiction_count(self) -> int:
        return len(self.contradictions)

    def to_dict(self) -> dict:
        return {
            "claims_total": len(self.claims),
            "corroborated": self.corroborated_count,
            "contradictions": self.contradiction_count,
            "claims": [c.to_dict() for c in self.claims],
            "contradiction_pairs": [
                {"a": a, "b": b} for a, b in self.contradictions
            ],
            "fallback": self.fallback,
        }


class ClaimGraph:
    """Extracts, deduplicates, and cross-validates claims from findings + rule firings."""

    def build(
        self,
        findings: list[dict],
        rule_firings: list = None,
        company: dict = None,
    ) -> ClaimGraphResult:
        """Build a ClaimGraph from research findings and rule firings."""
        claims: list[Claim] = []
        seen_texts: set[str] = set()

        # Extract claims from research findings
        for i, f in enumerate(findings):
            text = f.get("summary", "")
            if not text or text[:40].lower() in seen_texts:
                continue
            seen_texts.add(text[:40].lower())

            tier = f.get("source_tier", "general")
            source = ClaimSource(
                url=f.get("source", ""),
                title=f.get("source_title", ""),
                tier=tier,
            )
            corr_count = f.get("corroboration_count", 1)
            status = (
                "corroborated" if corr_count >= 2 and not f.get("insufficient_corroboration")
                else "unverified"
            )
            claims.append(Claim(
                claim_id=f"research_{i:03d}",
                text=text,
                category=f.get("category", "general"),
                status=status,
                sources=[source],
                risk_impact=f.get("risk_impact", "neutral"),
                confidence=f.get("confidence", 0.4),
            ))

        # Extract claims from rule firings
        if rule_firings:
            for i, rf in enumerate(rule_firings):
                # rf may be a RuleFiring dataclass or a dict
                if hasattr(rf, "rationale"):
                    rationale = rf.rationale
                    severity = rf.severity
                    risk_adj = getattr(rf, "risk_adjustment", 0.0)
                    slug = getattr(rf, "rule_slug", f"rule_{i}")
                else:
                    rationale = rf.get("rationale", "")
                    severity = rf.get("severity", "MEDIUM")
                    risk_adj = rf.get("risk_adjustment", 0.0)
                    slug = rf.get("rule_slug", f"rule_{i}")

                if not rationale:
                    continue

                claims.append(Claim(
                    claim_id=f"rule_{slug}",
                    text=rationale,
                    category="rule",
                    status="corroborated",   # rule firings are deterministic evidence
                    sources=[ClaimSource(url="", title=f"Rule: {slug}", tier="rule")],
                    risk_impact="negative" if severity in ("HIGH", "CRITICAL") else "neutral",
                    confidence=min(0.5 + risk_adj, 1.0),
                ))

        # Detect contradictions (simple heuristic: positive vs negative claims in same category)
        contradictions: list[tuple[str, str]] = []
        for i, ca in enumerate(claims):
            for j, cb in enumerate(claims):
                if i >= j:
                    continue
                if (ca.category == cb.category
                        and ca.risk_impact in ("positive", "negative")
                        and cb.risk_impact in ("positive", "negative")
                        and ca.risk_impact != cb.risk_impact):
                    contradictions.append((ca.claim_id, cb.claim_id))

        return ClaimGraphResult(
            claims=claims,
            contradictions=contradictions,
            fallback=False,
        )

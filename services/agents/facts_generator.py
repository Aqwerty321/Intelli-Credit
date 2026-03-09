"""
AutoFetch facts.md generator.

Takes research findings from ResearchAgent + company profile and uses
DeepSeek R1 8B to synthesize a structured facts.md document that the
existing validator.py regex extractors can parse.
"""
import json
import re
from datetime import datetime, timezone

# ── Facts.md template (deterministic fallback when LLM unavailable) ──────────

_TEMPLATE = """\
# Credit Assessment — {company_name}

## Company Profile
- **Company:** {company_name}
- **Promoter:** {promoter_name}
- **Sector:** {sector}
- **Location:** {location}
- **Loan Amount:** ₹{loan_amount_formatted} ({loan_purpose})

## CIBIL Commercial Report (MSME)
- CMR Rank: {cmr}/10
- Risk Category: {risk_category}
- Max DPD (Last 12 Months): {dpd} days
- Dishonoured Cheques: {dishonoured_cheques}

## GST Reconciliation
- ITC Available (GSTR-2A): INR {itc_2a}
- ITC Claimed (GSTR-3B): INR {itc_3b}

## Financial Indicators
- Declared GST Turnover: ₹{gst_turnover}
- Bank Statement Credits (12M): ₹{bank_credits}
- Capacity Utilization: {capacity}%
- Collateral Value: ₹{collateral}

{litigation_section}\
## Assessment Summary
{assessment_summary}
"""

_LITIGATION_TEMPLATE = """\
## Legal & Regulatory Status
{litigation_items}

"""


def _fmt_inr(amount: float) -> str:
    """Format number in Indian style (e.g. 1,50,00,000)."""
    s = str(int(amount))
    if len(s) <= 3:
        return s
    last3 = s[-3:]
    rest = s[:-3]
    parts = []
    while rest:
        parts.append(rest[-2:] if len(rest) >= 2 else rest)
        rest = rest[:-2]
    return ",".join(reversed(parts)) + "," + last3


class FactsGenerator:
    """Generate a facts.md document from research findings + company profile."""

    def __init__(self):
        self.engine = None
        self.llm_available = False
        try:
            from services.cognitive.engine import CognitiveEngine, LIGHT_MODEL
            self.engine = CognitiveEngine(model=LIGHT_MODEL)
            self.llm_available = self.engine.is_alive()
        except Exception:
            pass

    def generate(self, company: dict, findings: list[dict],
                 progress_cb=None) -> tuple[str, dict]:
        """
        Generate facts.md content from research findings.

        Args:
            company: {name, sector, location, promoters, loan_amount, loan_purpose}
            findings: List of research finding dicts from ResearchAgent
            progress_cb: Optional callback(message) for progress updates

        Returns:
            (markdown_content, generation_meta)
        """
        if self.llm_available:
            return self._generate_with_llm(company, findings, progress_cb)
        return self._generate_deterministic(company, findings, progress_cb)

    def _generate_with_llm(self, company: dict, findings: list[dict],
                           progress_cb=None) -> tuple[str, dict]:
        """Use DeepSeek R1 8B to synthesize findings into structured facts.md."""
        if progress_cb:
            progress_cb("Synthesizing with DeepSeek R1 8B...")

        name = company.get("name", "Unknown Company")
        sector = company.get("sector", "General")
        location = company.get("location", "India")
        loan_amount = company.get("loan_amount", 0)
        loan_purpose = company.get("loan_purpose", "Working Capital")
        promoters = company.get("promoters", [])
        promoter_names = [p.get("name", "") for p in promoters if p.get("name")]
        promoter_str = ", ".join(promoter_names) if promoter_names else "Not Available"

        # Build findings context for LLM
        findings_text = self._format_findings_for_prompt(findings)

        system_prompt = (
            "You are a senior Indian credit analyst preparing a Credit Assessment document "
            "for an MSME loan application. You MUST output a Markdown document following the "
            "EXACT format specified below. Use the research findings provided to estimate "
            "realistic values. Where you lack hard data, make conservative estimates based on "
            "the sector, research signals, and risk profile.\n\n"
            "CRITICAL FORMAT RULES — the downstream parser uses regex, so you MUST use these "
            "exact field formats:\n"
            "- CMR Rank: X/10  (integer 1-10, where 1=best, 10=worst)\n"
            "- Max DPD (Last 12 Months): X days  (integer)\n"
            "- Dishonoured Cheques: X  (integer)\n"
            "- ITC Available (GSTR-2A): INR XXXXXXX  (integer, no commas)\n"
            "- ITC Claimed (GSTR-3B): INR XXXXXXX  (integer, no commas)\n"
            "- Capacity Utilization: XX%  (integer percentage)\n"
            "- Collateral Value: ₹XXXXXXXX  (integer with ₹ prefix, no commas)\n"
            "- Criminal Cases: X  (integer, only if applicable)\n"
            "- Civil Cases: X  (integer, only if applicable)\n\n"
            "If negative findings (litigation, fraud, regulatory) exist, add a "
            "'## Legal & Regulatory Status' section BEFORE the Assessment Summary.\n\n"
            "Mark any value you estimated (not from official documents) with [ESTIMATED] "
            "on the same line, e.g.: 'CMR Rank: 5/10 [ESTIMATED]'"
        )

        user_prompt = (
            f"Generate a Credit Assessment document for:\n\n"
            f"Company: {name}\n"
            f"Promoter(s): {promoter_str}\n"
            f"Sector: {sector}\n"
            f"Location: {location}\n"
            f"Loan Amount: ₹{_fmt_inr(loan_amount)} ({loan_purpose})\n\n"
            f"=== REASONABLE DEFAULT VALUES (use unless research contradicts) ===\n"
            f"CMR Rank: 4/10 (moderate, adjust up if negatives found)\n"
            f"Max DPD: 0 days (increase only if research shows payment delays)\n"
            f"Dishonoured Cheques: 0\n"
            f"GST Turnover: ₹{_fmt_inr(int(loan_amount * 3))} (3x loan amount)\n"
            f"Bank Credits: ₹{_fmt_inr(int(loan_amount * 3.15))} (should be >= GST turnover)\n"
            f"ITC Available (GSTR-2A): INR {int(loan_amount * 0.27)} (9% of turnover)\n"
            f"ITC Claimed (GSTR-3B): INR {int(loan_amount * 0.27)} (should be close to 2A)\n"
            f"Capacity Utilization: 75%\n"
            f"Collateral Value: ₹{int(loan_amount * 1.5)} (1.5x loan amount)\n\n"
            f"=== RESEARCH FINDINGS ({len(findings)} items) ===\n"
            f"{findings_text}\n\n"
            f"=== REQUIRED OUTPUT FORMAT ===\n"
            f"# Credit Assessment — {name}\n\n"
            f"## Company Profile\n"
            f"- **Company:** {name}\n"
            f"- **Promoter:** {promoter_str}\n"
            f"- **Sector:** {sector}\n"
            f"- **Location:** {location}\n"
            f"- **Loan Amount:** ₹{_fmt_inr(loan_amount)} ({loan_purpose})\n\n"
            f"## CIBIL Commercial Report (MSME)\n"
            f"- CMR Rank: ?/10\n"
            f"- Risk Category: ?\n"
            f"- Max DPD (Last 12 Months): ? days\n"
            f"- Dishonoured Cheques: ?\n\n"
            f"## GST Reconciliation\n"
            f"- ITC Available (GSTR-2A): INR ?\n"
            f"- ITC Claimed (GSTR-3B): INR ?\n\n"
            f"## Financial Indicators\n"
            f"- Declared GST Turnover: ₹?\n"
            f"- Bank Statement Credits (12M): ₹?\n"
            f"- Capacity Utilization: ?%\n"
            f"- Collateral Value: ₹?\n\n"
            f"[Add ## Legal & Regulatory Status if negative findings exist]\n\n"
            f"## Assessment Summary\n"
            f"[2-4 sentence assessment based on all findings]\n\n"
            f"Fill in the ? values. Use the REASONABLE DEFAULTS above as a starting point "
            f"and adjust based on research findings. CRITICAL: Bank Credits must be >= GST "
            f"Turnover. Collateral must be >= loan amount. Mark estimated values with [ESTIMATED]. "
            f"Output ONLY the markdown document, no additional commentary."
        )

        try:
            resp = self.engine.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=2048,
                temperature=0.3,
            )
            raw = resp.answer if resp.answer else resp.raw_text

            # Validate the output has required sections
            if "## Company Profile" in raw and "## CIBIL" in raw:
                if progress_cb:
                    progress_cb("Facts document generated successfully")
                return raw.strip(), {
                    "method": "llm",
                    "model": resp.model,
                    "tokens_used": resp.tokens_used,
                    "latency_ms": resp.latency_ms,
                }
            else:
                # LLM output didn't match format, fall back
                if progress_cb:
                    progress_cb("LLM output format mismatch — using template fallback")
                return self._generate_deterministic(company, findings, progress_cb)

        except Exception as e:
            if progress_cb:
                progress_cb(f"LLM synthesis failed ({e}) — using template fallback")
            return self._generate_deterministic(company, findings, progress_cb)

    def _generate_deterministic(self, company: dict, findings: list[dict],
                                progress_cb=None) -> tuple[str, dict]:
        """Generate facts.md using template + research signals (no LLM needed)."""
        if progress_cb:
            progress_cb("Generating facts document (template mode)...")

        name = company.get("name", "Unknown Company")
        sector = company.get("sector", "General")
        location = company.get("location", "India")
        loan_amount = company.get("loan_amount", 0)
        loan_purpose = company.get("loan_purpose", "Working Capital")
        promoters = company.get("promoters", [])
        promoter_names = [p.get("name", "") for p in promoters if p.get("name")]
        promoter_str = ", ".join(promoter_names) if promoter_names else "Not Available"

        # Derive estimates from research signals
        neg_count = sum(1 for f in findings if f.get("risk_impact") == "negative")
        lit_findings = [f for f in findings if f.get("category") in ("litigation", "fraud")]
        reg_findings = [f for f in findings if f.get("category") == "regulatory"]

        # CMR estimation: base 4, modestly adjust for serious negatives only
        fraud_count = sum(1 for f in findings if f.get("category") in ("fraud", "litigation"))
        cmr = min(8, 4 + fraud_count)  # only litigation/fraud move CMR, not general negatives
        if fraud_count == 0:
            cmr = 3 if neg_count == 0 else 4
            risk_cat = "Low Risk" if neg_count == 0 else "Moderate Risk"
        elif fraud_count <= 2:
            risk_cat = "Medium Risk"
        elif fraud_count <= 4:
            risk_cat = "High Risk"
        else:
            risk_cat = "Critical Risk"

        # DPD estimation — only if direct payment delay/default signals exist
        dpd = 0
        dpd_keywords = ("dpd", "default", "npa", "overdue", "delay")
        dpd_findings = [f for f in findings if any(k in f.get("summary", "").lower() for k in dpd_keywords)]
        if dpd_findings:
            dpd = min(60, len(dpd_findings) * 15)
        dishonoured = min(3, sum(1 for f in lit_findings if "cheque" in f.get("summary", "").lower() or "dishonour" in f.get("summary", "").lower()))

        # Financial estimates based on loan amount
        gst_turnover = int(loan_amount * 3)
        bank_credits = int(gst_turnover * 1.05)
        itc_2a = int(gst_turnover * 0.09)
        itc_3b = int(itc_2a * (1.15 if neg_count > 2 else 1.02))
        capacity = max(30, 75 - neg_count * 8)
        collateral = int(loan_amount * 1.5)

        # Build litigation section
        litigation_section = ""
        if lit_findings or reg_findings:
            items = []
            criminal = sum(1 for f in lit_findings if "criminal" in f.get("summary", "").lower())
            civil = len(lit_findings) - criminal
            for f in (lit_findings + reg_findings)[:5]:
                items.append(f"- {f.get('summary', 'Finding details unavailable')}")
            if criminal:
                items.append(f"- Criminal Cases: {criminal}")
            if civil:
                items.append(f"- Civil Cases: {civil}")
            litigation_section = _LITIGATION_TEMPLATE.format(
                litigation_items="\n".join(items)
            )

        # Build assessment summary
        if neg_count == 0:
            assessment = (
                f"Moderate credit profile based on available research. No significant negative "
                f"signals found for {name}. All values are estimated from web research and should "
                f"be verified with official documents (CIBIL report, GST returns, bank statements)."
            )
        elif neg_count <= 2:
            assessment = (
                f"Borderline case. {neg_count} negative signal(s) found in research. "
                f"CMR and DPD values are estimated — verify with official CIBIL report. "
                f"Recommendation: CONDITIONAL — proceed with enhanced due diligence."
            )
        else:
            assessment = (
                f"Elevated risk profile. {neg_count} negative signals including "
                f"{len(lit_findings)} litigation/fraud indicator(s). CMR and financial values "
                f"are estimated conservatively. Full document verification mandatory before "
                f"any lending decision."
            )

        content = _TEMPLATE.format(
            company_name=name,
            promoter_name=promoter_str,
            sector=sector,
            location=location,
            loan_amount_formatted=_fmt_inr(loan_amount),
            loan_purpose=loan_purpose,
            cmr=cmr,
            risk_category=risk_cat,
            dpd=dpd,
            dishonoured_cheques=dishonoured,
            itc_2a=itc_2a,
            itc_3b=itc_3b,
            gst_turnover=_fmt_inr(gst_turnover),
            bank_credits=_fmt_inr(bank_credits),
            capacity=capacity,
            collateral=collateral,
            litigation_section=litigation_section,
            assessment_summary=assessment,
        )

        # Append raw research findings as appendix
        if findings:
            content += "\n## Research Findings (Auto-Fetched)\n"
            for i, f in enumerate(findings[:15], 1):
                summary = f.get("summary", "")
                source = f.get("source", "")
                category = f.get("category", "general")
                impact = f.get("risk_impact", "neutral")
                content += f"{i}. [{category}/{impact}] {summary}\n"
                if source:
                    content += f"   Source: {source}\n"

        return content.strip(), {"method": "deterministic", "findings_used": len(findings)}

    def _format_findings_for_prompt(self, findings: list[dict]) -> str:
        """Format research findings as concise text for the LLM prompt."""
        if not findings:
            return "No research findings available."
        lines = []
        for i, f in enumerate(findings[:20], 1):
            cat = f.get("category", "general")
            impact = f.get("risk_impact", "neutral")
            conf = f.get("confidence", 0)
            summary = f.get("summary", "")
            source = f.get("source_title", f.get("source", ""))
            stale = " [STALE]" if f.get("stale") else ""
            lines.append(f"{i}. [{cat}|{impact}|conf={conf:.2f}{stale}] {summary}")
            if source:
                lines.append(f"   Source: {source}")
        return "\n".join(lines)

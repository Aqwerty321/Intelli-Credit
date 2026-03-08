"""
Field validator for extracted Indian corporate document fields.
Validates GSTIN, PAN, invoice totals, dates using regex patterns.
"""
import re
from typing import Optional
# Standard library used by Ollama fallback extractor (lazy-imported inside function)
# import json, os, urllib.request, urllib.error — imported lazily below


# Indian GSTIN: 2-digit state code + 10-char PAN + 1 entity code + 1 Z + 1 check digit
GSTIN_PATTERN = re.compile(
    r'\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d][Z][A-Z\d])\b'
)

# Indian PAN: 5 letters + 4 digits + 1 letter
PAN_PATTERN = re.compile(
    r'\b([A-Z]{5}\d{4}[A-Z])\b'
)

# Invoice total: various Indian currency formats (₹, Rs., INR) + bare Indian-format numbers
# Third alternation: Indian lakhs/crores pattern requiring at least X,XX,XXX (6+ digits)
INVOICE_TOTAL_PATTERN = re.compile(
    r'(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)'
    r'|(?:Total|Amount|Grand\s*Total|Net\s*Amount)\s*[:\s]*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)'
    r'|\b(\d{1,2},\d{2}(?:,\d{2})*,\d{3}(?:\.\d{1,2})?)\b',
    re.IGNORECASE
)

# Indian date formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, and variations
DATE_PATTERN = re.compile(
    r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b'
    r'|\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4})\b',
    re.IGNORECASE
)

# CIN: Company Identification Number
CIN_PATTERN = re.compile(
    r'\b([UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b'
)

# Indian phone numbers
PHONE_PATTERN = re.compile(
    r'\b(?:\+91[\s\-]?)?([6-9]\d{9})\b'
)

# IFSC Code
IFSC_PATTERN = re.compile(
    r'\b([A-Z]{4}0[A-Z\d]{6})\b'
)


def validate_gstin(value: str) -> bool:
    """Validate GSTIN format (15 characters)."""
    return bool(GSTIN_PATTERN.fullmatch(value.strip().upper()))


def validate_pan(value: str) -> bool:
    """Validate PAN format (10 characters)."""
    return bool(PAN_PATTERN.fullmatch(value.strip().upper()))


def extract_gstins(text: str) -> list[str]:
    """Extract all GSTINs from text."""
    return GSTIN_PATTERN.findall(text.upper())


def extract_pans(text: str) -> list[str]:
    """Extract all PANs from text."""
    return PAN_PATTERN.findall(text.upper())


def extract_invoice_totals(text: str) -> list[str]:
    """Extract all invoice/amount totals from text."""
    results = []
    for match in INVOICE_TOTAL_PATTERN.finditer(text):
        value = match.group(1) or match.group(2) or match.group(3)
        if value:
            raw = value.replace(',', '')
            results.append(raw)
    return results


def extract_dates(text: str) -> list[str]:
    """Extract all dates from text."""
    results = []
    for match in DATE_PATTERN.finditer(text):
        date_str = match.group(1) or match.group(2)
        if date_str:
            results.append(date_str.strip())
    return results


def extract_all_fields(text: str) -> dict[str, list[str]]:
    """Extract all known field types from text."""
    return {
        "gstin": extract_gstins(text),
        "pan": extract_pans(text),
        "invoice_total": extract_invoice_totals(text),
        "date": extract_dates(text),
    }


# ---------------------------------------------------------------------------
# Domain-specific extractors (CIBIL, GST ITC)
# ---------------------------------------------------------------------------

def extract_cibil_facts(text: str) -> dict:
    """Extract CIBIL-specific fields: CMR rank, max DPD, dishonoured cheques.

    Accepts multiple real-world formats found in Indian CIBIL reports:
      CMR Rank: 9/10 | CIBIL CMR Rank: 9 | CIBIL MSME Rank (CMR) 7 | CMR: 9
      Max DPD (Last 12 Months): 45 days | Max DPD 12M: 45 | DPD: 30
      Dishonoured Cheques: 5 | Bounced Cheques: 3 | Cheque Returns: 2
    """
    facts = {}

    # CMR Score / Rank — try patterns in priority order (most specific first)
    _CMR_PATTERNS = [
        r'CMR\s*(?:Score|Rank)?\s*[:\s]*(\d{1,2})\s*/\s*10',
        r'CIBIL\s+(?:(?:MSME|CMR|Commercial)\s+){0,2}(?:Score|Rank)\s*(?:\(CMR\))?\s*[:\s]*(\d{1,2})\b',
        r'\bCMR\s*[:\s=]\s*(\d{1,2})\b',
    ]
    for pat in _CMR_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            facts["cibil_cmr_rank"] = int(m.group(1))
            break

    # Max DPD — try patterns in priority order
    _DPD_PATTERNS = [
        r'Max(?:imum)?\s*DPD\s*(?:\([^)]*\))?\s*[:\s]*(\d+)\s*days?',
        r'Max\s*DPD\s+\d+M\s*[:\s]*(\d+)',
        r'\bDPD\s*[:\s=]\s*(\d+)',
    ]
    for pat in _DPD_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            facts["max_dpd_last_12m"] = int(m.group(1))
            break

    # Dishonoured / Bounced Cheques
    _CHEQUE_PATTERNS = [
        r'Dishonoured\s*Cheques?\s*[:\s]*(\d+)',
        r'Bounced\s*Cheques?\s*[:\s]*(\d+)',
        r'Cheque\s*(?:Returns?|Bounces?)\s*[:\s]*(\d+)',
    ]
    for pat in _CHEQUE_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            facts["dishonoured_cheque_count_12m"] = int(m.group(1))
            break

    # Risk Category
    m = re.search(
        r'Risk\s*Category\s*[:\s]*(Low|Medium|High|Very\s*High|Critical)\s*Risk',
        text, re.IGNORECASE
    )
    if m:
        facts["risk_category"] = m.group(1).strip()

    return facts


def extract_gst_itc_facts(text: str) -> dict:
    """Extract GST ITC fields: GSTR-2A available, GSTR-3B claimed."""
    facts = {}

    # ITC Available (GSTR-2A): Rs. X,XX,XXX
    m = re.search(r'ITC\s*Available\s*\(GSTR-2A\)\s*[:\s]*(?:Rs\.?|₹|INR)\s*([\d,]+)', text, re.IGNORECASE)
    if m:
        facts["gstr2a_itc_available"] = int(m.group(1).replace(',', ''))

    # ITC Claimed (GSTR-3B): Rs. X,XX,XXX
    m = re.search(r'ITC\s*Claimed\s*\(GSTR-3B\)\s*[:\s]*(?:Rs\.?|₹|INR)\s*([\d,]+)', text, re.IGNORECASE)
    if m:
        facts["gstr3b_itc_claimed"] = int(m.group(1).replace(',', ''))

    # Taxable value / Total Tax Payable
    m = re.search(r'Taxable\s*Value\s*[:\s]*(?:Rs\.?|₹|INR)\s*([\d,]+)', text, re.IGNORECASE)
    if m:
        facts["taxable_value"] = int(m.group(1).replace(',', ''))

    m = re.search(r'Total\s*Tax\s*Payable\s*[:\s]*(?:Rs\.?|₹|INR)\s*([\d,]+)', text, re.IGNORECASE)
    if m:
        facts["total_tax_payable"] = int(m.group(1).replace(',', ''))

    return facts


def extract_financial_facts(text: str) -> dict:
    """Extract financial metrics: collateral, capacity utilisation, GST turnover, bank credits."""
    facts = {}

    # Collateral / security value
    _COLLATERAL_PATTERNS = [
        r'Collateral\s*(?:Value|Amount|Security)\s*[:\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)',
        r'(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)\s*(?:[^\n]{0,30})?collateral',
        r'Security\s*(?:Value|Amount)\s*[:\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)',
    ]
    for pat in _COLLATERAL_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            facts["collateral_value"] = float(m.group(1).replace(',', ''))
            break

    # Capacity utilisation percentage
    _CAP_PATTERNS = [
        r'Capacity\s*(?:Utiliz|Utilis)ation\s*[:\s]*(\d{1,3})(?:\.\d+)?\s*%',
        r'Plant\s*(?:Utiliz|Utilis)ation\s*[:\s]*(\d{1,3})(?:\.\d+)?\s*%',
        r'(?:Operating|Production)\s*Capacity\s*[:\s]*(\d{1,3})(?:\.\d+)?\s*%',
    ]
    for pat in _CAP_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            facts["capacity_utilization_pct"] = float(m.group(1))
            break

    # GST declared turnover
    _TURNOVER_PATTERNS = [
        r'(?:GST|GSTR[\-\s]?(?:1|3B))\s*(?:Declared\s*)?(?:Turnover|Sales)\s*[:\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)',
        r'Declared\s*(?:GST\s*)?(?:Turnover|Sales|Revenue)\s*[:\s]*(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)',
        r'Annual\s*Turnover\s*\(GST\)\s*[:\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)',
    ]
    for pat in _TURNOVER_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            facts["gst_declared_turnover"] = float(m.group(1).replace(',', ''))
            break

    # Bank statement total credits
    _BANK_PATTERNS = [
        r'Bank\s*(?:Statement\s*)?Credits?\s*(?:\(\d+M\))?\s*[:\s]*(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)',
        r'Total\s*Bank\s*Credits?\s*[:\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)',
        r'Credit\s*Summation\s*[:\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)',
    ]
    for pat in _BANK_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            facts["bank_statement_credits"] = float(m.group(1).replace(',', ''))
            break

    return facts


def extract_litigation_facts(text: str) -> dict:
    """Extract litigation signals: criminal cases, civil cases."""
    facts = {}

    # Criminal cases
    m = re.search(r'Criminal\s*Cases?\s*[:\s]*(\d+)', text, re.IGNORECASE)
    if m:
        facts["criminal_cases"] = int(m.group(1))
    else:
        m = re.search(r'(\d+)\s+(?:criminal|IPC|FIR)\s+(?:cases?|charges?|complaints?)', text, re.IGNORECASE)
        if m:
            facts["criminal_cases"] = int(m.group(1))

    # Civil high-value cases
    m = re.search(r'Civil\s*High\s*Value\s*Cases?\s*[:\s]*(\d+)', text, re.IGNORECASE)
    if m:
        facts["civil_high_value_cases"] = int(m.group(1))

    # Civil cases (any)
    m = re.search(r'Civil\s*(?:Cases?|Suits?)\s*(?:[^:\d]{0,30})?[:\s]*(\d+)', text, re.IGNORECASE)
    if m:
        facts["civil_any_cases"] = int(m.group(1))
    else:
        m = re.search(r'(\d+)\s+civil\s+(?:cases?|suits?)', text, re.IGNORECASE)
        if m:
            facts["civil_any_cases"] = int(m.group(1))

    return facts


def extract_graph_facts(text: str) -> dict:
    """Extract circular-trading / graph signals from document text."""
    facts = {}

    # cycle_detected: explicit fraud-pattern language in document
    _FRAUD_PHRASES = [
        "circular transaction", "circular trading", "round trip",
        "accommodation invoice", "fictitious transaction", "layering",
    ]
    _text_lower = text.lower()
    if any(phrase in _text_lower for phrase in _FRAUD_PHRASES):
        if any(w in _text_lower for w in ("detected", "found", "identified", "pattern", "alleged")):
            facts["cycle_detected"] = True

    # cycle_length
    m = re.search(r'Cycle\s*(?:Length|Size)\s*[:\s]*(\d+)', text, re.IGNORECASE)
    if m:
        facts["cycle_length"] = int(m.group(1))

    # total_value involved in circular transactions
    m = re.search(
        r'Total\s*(?:Transaction|Circular|Cycle)?\s*Value\s*[:\s]*(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)',
        text, re.IGNORECASE
    )
    if m:
        facts["total_value"] = float(m.group(1).replace(',', ''))

    return facts


def _try_ollama_extraction(text: str, missing_fields: list) -> dict:
    """Lightweight Ollama fallback for critical fields not found by regex.

    Uses the first available small model (qwen2.5:3b preferred).
    Returns {} silently on any error (network, parse, model unavailable).
    """
    import json as _json
    import os as _os
    import urllib.request as _urlreq
    import urllib.error as _urlerr

    OLLAMA_BASE = _os.environ.get("OLLAMA_HOST", "http://172.23.112.1:11434")
    _FIELD_DESCS = {
        "cibil_cmr_rank": "CIBIL CMR Score (integer 1-10, 10=worst risk)",
        "max_dpd_last_12m": "Maximum Days Past Due in last 12 months (integer, 0=no delay)",
        "collateral_value": "Collateral or security value in INR (number)",
        "capacity_utilization_pct": "Capacity utilisation percentage (0-100)",
    }
    requested = {f: _FIELD_DESCS[f] for f in missing_fields if f in _FIELD_DESCS}
    if not requested:
        return {}

    try:
        # Check which models are available
        with _urlreq.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=3) as r:
            models_data = _json.loads(r.read())
        available_names = [m["name"] for m in models_data.get("models", [])]
        model = next(
            (c for c in ("qwen2.5:3b", "qwen2.5:0.5b", "phi3:mini", "llama3.2:3b")
             if any(c in n for n in available_names)),
            None,
        )
        if not model:
            return {}

        prompt = (
            "Extract these credit metrics from the document. Return ONLY valid JSON.\n"
            f"Fields: {_json.dumps(requested)}\n\n"
            f"Document snippet:\n{text[:1500]}\n\n"
            "Return JSON only. Use null for fields not clearly stated."
        )
        payload = _json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": 200, "temperature": 0.0},
        }).encode()
        req = _urlreq.Request(
            f"{OLLAMA_BASE}/api/chat", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with _urlreq.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read())

        raw = data.get("message", {}).get("content", "")
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start == -1 or end == 0:
            return {}
        extracted = _json.loads(raw[start:end])

        result = {}
        for k, v in extracted.items():
            if v is None or k not in missing_fields:
                continue
            try:
                if k in ("cibil_cmr_rank", "max_dpd_last_12m"):
                    result[k] = int(float(v))
                else:
                    result[k] = float(v)
            except (ValueError, TypeError):
                pass
        return result
    except Exception:
        return {}


def extract_domain_facts(text: str) -> dict:
    """Extract all domain-specific facts from document text.

    Runs all regex extractors first; falls back to Ollama for critical fields
    (CMR rank, max DPD) only if they were not found by regex.
    """
    facts = {}
    facts.update(extract_cibil_facts(text))
    facts.update(extract_gst_itc_facts(text))
    facts.update(extract_financial_facts(text))
    facts.update(extract_litigation_facts(text))
    facts.update(extract_graph_facts(text))

    # Ollama fallback for critical fields still missing after regex pass
    _CRITICAL = ("cibil_cmr_rank", "max_dpd_last_12m")
    missing = [f for f in _CRITICAL if f not in facts]
    if missing:
        ollama_facts = _try_ollama_extraction(text, missing)
        if ollama_facts:
            facts.update(ollama_facts)
            facts["_extraction_fallback"] = list(ollama_facts.keys())

    return facts


def compute_confidence(field_type: str, value: str, context: Optional[str] = None) -> float:
    """Compute extraction confidence score for a field."""
    base_confidence = 0.5

    if field_type == "gstin":
        if validate_gstin(value):
            base_confidence = 0.95
        else:
            base_confidence = 0.3

    elif field_type == "pan":
        if validate_pan(value):
            base_confidence = 0.95
        else:
            base_confidence = 0.3

    elif field_type == "invoice_total":
        # Higher confidence if preceded by clear label
        if context and re.search(r'(?:total|amount|grand)', context, re.IGNORECASE):
            base_confidence = 0.85
        else:
            base_confidence = 0.6

    elif field_type == "date":
        base_confidence = 0.7

    return base_confidence

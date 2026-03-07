"""
Field validator for extracted Indian corporate document fields.
Validates GSTIN, PAN, invoice totals, dates using regex patterns.
"""
import re
from typing import Optional


# Indian GSTIN: 2-digit state code + 10-char PAN + 1 entity code + 1 Z + 1 check digit
GSTIN_PATTERN = re.compile(
    r'\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d][Z][A-Z\d])\b'
)

# Indian PAN: 5 letters + 4 digits + 1 letter
PAN_PATTERN = re.compile(
    r'\b([A-Z]{5}\d{4}[A-Z])\b'
)

# Invoice total: various Indian currency formats (₹, Rs., INR)
INVOICE_TOTAL_PATTERN = re.compile(
    r'(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)'
    r'|(?:Total|Amount|Grand\s*Total|Net\s*Amount)\s*[:\s]*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)',
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
        value = match.group(1) or match.group(2)
        if value:
            results.append(value.replace(',', ''))
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

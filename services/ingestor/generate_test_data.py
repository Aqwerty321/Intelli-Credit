"""
Synthetic test data generator for Intelli-Credit.
Creates realistic Indian corporate document PDFs with known ground truth.
"""
import json
import os
import random
import string
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def random_gstin() -> str:
    """Generate a valid-format GSTIN."""
    state_code = f"{random.randint(1, 37):02d}"
    pan = random_pan()
    entity_code = random.choice(string.digits + string.ascii_uppercase)
    return f"{state_code}{pan}Z{entity_code}"


def random_pan() -> str:
    """Generate a valid-format PAN."""
    first_three = ''.join(random.choices(string.ascii_uppercase, k=3))
    fourth = random.choice("PCFHTA")  # entity type
    fifth = random.choice(string.ascii_uppercase)
    digits = f"{random.randint(1000, 9999)}"
    last = random.choice(string.ascii_uppercase)
    return f"{first_three}{fourth}{fifth}{digits}{last}"


def random_date(start_year=2023, end_year=2025) -> str:
    """Generate a random date in DD/MM/YYYY format."""
    year = random.randint(start_year, end_year)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{day:02d}/{month:02d}/{year}"


def random_amount(min_val=10000, max_val=50000000) -> str:
    """Generate a random Indian currency amount."""
    amount = random.randint(min_val, max_val)
    # Format with Indian comma separators (lakhs/crores)
    s = str(amount)
    if len(s) > 3:
        last_three = s[-3:]
        remaining = s[:-3]
        parts = []
        while remaining:
            parts.append(remaining[-2:] if len(remaining) >= 2 else remaining)
            remaining = remaining[:-2]
        parts.reverse()
        s = ','.join(parts) + ',' + last_three
    return s


def generate_gst_return_pdf(output_dir: str, sample_id: str) -> dict:
    """Generate a synthetic GST return PDF and ground truth."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
    except ImportError:
        return generate_text_based_sample(output_dir, sample_id, "gst")

    gstin = random_gstin()
    pan = gstin[2:12]
    dates = [random_date() for _ in range(3)]
    amounts = [random_amount(100000, 10000000) for _ in range(5)]

    pdf_path = os.path.join(output_dir, f"{sample_id}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, h = A4

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(30 * mm, h - 30 * mm, "GOODS AND SERVICES TAX RETURN")
    c.setFont("Helvetica", 10)
    c.drawString(30 * mm, h - 38 * mm, "Form GSTR-3B [See Rule 61(5)]")

    # Company details
    y = h - 55 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30 * mm, y, "1. GSTIN:")
    c.setFont("Helvetica", 11)
    c.drawString(65 * mm, y, gstin)

    y -= 8 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30 * mm, y, "2. Legal Name:")
    c.setFont("Helvetica", 11)
    company_name = f"M/s {random.choice(['Sharma', 'Patel', 'Gupta', 'Reddy', 'Singh'])} Industries Pvt. Ltd."
    c.drawString(65 * mm, y, company_name)

    y -= 8 * mm
    c.drawString(30 * mm, y, f"PAN: {pan}")

    y -= 8 * mm
    c.drawString(30 * mm, y, f"Return Period: {dates[0]} to {dates[1]}")

    y -= 8 * mm
    c.drawString(30 * mm, y, f"Date of Filing: {dates[2]}")

    # Tax details table
    y -= 20 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(30 * mm, y, "3. Details of Outward Supplies")

    y -= 10 * mm
    c.setFont("Helvetica", 10)
    rows = [
        ("Taxable Value", f"Rs. {amounts[0]}"),
        ("Integrated Tax (IGST)", f"Rs. {amounts[1]}"),
        ("Central Tax (CGST)", f"Rs. {amounts[2]}"),
        ("State Tax (SGST)", f"Rs. {amounts[3]}"),
        ("Total Tax Payable", f"Rs. {amounts[4]}"),
    ]

    for label, value in rows:
        c.drawString(30 * mm, y, f"{label}:")
        c.drawString(120 * mm, y, value)
        y -= 7 * mm

    # ITC section
    y -= 10 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(30 * mm, y, "4. Input Tax Credit (ITC)")
    y -= 10 * mm

    itc_amounts = [random_amount(50000, 5000000) for _ in range(3)]
    c.setFont("Helvetica", 10)
    c.drawString(30 * mm, y, f"ITC Available (GSTR-2A): Rs. {itc_amounts[0]}")
    y -= 7 * mm
    c.drawString(30 * mm, y, f"ITC Claimed (GSTR-3B): Rs. {itc_amounts[1]}")
    y -= 7 * mm
    c.drawString(30 * mm, y, f"ITC Reversed: Rs. {itc_amounts[2]}")

    c.save()

    # Build ground truth
    all_amounts_raw = [a.replace(',', '') for a in amounts + itc_amounts]
    ground_truth = {
        "gstin": [gstin],
        "pan": [pan],
        "invoice_total": all_amounts_raw,
        "date": dates,
        "company_name": company_name,
        "document_type": "GSTR-3B",
    }

    gt_path = os.path.join(output_dir, f"{sample_id}_ground_truth.json")
    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2)

    return ground_truth


def generate_bank_statement_pdf(output_dir: str, sample_id: str) -> dict:
    """Generate a synthetic bank statement PDF and ground truth."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
    except ImportError:
        return generate_text_based_sample(output_dir, sample_id, "bank")

    pdf_path = os.path.join(output_dir, f"{sample_id}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, h = A4

    pan = random_pan()
    account = ''.join(random.choices(string.digits, k=14))
    ifsc = ''.join(random.choices(string.ascii_uppercase, k=4)) + '0' + ''.join(random.choices(string.digits, k=6))
    dates = [random_date() for _ in range(10)]
    amounts = [random_amount(5000, 2000000) for _ in range(10)]

    c.setFont("Helvetica-Bold", 14)
    c.drawString(30 * mm, h - 25 * mm, random.choice(["State Bank of India", "HDFC Bank", "ICICI Bank", "Punjab National Bank"]))
    c.setFont("Helvetica", 10)
    c.drawString(30 * mm, h - 33 * mm, "ACCOUNT STATEMENT")

    y = h - 48 * mm
    c.drawString(30 * mm, y, f"Account No: {account}")
    y -= 7 * mm
    c.drawString(30 * mm, y, f"IFSC: {ifsc}")
    y -= 7 * mm
    c.drawString(30 * mm, y, f"PAN: {pan}")
    y -= 7 * mm
    c.drawString(30 * mm, y, f"Period: {dates[0]} to {dates[1]}")

    y -= 15 * mm
    c.setFont("Helvetica-Bold", 10)
    headers = ["Date", "Description", "Debit (Rs.)", "Credit (Rs.)", "Balance (Rs.)"]
    x_positions = [30, 55, 100, 130, 160]
    for hdr, x_pos in zip(headers, x_positions):
        c.drawString(x_pos * mm, y, hdr)

    y -= 3 * mm
    c.line(30 * mm, y, 185 * mm, y)
    y -= 5 * mm

    c.setFont("Helvetica", 9)
    balance = random.randint(100000, 5000000)
    txn_dates = []
    txn_amounts = []

    for i in range(min(8, len(dates) - 2)):
        dt = dates[i + 2]
        txn_dates.append(dt)
        is_credit = random.choice([True, False])
        amt = amounts[i]
        txn_amounts.append(amt)

        desc = random.choice([
            "NEFT/RTGS Transfer", "UPI Payment", "Cheque Deposit",
            "Salary Credit", "GST Payment", "EMI Deduction",
            "Vendor Payment", "Customer Receipt"
        ])

        c.drawString(30 * mm, y, dt)
        c.drawString(55 * mm, y, desc[:25])

        amt_num = int(amt.replace(',', ''))
        if is_credit:
            c.drawString(130 * mm, y, f"{amt}")
            balance += amt_num
        else:
            c.drawString(100 * mm, y, f"{amt}")
            balance -= amt_num

        c.drawString(160 * mm, y, f"{balance:,}")
        y -= 6 * mm

    c.save()

    ground_truth = {
        "gstin": [],
        "pan": [pan],
        "invoice_total": [a.replace(',', '') for a in txn_amounts],
        "date": txn_dates,
        "document_type": "Bank Statement",
    }

    gt_path = os.path.join(output_dir, f"{sample_id}_ground_truth.json")
    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2)

    return ground_truth


def generate_cibil_report_pdf(output_dir: str, sample_id: str) -> dict:
    """Generate a synthetic CIBIL commercial report PDF."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
    except ImportError:
        return generate_text_based_sample(output_dir, sample_id, "cibil")

    pdf_path = os.path.join(output_dir, f"{sample_id}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, h = A4

    pan = random_pan()
    cin = 'U' + ''.join(random.choices(string.digits, k=5)) + ''.join(random.choices(string.ascii_uppercase, k=2)) + \
          ''.join(random.choices(string.digits, k=4)) + ''.join(random.choices(string.ascii_uppercase, k=3)) + \
          ''.join(random.choices(string.digits, k=6))
    cmr = random.randint(1, 10)
    dpd = random.choice([0, 0, 0, 15, 30, 60, 90, 120])
    dishonoured = random.randint(0, 6)
    dates = [random_date() for _ in range(3)]

    c.setFont("Helvetica-Bold", 14)
    c.drawString(30 * mm, h - 25 * mm, "CIBIL COMMERCIAL CREDIT REPORT")
    c.setFont("Helvetica", 10)
    c.drawString(30 * mm, h - 33 * mm, f"Report Date: {dates[0]}")

    y = h - 48 * mm
    company_name = f"{random.choice(['Apex', 'Global', 'National', 'Premier'])} {random.choice(['Steel', 'Textiles', 'Pharma', 'Auto'])} Ltd."
    c.drawString(30 * mm, y, f"Company Name: {company_name}")
    y -= 7 * mm
    c.drawString(30 * mm, y, f"CIN: {cin}")
    y -= 7 * mm
    c.drawString(30 * mm, y, f"PAN: {pan}")

    y -= 15 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(30 * mm, y, "CIBIL MSME Rank (CMR)")
    y -= 10 * mm
    c.setFont("Helvetica", 11)
    c.drawString(30 * mm, y, f"CMR Score: {cmr}/10")
    y -= 7 * mm
    c.drawString(30 * mm, y, f"Risk Category: {'High Risk' if cmr >= 7 else 'Medium Risk' if cmr >= 4 else 'Low Risk'}")

    y -= 15 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(30 * mm, y, "Credit Profile Summary")
    y -= 10 * mm
    c.setFont("Helvetica", 10)
    c.drawString(30 * mm, y, f"Max DPD (Last 12 Months): {dpd} days")
    y -= 7 * mm
    c.drawString(30 * mm, y, f"Dishonoured Cheques: {dishonoured}")
    y -= 7 * mm
    amounts = [random_amount(1000000, 50000000) for _ in range(3)]
    c.drawString(30 * mm, y, f"Total Outstanding: Rs. {amounts[0]}")
    y -= 7 * mm
    c.drawString(30 * mm, y, f"Total Sanctioned: Rs. {amounts[1]}")
    y -= 7 * mm
    c.drawString(30 * mm, y, f"Total Overdue: Rs. {amounts[2]}")

    c.save()

    ground_truth = {
        "gstin": [],
        "pan": [pan],
        "invoice_total": [a.replace(',', '') for a in amounts],
        "date": dates,
        "cmr_rank": cmr,
        "max_dpd": dpd,
        "dishonoured_cheques": dishonoured,
        "document_type": "CIBIL Commercial Report",
    }

    gt_path = os.path.join(output_dir, f"{sample_id}_ground_truth.json")
    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2)

    return ground_truth


def generate_text_based_sample(output_dir: str, sample_id: str, doc_type: str) -> dict:
    """Fallback: Generate text file instead of PDF when reportlab unavailable."""
    gstin = random_gstin()
    pan = gstin[2:12] if doc_type == "gst" else random_pan()
    dates = [random_date() for _ in range(3)]
    amounts = [random_amount() for _ in range(3)]

    content = f"""
{doc_type.upper()} DOCUMENT — Sample {sample_id}

GSTIN: {gstin}
PAN: {pan}
Date: {dates[0]}
Amount: Rs. {amounts[0]}
Total: Rs. {amounts[1]}
Filing Date: {dates[1]}
Due Date: {dates[2]}
GST Amount: Rs. {amounts[2]}
"""
    txt_path = os.path.join(output_dir, f"{sample_id}.txt")
    with open(txt_path, "w") as f:
        f.write(content)

    ground_truth = {
        "gstin": [gstin] if doc_type == "gst" else [],
        "pan": [pan],
        "invoice_total": [a.replace(',', '') for a in amounts],
        "date": dates,
        "document_type": doc_type,
    }

    gt_path = os.path.join(output_dir, f"{sample_id}_ground_truth.json")
    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2)

    return ground_truth


def generate_company_profile(output_dir: str, company_name: str, sample_id: str) -> dict:
    """Generate a company profile for research depth testing."""
    profile = {
        "name": company_name,
        "gstin": random_gstin(),
        "pan": random_pan(),
        "sector": random.choice(["Steel", "Textiles", "Pharmaceuticals", "Auto Parts", "Electronics", "FMCG"]),
        "location": random.choice(["Mumbai", "Delhi", "Bengaluru", "Chennai", "Pune", "Ahmedabad"]),
        "promoters": [
            {"name": f"{random.choice(['Rajesh', 'Amit', 'Sunil', 'Vikram'])} {random.choice(['Kumar', 'Sharma', 'Patel', 'Singh'])}",
             "din": ''.join(random.choices(string.digits, k=8))},
        ],
        "known_facts": [
            f"Incorporated in {random.randint(1990, 2020)}",
            f"Annual turnover approximately Rs. {random_amount(10000000, 500000000)}",
            f"Located in {random.choice(['MIDC', 'SEZ', 'Industrial Area'])}",
        ],
        "loan_requested": int(random_amount(5000000, 100000000).replace(',', '')),
    }

    out_path = os.path.join(output_dir, f"{sample_id}.json")
    with open(out_path, "w") as f:
        json.dump(profile, f, indent=2)

    return profile


def main():
    smoke_dir = PROJECT_ROOT / "tests" / "extraction_smoke"
    research_dir = PROJECT_ROOT / "tests" / "research_depth"
    os.makedirs(smoke_dir, exist_ok=True)
    os.makedirs(research_dir, exist_ok=True)

    print("Generating synthetic test data for Intelli-Credit...")

    # Generate extraction smoke test samples
    generators = [
        ("sample_gst_01", generate_gst_return_pdf),
        ("sample_gst_02", generate_gst_return_pdf),
        ("sample_bank_01", generate_bank_statement_pdf),
        ("sample_bank_02", generate_bank_statement_pdf),
        ("sample_cibil_01", generate_cibil_report_pdf),
    ]

    for sample_id, gen_func in generators:
        print(f"  Generating {sample_id}...")
        gt = gen_func(str(smoke_dir), sample_id)
        print(f"    → {gt.get('document_type', 'unknown')}: "
              f"GSTIN={len(gt.get('gstin', []))}, "
              f"PAN={len(gt.get('pan', []))}, "
              f"amounts={len(gt.get('invoice_total', []))}, "
              f"dates={len(gt.get('date', []))}")

    # Generate research depth test company profiles
    companies = [
        ("Apex Steel Industries Ltd.", "company_apex_steel"),
        ("Greenfield Pharma Pvt. Ltd.", "company_greenfield_pharma"),
        ("National Auto Components Ltd.", "company_national_auto"),
    ]

    for company_name, sample_id in companies:
        print(f"  Generating company profile: {company_name}...")
        generate_company_profile(str(research_dir), company_name, sample_id)

    print(f"\nGenerated {len(generators)} extraction smoke samples in {smoke_dir}")
    print(f"Generated {len(companies)} company profiles in {research_dir}")


if __name__ == "__main__":
    main()

"""
Professional PDF CAM generator using ReportLab.

Produces a multi-page Credit Appraisal Memo with embedded risk gauges,
waterfall-style rule breakdowns, and graph summary sections.
"""
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Wedge, Line
from reportlab.graphics import renderPDF

WIDTH, HEIGHT = A4

# ── Color palette ────────────────────────────────────────────────────────────
BRAND = colors.HexColor("#1e40af")
BRAND_LIGHT = colors.HexColor("#3b82f6")
GREEN = colors.HexColor("#16a34a")
AMBER = colors.HexColor("#d97706")
RED = colors.HexColor("#dc2626")
SLATE = colors.HexColor("#475569")
SLATE_LIGHT = colors.HexColor("#94a3b8")
BG_LIGHT = colors.HexColor("#f8fafc")
WHITE = colors.white

VERDICT_COLORS = {
    "APPROVE": GREEN,
    "CONDITIONAL": AMBER,
    "REJECT": RED,
}


def _risk_color(score: float):
    if score <= 0.3:
        return GREEN
    if score <= 0.6:
        return AMBER
    return RED


def _gauge_drawing(score: float, size=80):
    """Draw a semi-circular risk gauge."""
    d = Drawing(size, size * 0.7)
    cx, cy = size / 2, size * 0.5
    r_outer = size * 0.4
    r_inner = size * 0.26

    # Background arc (gray)
    d.add(Wedge(cx, cy, r_outer, -40, 220, innerRadius=r_inner,
                fillColor=colors.HexColor("#e2e8f0"), strokeColor=None))

    # Filled arc
    angle_span = 260  # from -40 to 220
    fill_angle = score * angle_span
    d.add(Wedge(cx, cy, r_outer, 220 - fill_angle, 220, innerRadius=r_inner,
                fillColor=_risk_color(score), strokeColor=None))

    # Score text
    label = f"{int(score * 100)}%"
    d.add(String(cx, cy - 8, label, fontSize=11, fontName="Helvetica-Bold",
                 fillColor=_risk_color(score), textAnchor="middle"))

    return d


def _section_heading(text):
    return Paragraph(text, ParagraphStyle(
        "SectionHeading", fontName="Helvetica-Bold", fontSize=12,
        textColor=BRAND, spaceBefore=14, spaceAfter=6,
        borderWidth=0, borderPadding=0,
    ))


def _make_styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("Title2", parent=base["Title"],
                                fontName="Helvetica-Bold", fontSize=20,
                                textColor=BRAND, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("Subtitle2", parent=base["Normal"],
                                   fontName="Helvetica", fontSize=10,
                                   textColor=SLATE_LIGHT, alignment=TA_CENTER),
        "body": ParagraphStyle("Body2", parent=base["Normal"],
                               fontName="Helvetica", fontSize=9.5,
                               textColor=SLATE, leading=13),
        "body_bold": ParagraphStyle("BodyBold", parent=base["Normal"],
                                    fontName="Helvetica-Bold", fontSize=9.5,
                                    textColor=SLATE, leading=13),
        "small": ParagraphStyle("Small2", parent=base["Normal"],
                                fontName="Helvetica", fontSize=8,
                                textColor=SLATE_LIGHT, leading=10),
        "verdict": ParagraphStyle("Verdict", fontName="Helvetica-Bold",
                                  fontSize=16, alignment=TA_CENTER),
    }
    return styles


def generate_cam_pdf(
    output_path: str,
    company_name: str,
    loan_amount: float,
    loan_purpose: str,
    sector: str,
    recommendation: str,
    risk_score: float,
    recommended_amount: float,
    rule_firings: list,
    graph_trace: dict,
    evidence_judge: dict,
    trace: dict,
):
    """Generate a professional multi-page PDF CAM."""
    styles = _make_styles()
    elements = []

    # ── Page 1: Title Block ──────────────────────────────────────────────────
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("CREDIT APPRAISAL MEMO", styles["title"]))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Intelli-Credit Decisioning Engine · Confidential", styles["subtitle"]))
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="80%", thickness=1, color=BRAND_LIGHT,
                               spaceAfter=12, spaceBefore=4, hAlign="CENTER"))

    # Borrower info table
    loan_str = f"₹{loan_amount:,.0f}" if loan_amount else "—"
    rec_amt_str = f"₹{recommended_amount:,.0f}" if recommended_amount else "—"
    risk_str = f"{risk_score:.2f}" if risk_score is not None else "—"

    info_data = [
        ["Borrower", company_name, "Sector", sector or "—"],
        ["Loan Requested", loan_str, "Purpose", loan_purpose or "Working Capital"],
        ["Recommended Amt", rec_amt_str, "Risk Score", risk_str],
    ]

    info_table = Table(info_data, colWidths=[90, 160, 90, 160])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), SLATE_LIGHT),
        ("TEXTCOLOR", (2, 0), (2, -1), SLATE_LIGHT),
        ("TEXTCOLOR", (1, 0), (1, -1), SLATE),
        ("TEXTCOLOR", (3, 0), (3, -1), SLATE),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, -1), BG_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, SLATE_LIGHT),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 14))

    # ── Verdict + Risk Gauge side by side ────────────────────────────────────
    verdict_color = VERDICT_COLORS.get(recommendation, SLATE)

    gauge = _gauge_drawing(min(1, max(0, risk_score or 0)), size=90)

    verdict_para = Paragraph(
        f'<font color="{verdict_color.hexval()}">{recommendation or "PENDING"}</font>',
        styles["verdict"]
    )
    verdict_label = Paragraph("RECOMMENDATION", ParagraphStyle(
        "VL", fontName="Helvetica", fontSize=8, textColor=SLATE_LIGHT,
        alignment=TA_CENTER, spaceBefore=2))
    gauge_label = Paragraph("RISK SCORE", ParagraphStyle(
        "GL", fontName="Helvetica", fontSize=8, textColor=SLATE_LIGHT,
        alignment=TA_CENTER, spaceBefore=2))

    verdict_table = Table(
        [[verdict_label, gauge_label],
         [verdict_para, gauge]],
        colWidths=[250, 250],
    )
    verdict_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(verdict_table)
    elements.append(Spacer(1, 10))

    # ── Executive Summary ────────────────────────────────────────────────────
    exec_summary = trace.get("executive_summary", "")
    # Also check orchestration_impact
    orchestration = trace.get("orchestration_impact", {})
    if not exec_summary and orchestration:
        pre = orchestration.get("pre_orchestration_risk_score", "?")
        post = orchestration.get("post_orchestration_risk_score", risk_score)
        exec_summary = (
            f"The automated analysis pipeline assessed {company_name} with a final risk score "
            f"of {post}. {len(rule_firings)} rules were triggered during evaluation."
        )
    if exec_summary:
        elements.append(_section_heading("Executive Summary"))
        elements.append(Paragraph(exec_summary, styles["body"]))
        elements.append(Spacer(1, 8))

    # ── Rule Firings (Waterfall table) ───────────────────────────────────────
    if rule_firings:
        elements.append(_section_heading("Rule Firings & Risk Adjustments"))

        waterfall_data = [["Rule", "Severity", "Adjustment", "Rationale"]]
        running = 0
        for rf in rule_firings:
            adj = rf.get("risk_adjustment", 0)
            running += adj
            slug = (rf.get("rule_slug") or rf.get("rule_id", "—")).replace("_", " ").title()
            sev = rf.get("severity", "—")
            rat = rf.get("rationale", "")
            if len(rat) > 90:
                rat = rat[:87] + "..."
            waterfall_data.append([
                slug,
                sev,
                f"+{adj:.2f}" if adj > 0 else f"{adj:.2f}",
                Paragraph(rat, styles["small"]),
            ])
        waterfall_data.append(["Total Adjustment", "", f"+{running:.2f}", ""])

        n_rows = len(waterfall_data)
        wf_table = Table(waterfall_data, colWidths=[110, 60, 65, 265])
        wf_styles = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("BACKGROUND", (0, 0), (-1, 0), BRAND),
            ("BACKGROUND", (0, 1), (-1, -2), BG_LIGHT),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, -1), (-1, -1), WHITE),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 0.5, SLATE_LIGHT),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        wf_table.setStyle(TableStyle(wf_styles))
        elements.append(wf_table)
        elements.append(Spacer(1, 10))
    else:
        elements.append(_section_heading("Rule Firings"))
        elements.append(Paragraph("No rules were triggered — clean profile.", styles["body"]))
        elements.append(Spacer(1, 8))

    # ── Graph Analysis ───────────────────────────────────────────────────────
    elements.append(_section_heading("Transaction Graph Analysis"))

    gnn_label = graph_trace.get("gnn_label", "—")
    gnn_risk = graph_trace.get("gnn_risk_score", 0)
    n_nodes = graph_trace.get("node_count", 0)
    n_edges = graph_trace.get("edge_count", 0)
    n_cycles = graph_trace.get("suspicious_cycles", 0)
    fraud_alerts = graph_trace.get("fraud_alerts", [])

    graph_data = [
        ["Metric", "Value"],
        ["Nodes", str(n_nodes)],
        ["Edges", str(n_edges)],
        ["GNN Classification", gnn_label.replace("_", " ").title()],
        ["GNN Risk Score", f"{gnn_risk:.2f}"],
        ["Suspicious Cycles", str(n_cycles)],
        ["Fraud Alerts", str(len(fraud_alerts))],
    ]
    g_table = Table(graph_data, colWidths=[180, 320])
    g_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("BACKGROUND", (0, 1), (-1, -1), BG_LIGHT),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, SLATE_LIGHT),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    elements.append(g_table)

    if fraud_alerts:
        elements.append(Spacer(1, 6))
        for alert in fraud_alerts[:5]:
            severity = alert.get("severity", "?")
            atype = alert.get("type", "?")
            entities = ", ".join(alert.get("entities", [])[:4])
            color_hex = RED.hexval() if severity == "CRITICAL" else AMBER.hexval()
            elements.append(Paragraph(
                f'<font color="{color_hex}">⚠ [{severity}]</font> '
                f'{atype}: {entities}',
                styles["body"]
            ))

    elements.append(Spacer(1, 8))

    # ── Evidence Quality ─────────────────────────────────────────────────────
    if evidence_judge:
        elements.append(_section_heading("Evidence Quality Assessment"))
        precision = evidence_judge.get("precision_at_10", "—")
        corroboration = evidence_judge.get("corroboration_rate", "—")
        composite = evidence_judge.get("composite_score", "—")

        eq_data = [
            ["Metric", "Value"],
            ["Precision@10", f"{precision}" if isinstance(precision, str) else f"{precision:.1%}"],
            ["Corroboration Rate", f"{corroboration}" if isinstance(corroboration, str) else f"{corroboration:.1%}"],
            ["Composite Score", f"{composite}" if isinstance(composite, str) else f"{composite:.2f}"],
        ]
        eq_table = Table(eq_data, colWidths=[180, 320])
        eq_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("BACKGROUND", (0, 0), (-1, 0), BRAND),
            ("BACKGROUND", (0, 1), (-1, -1), BG_LIGHT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 0.5, SLATE_LIGHT),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ]))
        elements.append(eq_table)
        elements.append(Spacer(1, 8))

    # ── Counterfactual Scenarios ─────────────────────────────────────────────
    counterfactuals = trace.get("counterfactuals", {})
    scenarios = counterfactuals.get("scenarios", []) if isinstance(counterfactuals, dict) else []
    if scenarios:
        elements.append(_section_heading("What-If Scenarios"))
        for s in scenarios[:5]:
            desc = s.get("description", "")
            delta = s.get("delta_risk_score", 0)
            hyp_rec = s.get("hypothetical_recommendation", "—")
            arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            color = RED.hexval() if delta > 0 else GREEN.hexval()
            elements.append(Paragraph(
                f'• {desc} — <font color="{color}">{arrow} {delta:+.2f}</font> → {hyp_rec}',
                styles["body"]
            ))
        elements.append(Spacer(1, 8))

    # ── Footer: Disclaimer ───────────────────────────────────────────────────
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=SLATE_LIGHT, spaceAfter=6))
    elements.append(Paragraph(
        "This Credit Appraisal Memo was generated by the Intelli-Credit Decisioning Engine. "
        "All assessments are based on automated analysis of submitted documents, public records, "
        "and neuro-symbolic rule evaluation. This memo is for internal use only and does not "
        "constitute a binding credit decision.",
        styles["small"]
    ))

    # ── Build PDF ────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        title=f"CAM - {company_name}",
        author="Intelli-Credit",
    )
    doc.build(elements)
    return output_path

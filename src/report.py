"""PDF financial report (bonus feature) built with ReportLab."""
from __future__ import annotations

import io
import re
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import APP_NAME, DISCLAIMER, EXPENSE_CATEGORIES
from .financial_calculator import FinancialInput, FinancialMetrics, format_money

INK = colors.HexColor("#14382E")
MUTED = colors.HexColor("#5C6B64")
RULE = colors.HexColor("#D5DFD9")
HIGHLIGHT = colors.HexColor("#FBEFD2")


def _pdf_money(amount: float, currency: str) -> str:
    """Built-in PDF fonts lack the rupee sign (₹), so spell the code out instead."""
    return format_money(amount, currency).replace("₹", "INR ")


def _md_to_para(text: str) -> str:
    """Escape text and convert **bold** to ReportLab markup."""
    safe = escape((text or "").replace("₹", "INR "))
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)


def build_pdf_report(data: FinancialInput, metrics: FinancialMetrics, analysis: dict | None,
                     narrative: str | None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title=f"{APP_NAME} report")
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], textColor=INK, alignment=0, fontSize=20, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], textColor=INK, fontSize=13, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=base["BodyText"], fontSize=9.5, leading=13.5)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=11, textColor=MUTED)
    cur = data.currency
    story = [
        Paragraph(f"{APP_NAME} — monthly financial summary", h1),
        Paragraph(f"Generated {datetime.now():%d %B %Y, %H:%M} · Goal: {escape(data.financial_goal)}", small),
        Spacer(1, 6),
        Table([[Paragraph(f"<b>Educational use only.</b> {escape(DISCLAIMER)}", small)]],
              colWidths=[doc.width], style=[("BACKGROUND", (0, 0), (-1, -1), HIGHLIGHT),
                                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E3A92B")),
                                            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]),
        Paragraph("Calculated by Python", h2),
    ]
    rows = [
        ["Monthly income", _pdf_money(metrics.monthly_income, cur), "Savings ratio", f"{metrics.savings_ratio:.1f}%"],
        ["Total expenses", _pdf_money(metrics.total_expenses, cur), "Expense ratio", f"{metrics.expense_ratio:.1f}%"],
        ["Remaining income", _pdf_money(metrics.remaining_income, cur), "Debt share of income", f"{metrics.debt_ratio:.1f}%"],
        ["Monthly savings", _pdf_money(metrics.savings, cur), "Preliminary score",
         f"{metrics.preliminary_score}/100 ({metrics.score_band})"],
    ]
    grid = TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                       ("TEXTCOLOR", (2, 0), (2, -1), MUTED), ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                       ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"), ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
                       ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)])
    story.append(Table(rows, colWidths=[doc.width * w for w in (0.22, 0.26, 0.24, 0.28)], style=grid))

    story.append(Paragraph("Expense breakdown", h2))
    exp_rows = [["Category", "Amount", "Share of expenses"]] + [
        [label, _pdf_money(data.expenses[k], cur), f"{metrics.category_shares.get(k, 0):.1f}%"]
        for k, label in EXPENSE_CATEGORIES.items() if data.expenses[k] > 0]
    story.append(Table(exp_rows, colWidths=[doc.width * 0.5, doc.width * 0.25, doc.width * 0.25],
                       style=TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9),
                                         ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                         ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                                         ("ALIGN", (1, 0), (-1, -1), "RIGHT")])))

    if analysis:
        story.append(Paragraph("AI-generated insights (educational)", h2))
        story.append(Paragraph(f"<b>Health score:</b> {analysis['financial_health_score']}/100 · "
                               f"<b>Risk level:</b> {escape(analysis['risk_level'])}", body))
        story.append(Spacer(1, 4))
        story.append(Paragraph(_md_to_para(analysis["financial_summary"]), body))
        for title, key in [("Top priorities", "top_priorities"), ("Budget recommendations", "budget_recommendations"),
                           ("Savings strategy", "savings_strategy"), ("Next month's action plan", "next_month_action_plan")]:
            if analysis.get(key):
                story.append(Paragraph(title, h2))
                for i, item in enumerate(analysis[key], 1):
                    story.append(Paragraph(f"{i}. {_md_to_para(item)}", body))
        if analysis.get("spending_analysis"):
            story.append(Paragraph("Spending analysis", h2))
            for item in analysis["spending_analysis"]:
                story.append(Paragraph(f"<b>{escape(item['category'])}</b> — {_md_to_para(item['observation'])} "
                                       f"<i>{_md_to_para(item['recommendation'])}</i>", body))
    if narrative:
        story.append(Paragraph("Written recommendation", h2))
        for para in [p for p in narrative.split("\n") if p.strip()]:
            story.append(Paragraph(_md_to_para(re.sub(r"^#+\s*|^[-*]\s+", "", para.strip())), body))
    story += [Spacer(1, 10), Paragraph(escape(DISCLAIMER), small)]
    doc.build(story)
    return buffer.getvalue()

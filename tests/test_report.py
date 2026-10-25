"""PDF report generation (bonus)."""
from conftest import VALID_ANALYSIS
from src.financial_calculator import FinancialInput, analyse
from src.report import build_pdf_report


def test_pdf_with_and_without_ai():
    d = FinancialInput(4000, {"housing": 1200, "food": 500}, 400, "Save money", currency="INR")
    m = analyse(d)
    for analysis, narrative in [(VALID_ANALYSIS, "**Plan:** save ₹500 & cut <costs>."), (None, None)]:
        pdf = build_pdf_report(d, m, analysis, narrative)
        assert pdf.startswith(b"%PDF") and len(pdf) > 2000

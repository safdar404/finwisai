"""Safe JSON parsing and CSV import."""
import json

from conftest import VALID_ANALYSIS
from src.financial_calculator import FinancialInput, analyse
from src.utils import build_fallback_analysis, match_category, parse_expense_csv, parse_financial_json


def test_parses_clean_json():
    data, problems = parse_financial_json(json.dumps(VALID_ANALYSIS))
    assert data["financial_health_score"] == 82 and problems == []


def test_parses_fenced_json_with_chatter():
    text = "Sure! Here it is:\n```json\n" + json.dumps(VALID_ANALYSIS) + "\n```\nHope this helps."
    data, _ = parse_financial_json(text)
    assert data["risk_level"] == "LOW"


def test_trailing_commas_and_braces_in_strings():
    raw = json.dumps({**VALID_ANALYSIS, "financial_summary": "Use {curly} braces"})[:-1] + ",}"
    data, _ = parse_financial_json(raw)
    assert data["financial_summary"] == "Use {curly} braces"


def test_normalises_types():
    raw = {**VALID_ANALYSIS, "financial_health_score": "105 points", "risk_level": "moderate",
           "top_priorities": "1. Save more\n2. Spend less", "savings_strategy": [{"step": "Automate", "why": "habit"}]}
    data, _ = parse_financial_json(json.dumps(raw))
    assert data["financial_health_score"] == 100 and data["risk_level"] == "MEDIUM"
    assert data["top_priorities"] == ["Save more", "Spend less"]
    assert data["savings_strategy"] == ["Automate — habit"]


def test_missing_optional_keys_noted():
    raw = {k: VALID_ANALYSIS[k] for k in ("financial_summary", "financial_health_score", "risk_level")}
    data, problems = parse_financial_json(json.dumps(raw))
    assert data["top_priorities"] == [] and any("top_priorities" in p for p in problems)


def test_invalid_inputs_never_raise():
    for bad in ["", "not json", "{broken", "[1,2]", json.dumps({"financial_summary": "x"}),
                json.dumps({**VALID_ANALYSIS, "risk_level": "purple"})]:
        data, problems = parse_financial_json(bad)
        assert data is None and problems


def test_fallback_matches_schema():
    d = FinancialInput(2000, {"housing": 1500, "food": 900}, 0, "Pay off debt")
    fb = build_fallback_analysis(d, analyse(d))
    data, problems = parse_financial_json(json.dumps(fb))
    assert data is not None and data["risk_level"] == "HIGH"


def test_csv_import_months_and_matching():
    raw = b"month,category,amount\n2026-09,Rent,1000\n2026-09,Netflix,15\n2026-10,Groceries,\"1,200\"\n2026-10,Rent,x\n"
    months, warnings = parse_expense_csv(raw)
    assert list(months) == ["2026-09", "2026-10"]
    assert months["2026-09"]["housing"] == 1000 and months["2026-09"]["entertainment"] == 15
    assert months["2026-10"]["food"] == 1200 and warnings
    assert match_category("Unknown thing") == "other"


def test_csv_requires_columns():
    months, warnings = parse_expense_csv(b"foo,bar\n1,2\n")
    assert months == {} and warnings


def test_md_safe_escapes_dollars_for_streamlit():
    from src.utils import md_safe, md_safe_stream
    assert md_safe("Cut $850 to $700") == "Cut \\$850 to \\$700"
    assert md_safe("already \\$5") == "already \\$5"            # not double-escaped
    assert "".join(md_safe_stream(["Save $", "50 now"])) == "Save \\$50 now"

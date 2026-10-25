"""Deterministic calculations, including the five assignment test scenarios."""
import pytest

from src.config import EXPENSE_CATEGORIES, TEST_SCENARIOS
from src.financial_calculator import (FinancialInput, analyse, build_prompt_inputs, format_money,
                                      safe_percentage, score_band)


def run(name):
    s = TEST_SCENARIOS[name]
    data = FinancialInput(s["income"], s["expenses"], s["savings"], "Save money")
    return data, analyse(data)


def test_ten_categories():
    assert len(EXPENSE_CATEGORIES) == 10


def test_scenario_1_high_income_low_spending():
    _, m = run("1 · High income, low spending")
    assert m.total_expenses == 2000 and m.remaining_income == 6000
    assert m.preliminary_score >= 80 and m.rule_risk_level == "LOW"


def test_scenario_2_spending_above_income():
    _, m = run("2 · Spending above income")
    assert m.remaining_income < 0 and m.expense_ratio > 100
    assert m.preliminary_score < 40 and m.rule_risk_level == "HIGH"
    assert any("higher than income" in f for f in m.flags)


def test_scenario_3_heavy_debt():
    _, m = run("3 · Heavy debt repayments")
    assert m.debt_ratio == 50.0
    assert m.rule_risk_level in ("MEDIUM", "HIGH")


def test_scenario_4_strong_saver():
    _, m = run("4 · Strong saver")
    assert m.savings_ratio == 30.0
    assert m.preliminary_score >= 80 and m.rule_risk_level == "LOW"


def test_scenario_5_break_even():
    _, m = run("5 · Break-even month")
    assert m.remaining_income == 0
    assert m.rule_risk_level in ("MEDIUM", "HIGH")


def test_formulas_match_spec():
    data = FinancialInput(4000, {"housing": 1000, "food": 500}, 600, "Save money")
    m = analyse(data)
    assert m.total_expenses == 1500
    assert m.remaining_income == 2500
    assert m.savings_ratio == pytest.approx(600 / 4000 * 100)
    assert m.expense_ratio == pytest.approx(1500 / 4000 * 100)


def test_zero_income_no_division_error():
    m = analyse(FinancialInput(0, {"food": 300}, 0, "Save money"))
    assert m.savings_ratio == 0 and m.expense_ratio == 0 and m.preliminary_score == 0
    assert m.rule_risk_level == "HIGH"
    assert safe_percentage(5, 0) == 0.0


def test_negative_inputs_are_clamped():
    m = analyse(FinancialInput(-100, {"food": -50}, -10, "Save money"))
    assert m.monthly_income == 0 and m.total_expenses == 0


def test_deterministic():
    a = analyse(FinancialInput(3000, {"food": 400}, 300, "Save money"))
    b = analyse(FinancialInput(3000, {"food": 400}, 300, "Save money"))
    assert a == b


def test_score_bands():
    assert [score_band(s) for s in (95, 70, 45, 10)] == ["Strong", "Generally healthy", "Needs improvement",
                                                         "High attention"]


def test_goal_tracker():
    m = analyse(FinancialInput(4000, {"food": 400}, 500, "Plan a vacation", goal_target=3000, goal_saved=1000))
    assert m.goal_progress == pytest.approx(33.33, 0.01) and m.months_to_goal == 4.0


def test_prompt_inputs_and_money_format():
    data, m = run("4 · Strong saver")
    inputs = build_prompt_inputs(data, m)
    assert inputs["monthly_income"] == "$4,000.00" and inputs["savings_ratio"] == "30.0%"
    assert "Housing / rent: $1,000.00 (25.0% of income)" in inputs["expense_breakdown"]
    assert format_money(-12.5, "EUR") == "-€12.50" and format_money(1500, "JPY") == "¥1,500"

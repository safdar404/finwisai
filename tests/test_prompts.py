"""Prompt templates contain the required variables and safety rules."""
from langchain_core.messages import HumanMessage, SystemMessage

from src.prompts import ANALYSIS_CHAT_TEMPLATE, ANALYSIS_PROMPT, NARRATIVE_CHAT_TEMPLATE

REQUIRED = {"monthly_income", "total_expenses", "remaining_income", "savings", "savings_ratio",
            "expense_ratio", "financial_goal", "expense_breakdown"}


def _values(template):
    return {v: f"<{v}>" for v in template.input_variables}


def test_prompt_template_has_required_variables():
    assert REQUIRED <= set(ANALYSIS_PROMPT.input_variables)
    text = ANALYSIS_PROMPT.format(**_values(ANALYSIS_PROMPT))
    assert all(f"<{v}>" in text for v in REQUIRED)
    assert '"financial_health_score": 0' in text          # schema inserted verbatim


def test_chat_template_system_plus_human():
    messages = ANALYSIS_CHAT_TEMPLATE.format_messages(**_values(ANALYSIS_CHAT_TEMPLATE))
    assert [type(m) for m in messages] == [SystemMessage, HumanMessage]
    assert "Never recommend specific stocks" in messages[0].content
    assert "<expense_breakdown>" in messages[1].content


def test_narrative_template():
    messages = NARRATIVE_CHAT_TEMPLATE.format_messages(**_values(NARRATIVE_CHAT_TEMPLATE))
    assert "not financial advice" in messages[0].content

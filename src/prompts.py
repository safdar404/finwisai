"""Prompt engineering: PromptTemplate, ChatPromptTemplate and the JSON schema.

Design:
* ANALYSIS_PROMPT (PromptTemplate) is the reusable single-string template that
  carries every financial variable.
* ANALYSIS_CHAT_TEMPLATE (ChatPromptTemplate) wraps it: a system message with the
  assistant's role and safety rules + a human message built from ANALYSIS_PROMPT.
* NARRATIVE_CHAT_TEMPLATE produces the streamed, written recommendation.
"""
from __future__ import annotations

import json

from langchain_core.prompts import (ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate,
                                    SystemMessagePromptTemplate)

# ── JSON schema the model must return ───────────────────────────────────
JSON_SCHEMA_EXAMPLE = {
    "financial_summary": "",
    "financial_health_score": 0,
    "spending_analysis": [{"category": "", "observation": "", "recommendation": ""}],
    "risk_level": "",
    "top_priorities": [],
    "budget_recommendations": [],
    "savings_strategy": [],
    "next_month_action_plan": [],
}
JSON_SCHEMA = json.dumps(JSON_SCHEMA_EXAMPLE, indent=2)

# ── System role + safety rules ──────────────────────────────────────────
SAFETY_RULES = """Safety requirements (always follow):
1. You are an EDUCATIONAL budgeting assistant, not a licensed financial adviser.
2. Never recommend specific stocks, funds, cryptocurrencies or other investments.
3. Never promise or guarantee any financial outcome, return or approval.
4. Never ask for or mention bank logins, card numbers or account details; you cannot move money.
5. Use only the numbers provided. Do not invent income, expenses or facts.
6. Keep suggestions practical, respectful and non-judgemental.
7. When a situation looks serious (e.g. expenses above income or heavy debt), suggest speaking
   with a qualified financial professional or a non-profit credit counsellor."""

SYSTEM_PROMPT = f"""You are FinWise AI, a friendly educational assistant that helps people understand
their monthly budget. The deterministic numbers (totals, ratios and a preliminary score) were
calculated in Python and are correct — explain and interpret them; do not recalculate them differently.

{SAFETY_RULES}"""

# ── PromptTemplate: single string carrying all financial variables ──────
ANALYSIS_TEMPLATE = """Analyse this person's monthly finances for educational purposes.

Currency: {currency}
Monthly income: {monthly_income}
Total expenses: {total_expenses}
Remaining income (income - expenses): {remaining_income}
Current monthly savings: {savings}
Savings ratio: {savings_ratio}
Expense ratio: {expense_ratio}
Debt repayments as share of income: {debt_ratio}
Financial goal: {financial_goal}

Expense breakdown:
{expense_breakdown}

Python rule-based preliminary score: {preliminary_score}/100 (rule-based risk: {rule_risk_level})
Warning flags found by Python:
{warning_flags}

Instructions:
- Give a financial_health_score from 0 to 100. Stay within about 15 points of the preliminary
  score unless the data clearly justifies more, and explain the main reason in the summary.
  Bands: 80-100 strong, 60-79 generally healthy, 40-59 needs improvement, below 40 high attention.
- risk_level must be exactly one of: LOW, MEDIUM, HIGH.
- spending_analysis: cover the 3 to 5 most significant categories (largest or most concerning).
- top_priorities: 3 items. budget_recommendations, savings_strategy and next_month_action_plan:
  3 to 5 short, concrete items each, using the person's currency and numbers.
- Tailor everything to the financial goal.

Return ONLY valid JSON (no markdown, no comments) that matches exactly this schema:
{json_schema}"""

ANALYSIS_PROMPT = PromptTemplate(
    template=ANALYSIS_TEMPLATE,
    input_variables=[
        "monthly_income", "total_expenses", "remaining_income", "savings", "savings_ratio",
        "expense_ratio", "financial_goal", "expense_breakdown",
        "currency", "debt_ratio", "preliminary_score", "rule_risk_level", "warning_flags",
    ],
    partial_variables={"json_schema": JSON_SCHEMA},
)

# ── ChatPromptTemplate: system instructions + safety + dynamic user data ─
ANALYSIS_CHAT_TEMPLATE = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
    HumanMessagePromptTemplate(prompt=ANALYSIS_PROMPT),
])

# ── Narrative (streamed) recommendation ─────────────────────────────────
NARRATIVE_SYSTEM = SYSTEM_PROMPT + """

Write in plain, warm language. Use short Markdown sections with bold lead-ins, no tables.
Keep it under 280 words. End with one sentence reminding the reader this is educational
and not financial advice."""

NARRATIVE_HUMAN = """Write a personalised monthly budget recommendation for this person.

Income {monthly_income}; expenses {total_expenses}; remaining {remaining_income};
savings {savings} ({savings_ratio} of income); expense ratio {expense_ratio}.
Goal: {financial_goal}.

Expense breakdown:
{expense_breakdown}

Structured analysis already shown to the user (stay consistent with it):
Health score {health_score}/100, risk level {risk_level}.
Top priorities: {top_priorities}

Cover: what is going well, the biggest opportunity, a simple plan for next month, and how
it moves them toward their goal."""

NARRATIVE_CHAT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", NARRATIVE_SYSTEM),
    ("human", NARRATIVE_HUMAN),
])

# ── JSON repair (used once if the model returns invalid JSON) ───────────
REPAIR_TEMPLATE = PromptTemplate.from_template(
    """The text below was supposed to be JSON matching this schema but could not be parsed.
Problems: {errors}

Schema:
{json_schema}

Text:
{bad_output}

Return ONLY the corrected, valid JSON object."""
).partial(json_schema=JSON_SCHEMA)

# ── Follow-up conversation ──────────────────────────────────────────────
FOLLOW_UP_SYSTEM = SYSTEM_PROMPT + """

You are now answering follow-up questions about the analysis in this conversation.
Answer briefly (under 150 words) and only about budgeting and the user's numbers.
If asked for investment picks, guarantees or anything unsafe, politely decline and explain why."""

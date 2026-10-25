"""Safe JSON parsing, validation and small helpers.

LLMs sometimes wrap JSON in ```fences```, add a sentence before it, use the
wrong type or forget a key. `parse_financial_json` copes with all of these and
never raises: it returns (analysis | None, list_of_problems).
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from .config import EXPENSE_CATEGORIES, RISK_LEVELS
from .financial_calculator import FinancialInput, FinancialMetrics, format_money


# ── Schema ──────────────────────────────────────────────────────────────
class SpendingItem(BaseModel):
    category: str = ""
    observation: str = ""
    recommendation: str = ""


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [part for part in re.split(r"\n|;\s*", value) if part.strip()]
    if not isinstance(value, list):
        value = [value]
    out = []
    for item in value:
        if isinstance(item, dict):                      # e.g. {"step": "...", "detail": "..."}
            item = " — ".join(str(v) for v in item.values() if v)
        text = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", str(item)).strip()
        if text:
            out.append(text)
    return out


class FinancialAnalysis(BaseModel):
    financial_summary: str
    financial_health_score: int = Field(ge=0, le=100)
    spending_analysis: list[SpendingItem] = []
    risk_level: str
    top_priorities: list[str] = []
    budget_recommendations: list[str] = []
    savings_strategy: list[str] = []
    next_month_action_plan: list[str] = []

    @field_validator("financial_health_score", mode="before")
    @classmethod
    def _score(cls, v):
        if isinstance(v, str):
            match = re.search(r"-?\d+(\.\d+)?", v)
            v = float(match.group()) if match else 0
        return int(max(0, min(100, round(float(v)))))

    @field_validator("risk_level", mode="before")
    @classmethod
    def _risk(cls, v):
        text = str(v or "").upper()
        for level in ("HIGH", "MEDIUM", "LOW"):
            if level in text:
                return level
        if "MODERATE" in text:
            return "MEDIUM"
        raise ValueError(f"risk_level must be one of {RISK_LEVELS}")

    @field_validator("top_priorities", "budget_recommendations", "savings_strategy",
                     "next_month_action_plan", mode="before")
    @classmethod
    def _lists(cls, v):
        return _as_text_list(v)

    @field_validator("spending_analysis", mode="before")
    @classmethod
    def _spending(cls, v):
        if isinstance(v, dict):                          # {"Food": {...}} or a single item
            if {"category", "observation"} & set(v):
                v = [v]
            else:
                v = [{"category": k, **(val if isinstance(val, dict) else {"observation": str(val)})}
                     for k, val in v.items()]
        return [item for item in (v or []) if isinstance(item, dict)]


REQUIRED_KEYS = list(FinancialAnalysis.model_fields)


# ── Parsing ─────────────────────────────────────────────────────────────
def extract_json_block(text: str) -> str | None:
    """Return the first balanced {...} object in text (ignores fences and chatter)."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    while start != -1:
        depth, in_string, escaped = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        start = text.find("{", start + 1)
    return None


def _loads_lenient(block: str) -> Any:
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        # Common model slip: trailing commas before } or ].
        return json.loads(re.sub(r",\s*([}\]])", r"\1", block))


def parse_financial_json(text: str) -> tuple[dict | None, list[str]]:
    """Parse + validate model output. Never raises."""
    block = extract_json_block(text or "")
    if block is None:
        return None, ["No JSON object found in the response."]
    try:
        data = _loads_lenient(block)
    except json.JSONDecodeError as exc:
        return None, [f"Invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})."]
    if not isinstance(data, dict):
        return None, ["The JSON is not an object."]
    missing = [k for k in ("financial_summary", "financial_health_score", "risk_level") if k not in data]
    if missing:
        return None, [f"Missing required key(s): {', '.join(missing)}."]
    try:
        analysis = FinancialAnalysis.model_validate(data)
    except ValidationError as exc:
        return None, [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
    notes = [f"Key '{k}' was missing and left empty." for k in REQUIRED_KEYS if k not in data]
    return analysis.model_dump(), notes


# ── Fallback when the model can't produce valid JSON ────────────────────
def build_fallback_analysis(data: FinancialInput, metrics: FinancialMetrics) -> dict:
    """Rule-based analysis built only from Python numbers (clearly labelled in the UI)."""
    cur = data.currency
    top = sorted(data.expenses.items(), key=lambda kv: kv[1], reverse=True)[:3]
    spending = [{
        "category": EXPENSE_CATEGORIES[k],
        "observation": f"{format_money(v, cur)} per month, {metrics.category_shares.get(k, 0):.0f}% of expenses.",
        "recommendation": "Review this category for one realistic saving next month.",
    } for k, v in top if v > 0]
    priorities = []
    if metrics.remaining_income < 0:
        priorities.append("Bring expenses back below income.")
    if metrics.debt_ratio >= 20:
        priorities.append("Reduce the share of income going to debt repayments.")
    if metrics.savings_ratio < 10:
        priorities.append("Start or increase a small, automatic monthly saving.")
    priorities.append(f"Keep working toward your goal: {data.financial_goal.lower()}.")
    return {
        "financial_summary": (f"Python calculated a preliminary score of {metrics.preliminary_score}/100 "
                              f"({metrics.score_band.lower()}). This summary is rule-based because the AI "
                              "response could not be read."),
        "financial_health_score": metrics.preliminary_score,
        "spending_analysis": spending,
        "risk_level": metrics.rule_risk_level,
        "top_priorities": priorities[:3],
        "budget_recommendations": ["Track every expense for the next 30 days.",
                                   "Set a spending limit for your largest category."],
        "savings_strategy": ["Move savings to a separate account on payday."],
        "next_month_action_plan": ["Re-run FinWise AI next month and compare your score."],
    }


# ── CSV import (bonus) ──────────────────────────────────────────────────
_ALIASES = {
    "housing": ["housing", "rent", "mortgage", "home"],
    "food": ["food", "grocer", "dining", "restaurant", "meal"],
    "transportation": ["transport", "fuel", "gas station", "petrol", "car", "uber", "bus", "taxi"],
    "utilities": ["utilit", "electric", "water", "internet", "phone", "mobile"],
    "insurance": ["insurance", "premium"],
    "education": ["education", "school", "tuition", "course", "book"],
    "healthcare": ["health", "medical", "doctor", "pharma", "medicine", "hospital"],
    "entertainment": ["entertain", "movie", "stream", "netflix", "game", "hobby", "subscription"],
    "loan_debt": ["loan", "debt", "credit card", "repayment", "emi"],
}


def match_category(name: str) -> str:
    text = (name or "").strip().lower()
    if text in EXPENSE_CATEGORIES:
        return text
    for key, label in EXPENSE_CATEGORIES.items():
        if text == label.lower():
            return key
    for key, words in _ALIASES.items():
        if any(w in text for w in words):
            return key
    return "other"


def parse_expense_csv(raw: bytes) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Parse a CSV with columns `category, amount` and optional `month`.

    Returns ({month: {category_key: total}}, warnings). Without a month column
    everything goes under "Uploaded".
    """
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return {}, ["The CSV file is empty."]
    cols = {c.strip().lower(): c for c in reader.fieldnames if c}
    if "category" not in cols or "amount" not in cols:
        return {}, ["The CSV needs at least 'category' and 'amount' columns."]
    months: dict[str, dict[str, float]] = {}
    warnings, skipped = [], 0
    for row in reader:
        try:
            amount = float(str(row[cols["amount"]]).replace(",", "").strip() or 0)
        except ValueError:
            skipped += 1
            continue
        month = (row.get(cols["month"], "") if "month" in cols else "").strip() or "Uploaded"
        key = match_category(row[cols["category"]])
        bucket = months.setdefault(month, {k: 0.0 for k in EXPENSE_CATEGORIES})
        bucket[key] = round(bucket[key] + abs(amount), 2)
    if skipped:
        warnings.append(f"{skipped} row(s) with an unreadable amount were skipped.")
    return dict(sorted(months.items())), warnings


def risk_style(level: str) -> tuple[str, str]:
    """(emoji, streamlit alert kind) for a risk level."""
    return {"LOW": ("🟢", "success"), "MEDIUM": ("🟠", "warning"), "HIGH": ("🔴", "error")}.get(
        (level or "").upper(), ("⚪", "info"))


def md_safe(text: str) -> str:
    """Escape '$' so Streamlit Markdown doesn't render money amounts as LaTeX math."""
    return re.sub(r"(?<!\\)\$", r"\\$", str(text or ""))


def md_safe_stream(chunks):
    """Wrap a text stream so every chunk is safe for Streamlit Markdown."""
    for chunk in chunks:
        yield md_safe(chunk)

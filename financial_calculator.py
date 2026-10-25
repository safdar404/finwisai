"""Deterministic financial calculations — no AI involved.

The same inputs always produce the same outputs. These numbers are computed
*before* the LLM is called and are passed to it as facts, so the model explains
the numbers instead of inventing them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .config import CURRENCIES, EXPENSE_CATEGORIES, SCORE_BANDS

# Weights of the preliminary score (they add up to 100).
WEIGHT_SAVINGS = 30      # how much of income is saved
WEIGHT_LEFTOVER = 25     # money left after expenses
WEIGHT_EXPENSES = 25     # share of income spent
WEIGHT_DEBT = 20         # debt repayments as a share of income


@dataclass
class FinancialInput:
    monthly_income: float
    expenses: dict[str, float]
    savings: float
    financial_goal: str
    currency: str = "USD"
    goal_target: float = 0.0        # optional: amount needed for the goal
    goal_saved: float = 0.0         # optional: already saved toward the goal

    def __post_init__(self):
        # Negative numbers make no sense in this form; treat them as zero.
        self.monthly_income = max(0.0, float(self.monthly_income or 0))
        self.savings = max(0.0, float(self.savings or 0))
        self.goal_target = max(0.0, float(self.goal_target or 0))
        self.goal_saved = max(0.0, float(self.goal_saved or 0))
        self.expenses = {key: max(0.0, float(self.expenses.get(key, 0) or 0)) for key in EXPENSE_CATEGORIES}


@dataclass
class FinancialMetrics:
    monthly_income: float
    total_expenses: float
    remaining_income: float
    savings: float
    savings_ratio: float          # % of income saved
    expense_ratio: float          # % of income spent
    debt_ratio: float             # % of income going to debt repayments
    housing_ratio: float          # % of income going to housing
    category_shares: dict = field(default_factory=dict)   # key -> % of total expenses
    largest_category: str = ""
    preliminary_score: int = 0
    score_band: str = ""
    rule_risk_level: str = ""
    score_breakdown: dict = field(default_factory=dict)
    flags: list = field(default_factory=list)
    months_to_goal: float | None = None
    goal_progress: float | None = None   # % of goal already saved

    def to_dict(self) -> dict:
        return asdict(self)


# ── Small helpers ───────────────────────────────────────────────────────
def safe_percentage(part: float, whole: float) -> float:
    """part / whole * 100, returning 0.0 instead of dividing by zero."""
    if not whole:
        return 0.0
    return round(part / whole * 100, 2)


def _linear(value: float, best: float, worst: float) -> float:
    """Map value to 0..1 where `best` gives 1 and `worst` gives 0 (clamped)."""
    if best == worst:
        return 1.0
    fraction = (value - worst) / (best - worst)
    return max(0.0, min(1.0, fraction))


def score_band(score: float) -> str:
    for minimum, label, _ in SCORE_BANDS:
        if score >= minimum:
            return label
    return SCORE_BANDS[-1][1]


def format_money(amount: float, currency: str = "USD") -> str:
    symbol = CURRENCIES.get(currency, ("", ""))[0]
    sign = "-" if amount < 0 else ""
    decimals = 0 if currency == "JPY" else 2
    return f"{sign}{symbol}{abs(amount):,.{decimals}f}"


# ── Core calculations ───────────────────────────────────────────────────
def calculate_total_expenses(expenses: dict[str, float]) -> float:
    return round(sum(expenses.values()), 2)


def calculate_preliminary_score(savings_ratio: float, remaining_ratio: float,
                                expense_ratio: float, debt_ratio: float) -> tuple[int, dict]:
    """Weighted 0-100 heuristic. Returns (score, points per component)."""
    parts = {
        # 20% of income saved or more earns full marks.
        "savings": WEIGHT_SAVINGS * _linear(savings_ratio, best=20, worst=0),
        # 20% of income left after expenses or more earns full marks; 0 or less earns none.
        "leftover": WEIGHT_LEFTOVER * _linear(remaining_ratio, best=20, worst=0),
        # Spending 50% of income or less is full marks; 100% or more is zero.
        "expenses": WEIGHT_EXPENSES * _linear(expense_ratio, best=50, worst=100),
        # Debt repayments up to 10% of income are full marks; 40% or more is zero.
        "debt": WEIGHT_DEBT * _linear(debt_ratio, best=10, worst=40),
    }
    parts = {k: round(v, 1) for k, v in parts.items()}
    return int(round(sum(parts.values()))), parts


def rule_based_risk(score: int, remaining_income: float, debt_ratio: float, income: float) -> str:
    if income <= 0 or remaining_income < 0 or debt_ratio >= 40:
        return "HIGH"
    if score >= 70:
        return "LOW"
    if score >= 45:
        return "MEDIUM"
    return "HIGH"


def analyse(data: FinancialInput) -> FinancialMetrics:
    """Run every deterministic calculation for one month of data."""
    income = data.monthly_income
    total = calculate_total_expenses(data.expenses)
    remaining = round(income - total, 2)

    savings_ratio = safe_percentage(data.savings, income)
    expense_ratio = safe_percentage(total, income)
    remaining_ratio = safe_percentage(remaining, income)
    debt_ratio = safe_percentage(data.expenses["loan_debt"], income)
    housing_ratio = safe_percentage(data.expenses["housing"], income)

    shares = {k: safe_percentage(v, total) for k, v in data.expenses.items()}
    largest = max(data.expenses, key=data.expenses.get) if total > 0 else ""

    if income > 0:
        score, breakdown = calculate_preliminary_score(savings_ratio, remaining_ratio, expense_ratio, debt_ratio)
    else:
        score, breakdown = 0, {"savings": 0, "leftover": 0, "expenses": 0, "debt": 0}
    risk = rule_based_risk(score, remaining, debt_ratio, income)

    flags = []
    if income <= 0:
        flags.append("No income was entered, so ratios could not be calculated.")
    if remaining < 0:
        flags.append("Expenses are higher than income this month.")
    elif income > 0 and remaining == 0:
        flags.append("Income and expenses are exactly equal — nothing is left over.")
    if debt_ratio >= 36:
        flags.append(f"Debt repayments take {debt_ratio:.0f}% of income, which is a heavy burden.")
    if housing_ratio >= 40:
        flags.append(f"Housing takes {housing_ratio:.0f}% of income; many guides suggest about 30%.")
    if income > 0 and data.savings > max(remaining, 0):
        flags.append("Savings are larger than what is left after expenses — check whether savings come from reserves.")
    if income > 0 and data.savings == 0:
        flags.append("No monthly savings recorded.")

    months_to_goal = goal_progress = None
    if data.goal_target > 0:
        goal_progress = min(100.0, safe_percentage(data.goal_saved, data.goal_target))
        still_needed = max(0.0, data.goal_target - data.goal_saved)
        if still_needed == 0:
            months_to_goal = 0.0
        elif data.savings > 0:
            months_to_goal = round(still_needed / data.savings, 1)

    return FinancialMetrics(
        monthly_income=income, total_expenses=total, remaining_income=remaining, savings=data.savings,
        savings_ratio=savings_ratio, expense_ratio=expense_ratio, debt_ratio=debt_ratio,
        housing_ratio=housing_ratio, category_shares=shares, largest_category=largest,
        preliminary_score=score, score_band=score_band(score), rule_risk_level=risk,
        score_breakdown=breakdown, flags=flags, months_to_goal=months_to_goal, goal_progress=goal_progress,
    )


def expense_breakdown_text(data: FinancialInput) -> str:
    """Human-readable list used inside the prompts."""
    lines = []
    for key, label in EXPENSE_CATEGORIES.items():
        amount = data.expenses[key]
        lines.append(f"- {label}: {format_money(amount, data.currency)} "
                     f"({safe_percentage(amount, data.monthly_income):.1f}% of income)")
    return "\n".join(lines)


def build_prompt_inputs(data: FinancialInput, metrics: FinancialMetrics) -> dict:
    """Variables inserted dynamically into the LangChain prompt templates."""
    cur = data.currency
    return {
        "monthly_income": format_money(metrics.monthly_income, cur),
        "total_expenses": format_money(metrics.total_expenses, cur),
        "remaining_income": format_money(metrics.remaining_income, cur),
        "savings": format_money(metrics.savings, cur),
        "savings_ratio": f"{metrics.savings_ratio:.1f}%",
        "expense_ratio": f"{metrics.expense_ratio:.1f}%",
        "financial_goal": data.financial_goal,
        "expense_breakdown": expense_breakdown_text(data),
        "debt_ratio": f"{metrics.debt_ratio:.1f}%",
        "preliminary_score": str(metrics.preliminary_score),
        "rule_risk_level": metrics.rule_risk_level,
        "currency": f"{cur} ({CURRENCIES.get(cur, ('', cur))[1]})",
        "warning_flags": "\n".join(f"- {f}" for f in metrics.flags) or "- None",
    }

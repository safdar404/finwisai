"""Application settings and form options.

Everything that might change between deployments (model names, cache path,
form choices) lives here so the rest of the code never hard-codes it.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a local .env file (never commit the real one).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

APP_NAME = "FinWise AI"
APP_TAGLINE = "Personal financial analysis and smart budget assistant"
APP_VERSION = "1.0.0"


def get_openai_api_key() -> str:
    """Return the API key from the environment (.env) or an empty string."""
    return os.getenv("OPENAI_API_KEY", "").strip()


# ── Model settings ──────────────────────────────────────────────────────
DEFAULT_MODEL = os.getenv("FINWISE_MODEL", "gpt-4o-mini")
AVAILABLE_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"]
if DEFAULT_MODEL not in AVAILABLE_MODELS:
    AVAILABLE_MODELS.insert(0, DEFAULT_MODEL)
DEFAULT_TEMPERATURE = 0.2
REQUEST_TIMEOUT_SECONDS = 60

# ── Caching ─────────────────────────────────────────────────────────────
CACHE_NONE = "No cache"
CACHE_MEMORY = "In-memory cache"
CACHE_SQLITE = "SQLite cache"
CACHE_OPTIONS = [CACHE_MEMORY, CACHE_SQLITE, CACHE_NONE]
SQLITE_CACHE_PATH = Path(os.getenv("FINWISE_CACHE_PATH", PROJECT_ROOT / ".langchain_cache.db"))

# ── Form options ────────────────────────────────────────────────────────
# Ten expense categories: key -> label shown in the form.
EXPENSE_CATEGORIES: dict[str, str] = {
    "housing": "Housing / rent",
    "food": "Food & groceries",
    "transportation": "Transportation",
    "utilities": "Utilities",
    "insurance": "Insurance",
    "education": "Education",
    "healthcare": "Healthcare",
    "entertainment": "Entertainment",
    "loan_debt": "Loan / debt payments",
    "other": "Other",
}

EXPENSE_HELP: dict[str, str] = {
    "housing": "Rent or mortgage, property fees.",
    "food": "Groceries, dining out, delivery.",
    "transportation": "Fuel, public transport, car payments, ride-hailing.",
    "utilities": "Electricity, water, gas, internet, phone.",
    "insurance": "Health, life, car or home insurance premiums.",
    "education": "Tuition, courses, books, school fees.",
    "healthcare": "Doctor visits, medicine, out-of-pocket costs.",
    "entertainment": "Streaming, outings, hobbies, subscriptions.",
    "loan_debt": "Credit card, personal loan, student loan repayments.",
    "other": "Anything that doesn't fit above.",
}

FINANCIAL_GOALS = [
    "Save money",
    "Build an emergency fund",
    "Pay off debt",
    "Plan a vacation",
    "Start a business",
    "Improve budgeting",
]

# code -> (symbol, name)
CURRENCIES: dict[str, tuple[str, str]] = {
    "USD": ("$", "US dollar"),
    "EUR": ("€", "Euro"),
    "GBP": ("£", "British pound"),
    "PKR": ("Rs ", "Pakistani rupee"),
    "INR": ("₹", "Indian rupee"),
    "AED": ("AED ", "UAE dirham"),
    "SAR": ("SAR ", "Saudi riyal"),
    "CAD": ("C$", "Canadian dollar"),
    "AUD": ("A$", "Australian dollar"),
    "JPY": ("¥", "Japanese yen"),
}

# ── Scoring bands (educational only) ────────────────────────────────────
# (minimum score, label, short meaning)
SCORE_BANDS = [
    (80, "Strong", "Spending is well under control with room to grow savings."),
    (60, "Generally healthy", "A solid base with a few areas to tighten."),
    (40, "Needs improvement", "Some spending patterns deserve attention."),
    (0, "High attention", "Spending pressure is high; small changes can help."),
]
RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]

DISCLAIMER = (
    "FinWise AI is an educational prototype. Its numbers and suggestions are for "
    "informational purposes only and are not financial, investment, tax or legal advice. "
    "No outcome is guaranteed. Please consult a qualified financial professional before "
    "making money decisions."
)

# ── The five testing scenarios from the assignment (section 16) ─────────
# Used by the "Quick fill" panel so each scenario can be demonstrated in one click.
_ZERO = {k: 0.0 for k in EXPENSE_CATEGORIES}
TEST_SCENARIOS: dict[str, dict] = {
    "1 · High income, low spending": {
        "income": 8000, "savings": 1500, "expenses": {**_ZERO, "housing": 900, "food": 400, "transportation": 200,
        "utilities": 150, "insurance": 100, "healthcare": 50, "entertainment": 150, "other": 50}},
    "2 · Spending above income": {
        "income": 2000, "savings": 0, "expenses": {**_ZERO, "housing": 1100, "food": 500, "transportation": 250,
        "utilities": 180, "insurance": 80, "healthcare": 90, "entertainment": 200, "loan_debt": 150, "other": 50}},
    "3 · Heavy debt repayments": {
        "income": 5000, "savings": 200, "expenses": {**_ZERO, "housing": 900, "food": 350, "transportation": 150,
        "utilities": 100, "loan_debt": 2500}},
    "4 · Strong saver": {
        "income": 4000, "savings": 1200, "expenses": {**_ZERO, "housing": 1000, "food": 400, "transportation": 200,
        "utilities": 150, "insurance": 100, "healthcare": 50, "entertainment": 150, "other": 50}},
    "5 · Break-even month": {
        "income": 3000, "savings": 0, "expenses": {**_ZERO, "housing": 1200, "food": 600, "transportation": 300,
        "utilities": 200, "insurance": 150, "education": 100, "healthcare": 100, "entertainment": 200,
        "loan_debt": 100, "other": 50}},
}

# Starting values shown the first time the app opens.
DEFAULT_FORM = {"income": 5000, "savings": 500, "expenses": {**_ZERO, "housing": 1500, "food": 600,
                "transportation": 300, "utilities": 200, "insurance": 150, "education": 100, "healthcare": 100,
                "entertainment": 250, "loan_debt": 400, "other": 150}}

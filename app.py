"""FinWise AI — Smart Budget Assistant (v2.0)

Educational prototype. Python computes every number; an optional OpenAI model
(via LangChain) writes insights and powers the chat. Without an API key, a
built-in rule-based agent takes over so the app is always useful.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import re
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional
    pass

APP_VERSION = "2.0.0"
ROOT = Path(__file__).parent
LOGO_PATH = ROOT / "assets" / "logo.svg"

st.set_page_config(
    page_title="FinWise AI — Smart Budget Assistant",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────
RAINBOW = ["#FF4D8D", "#FF7A45", "#FFB443", "#FFD93D", "#9BE15D",
           "#3DDC97", "#3DE8FF", "#4D96FF", "#8B6CFF", "#D35CFF"]

# key, label, emoji, bucket for the 50/30/20 rule
CATEGORIES = [
    ("housing", "Housing / rent", "🏠", "needs"),
    ("food", "Food & groceries", "🛒", "needs"),
    ("transport", "Transportation", "🚗", "needs"),
    ("utilities", "Utilities", "💡", "needs"),
    ("insurance", "Insurance", "🛡️", "needs"),
    ("healthcare", "Healthcare", "🩺", "needs"),
    ("debt", "Loan / debt payments", "💳", "needs"),
    ("education", "Education", "🎓", "wants"),
    ("entertainment", "Entertainment", "🎬", "wants"),
    ("other", "Other", "📦", "wants"),
]
CAT_KEYS = [c[0] for c in CATEGORIES]
CAT_LABEL = {c[0]: c[1] for c in CATEGORIES}
CAT_EMOJI = {c[0]: c[2] for c in CATEGORIES}
CAT_BUCKET = {c[0]: c[3] for c in CATEGORIES}
CAT_COLOR = {k: RAINBOW[i] for i, k in enumerate(CAT_KEYS)}

# keywords used to map imported CSV categories to the form categories
CSV_KEYWORDS = {
    "housing": ["rent", "housing", "mortgage", "home", "house", "apartment"],
    "food": ["food", "grocer", "restaurant", "dining", "meal", "coffee", "takeaway"],
    "transport": ["transport", "car", "fuel", "gas", "petrol", "uber", "taxi", "bus", "train", "metro"],
    "utilities": ["utilit", "electric", "water", "internet", "phone", "mobile", "bill"],
    "insurance": ["insur"],
    "healthcare": ["health", "medical", "doctor", "pharma", "medicine", "dental", "gym"],
    "debt": ["loan", "debt", "credit", "emi", "installment", "card"],
    "education": ["educat", "school", "tuition", "course", "book", "college", "university"],
    "entertainment": ["entertain", "movie", "netflix", "spotify", "game", "subscription", "fun", "travel", "shopping"],
}

CURRENCIES = {
    "USD": "$", "EUR": "€", "GBP": "£", "PKR": "Rs ", "INR": "₹",
    "AED": "AED ", "SAR": "SAR ", "CAD": "C$", "AUD": "A$",
}

GOALS = {
    "🛟 Build an emergency fund": "emergency fund",
    "💳 Pay off debt": "debt payoff",
    "🏡 Save for a home": "home down payment",
    "✈️ Plan a trip": "travel",
    "🎓 Fund education": "education",
    "📈 Start investing": "investing",
    "🌴 Retire comfortably": "retirement",
}

PRESETS = {
    "🧪 Assignment test": dict(income=8000, savings=1500, saved=3000, goal_amt=10000,
                               goal="🛟 Build an emergency fund",
                               exp=dict(housing=900, food=400, transport=200, utilities=150, insurance=100,
                                        healthcare=50, debt=0, education=0, entertainment=150, other=50)),
    "🎓 Student": dict(income=1200, savings=60, saved=200, goal_amt=1500, goal="🎓 Fund education",
                       exp=dict(housing=450, food=250, transport=80, utilities=60, insurance=0,
                                healthcare=20, debt=50, education=120, entertainment=90, other=40)),
    "👨‍👩‍👧 Family of four": dict(income=6500, savings=400, saved=2500, goal_amt=20000,
                                  goal="🏡 Save for a home",
                                  exp=dict(housing=2100, food=1100, transport=550, utilities=320, insurance=380,
                                           healthcare=250, debt=600, education=300, entertainment=250, other=200)),
    "💼 Young professional": dict(income=4200, savings=350, saved=900, goal_amt=8000,
                                  goal="💳 Pay off debt",
                                  exp=dict(housing=1400, food=520, transport=300, utilities=160, insurance=120,
                                           healthcare=60, debt=450, education=0, entertainment=380, other=180)),
}

DISCLAIMER = ("FinWise AI is an educational prototype. Numbers and suggestions are informational only — "
              "not financial, investment, tax or legal advice. No outcome is guaranteed. Consult a qualified "
              "professional before making money decisions.")


# ──────────────────────────────────────────────────────────────────────────────
# Styling
# ──────────────────────────────────────────────────────────────────────────────
def logo_data_uri() -> str:
    if not LOGO_PATH.exists():
        return ""
    return "data:image/svg+xml;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode()


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&display=swap');
:root{
  --rb: linear-gradient(90deg,#FF4D8D,#FF9F43,#FFD93D,#3DDC97,#3DE8FF,#4D96FF,#B65CFF,#FF4D8D);
  --glass: rgba(26,23,52,.62);
  --line: rgba(255,255,255,.08);
  --muted: #A9A4CF;
}
html, body, [class*="css"], .stMarkdown, p, label, input, button { font-family: 'Inter', sans-serif; }
h1,h2,h3,h4,.fw-title { font-family:'Space Grotesk',system-ui,sans-serif,sans-serif !important; letter-spacing:-.01em; }

/* aurora background */
.stApp{
  background:
    radial-gradient(900px 500px at 8% -10%, rgba(255,77,141,.18), transparent 60%),
    radial-gradient(800px 500px at 100% 0%, rgba(77,150,255,.18), transparent 60%),
    radial-gradient(700px 600px at 50% 110%, rgba(61,220,151,.12), transparent 60%),
    #0B0A1A;
}
.stApp:before{ content:""; position:fixed; top:0; left:0; right:0; height:3px; z-index:1000;
  background:var(--rb); background-size:200% 100%; animation:rbshift 6s linear infinite; }
@keyframes rbshift{ to{ background-position:200% 0; } }

/* compact layout */
.block-container{ padding-top:2.2rem !important; padding-bottom:2rem !important; max-width:1180px; }
[data-testid="stVerticalBlock"]{ gap:.65rem; }
[data-testid="stSidebar"]{ background:linear-gradient(180deg,#14112B 0%,#0E0C20 100%); border-right:1px solid var(--line); }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{ gap:.5rem; }

/* hero */
.fw-hero{ display:flex; align-items:center; gap:16px; padding:16px 20px; border-radius:20px;
  background:var(--glass); border:1px solid var(--line); backdrop-filter:blur(10px); position:relative; overflow:hidden; }
.fw-hero:after{ content:""; position:absolute; inset:0; border-radius:20px; padding:1.5px;
  background:var(--rb); background-size:200% 100%; animation:rbshift 8s linear infinite;
  -webkit-mask:linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite:xor; mask-composite:exclude; pointer-events:none; }
.fw-hero img{ width:62px; height:62px; filter:drop-shadow(0 0 14px rgba(182,92,255,.55)); animation:float 4s ease-in-out infinite; }
@keyframes float{ 50%{ transform:translateY(-4px); } }
.fw-title{ font-size:2rem; font-weight:700; line-height:1.05; margin:0;
  background:var(--rb); background-size:200% 100%; -webkit-background-clip:text; background-clip:text; color:transparent;
  animation:rbshift 8s linear infinite; }
.fw-sub{ color:var(--muted); font-size:.92rem; margin-top:4px; }
.fw-pill{ display:inline-flex; align-items:center; gap:6px; font-size:.72rem; font-weight:600; padding:3px 10px;
  border-radius:999px; background:rgba(61,220,151,.12); color:#3DDC97; border:1px solid rgba(61,220,151,.35); margin-left:8px; vertical-align:middle;}
.fw-pill.off{ background:rgba(255,180,67,.12); color:#FFB443; border-color:rgba(255,180,67,.35); }
.fw-dot{ width:7px; height:7px; border-radius:50%; background:currentColor; box-shadow:0 0 8px currentColor; animation:pulse 1.6s infinite; }
@keyframes pulse{ 50%{ opacity:.35; } }
.fw-note{ font-size:.78rem; color:var(--muted); padding:6px 12px; border-radius:10px; background:rgba(255,255,255,.03); border:1px dashed var(--line); }

/* KPI cards */
.kpi-grid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }
.kpi{ position:relative; padding:12px 14px; border-radius:16px; background:var(--glass); border:1px solid var(--line); overflow:hidden; transition:transform .15s; }
.kpi:hover{ transform:translateY(-2px); }
.kpi:before{ content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--c); box-shadow:0 0 14px var(--c); }
.kpi .l{ font-size:.75rem; color:var(--muted); font-weight:500; white-space:nowrap; }
.kpi .v{ font-family:'Space Grotesk',system-ui,sans-serif; font-size:1.35rem; font-weight:700; margin-top:2px; white-space:nowrap; }
.kpi .d{ font-size:.72rem; color:var(--muted); margin-top:2px; }

/* insight cards */
.ins{ padding:11px 14px; border-radius:14px; background:var(--glass); border:1px solid var(--line); border-left:4px solid var(--c); margin-bottom:8px; }
.ins b{ font-family:'Space Grotesk',system-ui,sans-serif; }
.ins p{ margin:3px 0 0 0; color:#D6D2F5; font-size:.88rem; }

.badge{ display:inline-block; padding:5px 11px; margin:3px 4px 3px 0; border-radius:999px; font-size:.8rem; font-weight:600;
  background:rgba(255,255,255,.05); border:1px solid var(--line); }
.badge.on{ background:linear-gradient(90deg,rgba(255,77,141,.18),rgba(77,150,255,.18)); border-color:rgba(182,92,255,.5); }
.badge.off{ opacity:.4; filter:grayscale(1); }

.bar-wrap{ height:10px; border-radius:99px; background:rgba(255,255,255,.07); overflow:hidden; }
.bar-fill{ height:100%; border-radius:99px; background:var(--rb); background-size:200% 100%; animation:rbshift 5s linear infinite; }

/* widgets */
.stButton>button, .stDownloadButton>button, [data-testid="stFormSubmitButton"]>button{
  border-radius:12px; font-weight:600; border:1px solid var(--line); transition:all .15s; }
.stButton>button[kind="primary"]{ background:linear-gradient(90deg,#FF4D8D,#B65CFF 50%,#4D96FF); border:0; color:white;
  box-shadow:0 6px 22px rgba(182,92,255,.35); }
.stButton>button[kind="primary"]:hover{ filter:brightness(1.12); transform:translateY(-1px); }
.stButton>button:hover, .stDownloadButton>button:hover{ border-color:#B65CFF; }
[data-baseweb="tab-list"]{ gap:4px; flex-wrap:wrap; }
[data-baseweb="tab"]{ border-radius:10px !important; padding:6px 12px !important; background:rgba(255,255,255,.03); }
[data-baseweb="tab"][aria-selected="true"]{ background:linear-gradient(90deg,rgba(255,77,141,.22),rgba(182,92,255,.22),rgba(77,150,255,.22)); }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"]{ display:none; }
[data-testid="stExpander"] details, [data-testid="stForm"]{ border-radius:16px !important; border:1px solid var(--line) !important; background:var(--glass); }
[data-testid="stNumberInput"] input{ font-family:'Space Grotesk',system-ui,sans-serif; }
[data-testid="stChatMessage"]{ background:var(--glass); border:1px solid var(--line); border-radius:14px; }
footer{ visibility:hidden; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────────────────────────
def init_state() -> None:
    defaults = dict(income=0.0, savings=0.0, saved=0.0, goal_amt=0.0, goal=list(GOALS)[0],
                    analysed=False, chat=[], currency="USD", rate=5.0, years=10,
                    target_months=24, ai_text=None)
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    for k in CAT_KEYS:
        st.session_state.setdefault(f"exp_{k}", 0.0)
        st.session_state.setdefault(f"cut_{k}", 0)


init_state()


def load_preset(name: str) -> None:
    p = PRESETS[name]
    st.session_state.update(income=float(p["income"]), savings=float(p["savings"]), saved=float(p["saved"]),
                            goal_amt=float(p["goal_amt"]), goal=p["goal"], analysed=True, ai_text=None)
    for k in CAT_KEYS:
        st.session_state[f"exp_{k}"] = float(p["exp"].get(k, 0))
        st.session_state[f"cut_{k}"] = 0
    st.toast(f"{name} loaded", icon="✨")


def reset_all() -> None:
    keep = {k: st.session_state.get(k) for k in ("api_key", "model", "temperature", "currency")}
    st.session_state.clear()
    st.session_state.update({k: v for k, v in keep.items() if v is not None})


def match_category(name: str) -> str:
    n = str(name).lower().strip()
    for k in CAT_KEYS:
        if n == k or n == CAT_LABEL[k].lower():
            return k
    for k, words in CSV_KEYWORDS.items():
        if any(w in n for w in words):
            return k
    return "other"


def import_csv() -> None:
    f = st.session_state.get("csv_file")
    if f is None:
        return
    try:
        df = pd.read_csv(f)
        df.columns = [c.strip().lower() for c in df.columns]
        if not {"category", "amount"} <= set(df.columns):
            st.session_state["csv_msg"] = ("error", "CSV needs `category` and `amount` columns.")
            return
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0).abs()
        df["key"] = df["category"].map(match_category)
        months = df["month"].nunique() if "month" in df.columns else 1
        totals = df.groupby("key")["amount"].sum() / max(months, 1)
        for k in CAT_KEYS:
            st.session_state[f"exp_{k}"] = round(float(totals.get(k, 0.0)), 2)
        st.session_state["analysed"] = True
        st.session_state["csv_msg"] = ("success",
                                       f"Imported {len(df)} rows across {months} month(s) — averaged per month ✅")
    except Exception as e:  # noqa: BLE001
        st.session_state["csv_msg"] = ("error", f"Couldn't read that CSV: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Core calculations (pure Python — deterministic)
# ──────────────────────────────────────────────────────────────────────────────
def compute(income: float, savings: float, saved: float, exp: dict[str, float],
            goal_amt: float) -> dict:
    total = sum(exp.values())
    remaining = income - total
    unassigned = remaining - savings
    pct = (lambda x: (x / income * 100) if income > 0 else 0.0)
    needs = sum(v for k, v in exp.items() if CAT_BUCKET[k] == "needs")
    wants = total - needs
    ef_months = (saved / total) if total > 0 else 0.0
    goal_left = max(goal_amt - saved, 0.0)
    months_to_goal = math.ceil(goal_left / savings) if savings > 0 and goal_left > 0 else (0 if goal_left == 0 else None)

    # Preliminary score (transparent, rule-based, 0–100)
    breakdown = []
    s = 100
    sr, er, dr = pct(savings), pct(total), pct(exp.get("debt", 0))
    if sr < 10:
        breakdown.append(("Savings ratio below 10%", -25)); s -= 25
    elif sr < 20:
        breakdown.append(("Savings ratio below 20%", -10)); s -= 10
    if er > 90:
        breakdown.append(("Expenses above 90% of income", -30)); s -= 30
    elif er > 70:
        breakdown.append(("Expenses above 70% of income", -15)); s -= 15
    if dr > 36:
        breakdown.append(("Debt payments above 36% of income", -20)); s -= 20
    elif dr > 15:
        breakdown.append(("Debt payments above 15% of income", -8)); s -= 8
    if ef_months < 1:
        breakdown.append(("Emergency fund under 1 month", -10)); s -= 10
    elif ef_months < 3:
        breakdown.append(("Emergency fund under 3 months", -5)); s -= 5
    if remaining < 0:
        breakdown.append(("Spending more than you earn", -20)); s -= 20
    s = max(0, min(100, s))
    label = "Excellent 🌟" if s >= 85 else "Good 👍" if s >= 70 else "Fair ⚠️" if s >= 50 else "Needs care 🚨"

    return dict(income=income, savings=savings, saved=saved, exp=exp, total=total, remaining=remaining,
                unassigned=unassigned, savings_ratio=sr, expense_ratio=er, debt_ratio=dr,
                needs=needs, wants=wants, needs_pct=pct(needs), wants_pct=pct(wants),
                ef_months=ef_months, goal_amt=goal_amt, goal_left=goal_left, months_to_goal=months_to_goal,
                score=s, score_label=label, breakdown=breakdown)


def project_growth(monthly: float, start: float, rate_pct: float, years: int) -> pd.DataFrame:
    r = rate_pct / 100 / 12
    bal, contrib, rows = start, start, []
    for m in range(0, years * 12 + 1):
        if m:
            bal = bal * (1 + r) + monthly
            contrib += monthly
        if m % 12 == 0:
            rows.append(dict(year=m // 12, balance=bal, contributed=contrib))
    return pd.DataFrame(rows)


def badges(r: dict) -> list[tuple[str, str, bool]]:
    return [
        ("🌱", "Saver — 10%+ saved", r["savings_ratio"] >= 10),
        ("🚀", "Super saver — 20%+", r["savings_ratio"] >= 20),
        ("🛟", "3-month safety net", r["ef_months"] >= 3),
        ("🧘", "Living below means", r["expense_ratio"] <= 70),
        ("⛓️‍💥", "Low debt load", r["debt_ratio"] <= 15),
        ("⚖️", "50/30/20 balanced", r["needs_pct"] <= 50 and r["wants_pct"] <= 30),
        ("🎯", "Goal reached", r["goal_amt"] > 0 and r["goal_left"] == 0),
    ]


def rule_insights(r: dict, fmt) -> list[tuple[str, str, str, str]]:
    """Offline agent: (emoji, title, text, colour)."""
    out = []
    if r["income"] <= 0:
        return [("👋", "Add your income", "Enter a monthly income to unlock insights.", "#FFB443")]
    if r["remaining"] < 0:
        out.append(("🚨", "You're overspending",
                    f"Expenses exceed income by {fmt(-r['remaining'])}/month. Start with the largest flexible "
                    "category and trim it this week.", "#FF4D8D"))
    if r["unassigned"] > 0.05 * r["income"]:
        out.append(("💡", "Give every dollar a job",
                    f"{fmt(r['unassigned'])}/month isn't assigned to spending or savings. Automating even half of it "
                    f"into savings would add {fmt(r['unassigned'] * 6)} a year.", "#FFD93D"))
    if r["savings_ratio"] < 20:
        gap = 0.2 * r["income"] - r["savings"]
        out.append(("🐷", "Lift your savings rate",
                    f"You're saving {r['savings_ratio']:.1f}% of income. Reaching 20% means {fmt(gap)} more per month.",
                    "#FF9F43"))
    else:
        out.append(("🚀", "Strong savings habit",
                    f"Saving {r['savings_ratio']:.1f}% of income beats the common 20% benchmark. Keep it automated.",
                    "#3DDC97"))
    if r["ef_months"] < 3 and r["total"] > 0:
        out.append(("🛟", "Grow your safety net",
                    f"Your saved balance covers {r['ef_months']:.1f} months of expenses. Aim for 3–6 months "
                    f"({fmt(r['total'] * 3)}–{fmt(r['total'] * 6)}).", "#3DE8FF"))
    if r["debt_ratio"] > 15:
        out.append(("💳", "Debt is heavy",
                    f"Debt payments take {r['debt_ratio']:.1f}% of income. Consider paying the highest-interest balance "
                    "first (avalanche method).", "#FF4D8D"))
    if r["wants_pct"] > 30:
        out.append(("🎬", "Wants above 30%",
                    f"Flexible spending is {r['wants_pct']:.1f}% of income — trimming it to 30% frees "
                    f"{fmt(r['wants'] - 0.3 * r['income'])}/month.", "#D35CFF"))
    if r["total"] > 0:
        top = max(r["exp"], key=r["exp"].get)
        share = r["exp"][top] / r["total"] * 100
        out.append((CAT_EMOJI[top], f"Biggest category: {CAT_LABEL[top]}",
                    f"{fmt(r['exp'][top])} ({share:.0f}% of spending). A 10% cut here saves "
                    f"{fmt(r['exp'][top] * 1.2)} a year.", "#4D96FF"))
    if r["months_to_goal"]:
        out.append(("🎯", "Goal timeline",
                    f"At {fmt(r['savings'])}/month you'll reach your goal in about {r['months_to_goal']} months.",
                    "#9BE15D"))
    return out


def rule_chat(q: str, r: dict, fmt) -> str:
    q = q.lower()
    if any(w in q for w in ["save", "saving"]):
        return (f"🐷 You save **{fmt(r['savings'])}/month ({r['savings_ratio']:.1f}%)**. "
                f"Hitting 20% would mean **{fmt(max(0.2 * r['income'] - r['savings'], 0))}** more. "
                f"You also have **{fmt(max(r['unassigned'], 0))}** unassigned each month — automate a transfer on payday.")
    if any(w in q for w in ["debt", "loan", "credit"]):
        return (f"💳 Debt payments are **{r['debt_ratio']:.1f}%** of income. Under 15% is comfortable; above 36% is a "
                "warning sign. List debts by interest rate and send extra money to the highest one first.")
    if any(w in q for w in ["emergency", "safety"]):
        return (f"🛟 Your saved balance covers **{r['ef_months']:.1f} months**. A 3–6 month target is "
                f"**{fmt(r['total'] * 3)}–{fmt(r['total'] * 6)}**.")
    if any(w in q for w in ["goal", "target"]):
        if r["months_to_goal"]:
            return f"🎯 About **{r['months_to_goal']} months** to go, with {fmt(r['goal_left'])} left."
        return "🎯 Set a goal amount and a monthly savings figure, and I'll estimate the timeline."
    if any(w in q for w in ["cut", "reduce", "spend", "expense"]):
        top = sorted(r["exp"].items(), key=lambda x: -x[1])[:3]
        lst = ", ".join(f"{CAT_EMOJI[k]} {CAT_LABEL[k]} ({fmt(v)})" for k, v in top if v > 0)
        return f"✂️ Your top categories are {lst}. Try the **🔮 What-if** tab to see the effect of trimming them."
    if any(w in q for w in ["invest", "stock", "crypto"]):
        return ("📈 I can't give investment advice. Generally people build an emergency fund and clear high-interest "
                "debt before investing — a licensed adviser can help with specifics.")
    if any(w in q for w in ["score", "health"]):
        return f"🩺 Your score is **{r['score']}/100 ({r['score_label']})**. See *How the score works* in the Overview tab."
    return ("🤖 I'm running in offline mode. Ask me about **saving**, **debt**, **emergency fund**, **goals**, "
            "**cutting expenses** or your **score** — or add an OpenAI key for free-form answers.")


# ──────────────────────────────────────────────────────────────────────────────
# LLM (optional)
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM = ("You are FinWise AI, a friendly budgeting coach. Use ONLY the numbers given. Be concise, practical, "
          "upbeat and use a few relevant emojis. Never give investment, tax or legal advice; suggest a qualified "
          "professional for those. Format with short markdown bullets.")


def configured_api_key() -> str:
    key = st.session_state.get("api_key") or os.getenv("OPENAI_API_KEY", "")
    if not key:
        try:
            key = st.secrets.get("OPENAI_API_KEY", "")
        except (FileNotFoundError, KeyError):
            pass
    return str(key).strip()


def get_llm(stream: bool = True):
    key = configured_api_key()
    if not key:
        return None
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None
    return ChatOpenAI(model=st.session_state.get("model", "gpt-4o-mini"), api_key=key,
                      temperature=st.session_state.get("temperature", 0.2), streaming=stream, timeout=60, max_retries=2)


def summary_for_llm(r: dict, cur: str) -> str:
    d = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()
         if k not in ("breakdown", "exp")}
    d["expenses"] = {CAT_LABEL[k]: v for k, v in r["exp"].items()}
    d["currency"] = cur
    d["goal_type"] = GOALS[st.session_state["goal"]]
    return json.dumps(d, default=str)


def stream_text(llm, messages):
    for chunk in llm.stream(messages):
        yield (chunk.content or "").replace("$", "\\$")  # avoid accidental LaTeX


# ──────────────────────────────────────────────────────────────────────────────
# Charts
# ──────────────────────────────────────────────────────────────────────────────
PLOT_LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                   font=dict(color="#EEEBFF", family="Inter"), margin=dict(l=8, r=8, t=36, b=8))


def bar_chart(exp: dict, sym: str) -> go.Figure:
    items = sorted([(k, v) for k, v in exp.items() if v > 0], key=lambda x: x[1])
    fig = go.Figure(go.Bar(
        x=[v for _, v in items], y=[f"{CAT_EMOJI[k]} {CAT_LABEL[k]}" for k, _ in items], orientation="h",
        marker=dict(color=[CAT_COLOR[k] for k, _ in items], line=dict(width=0)),
        text=[f"{sym}{v:,.0f}" for _, v in items], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: " + sym + "%{x:,.2f}<extra></extra>"))
    fig.update_layout(**PLOT_LAYOUT, title=dict(text="💸 Where the money goes", font=dict(size=15)),
                      height=max(240, 34 * len(items) + 70), bargap=.35,
                      xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.06)", zeroline=False, showticklabels=False,
                                 range=[0, max([v for _, v in items] + [1]) * 1.22]),
                      yaxis=dict(showgrid=False))
    return fig


def donut_chart(exp: dict, total: float, sym: str) -> go.Figure:
    items = [(k, v) for k, v in exp.items() if v > 0]
    fig = go.Figure(go.Pie(
        labels=[f"{CAT_EMOJI[k]} {CAT_LABEL[k]}" for k, _ in items], values=[v for _, v in items], hole=.62,
        marker=dict(colors=[CAT_COLOR[k] for k, _ in items], line=dict(color="#0B0A1A", width=3)),
        textinfo="percent", textposition="inside", insidetextorientation="horizontal",
        textfont=dict(size=11, color="#0B0A1A"), sort=False,
        hovertemplate="%{label}<br>" + sym + "%{value:,.2f} · %{percent}<extra></extra>"))
    fig.update_layout(uniformtext_minsize=10, uniformtext_mode="hide")
    fig.update_layout(**PLOT_LAYOUT, title=dict(text="🍩 Share of spending", font=dict(size=15)), height=340,
                      showlegend=True, legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center", font=dict(size=11)),
                      annotations=[dict(text=f"<b>{sym}{total:,.0f}</b><br><span style='font-size:11px'>per month</span>",
                                        x=.5, y=.5, showarrow=False, font=dict(size=18))])
    return fig


def gauge(score: int) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, number=dict(suffix="/100", font=dict(size=30, family="Space Grotesk")),
        gauge=dict(axis=dict(range=[0, 100], tickcolor="#555", tickwidth=1),
                   bar=dict(color="#FFFFFF", thickness=.22),
                   bgcolor="rgba(255,255,255,.04)", borderwidth=0,
                   steps=[dict(range=[0, 25], color="#FF4D8D"), dict(range=[25, 50], color="#FF9F43"),
                          dict(range=[50, 70], color="#FFD93D"), dict(range=[70, 85], color="#3DDC97"),
                          dict(range=[85, 100], color="#4D96FF")])))
    fig.update_layout(**PLOT_LAYOUT, height=210)
    fig.update_layout(margin=dict(l=34, r=34, t=24, b=0))
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Export
# ──────────────────────────────────────────────────────────────────────────────
def _latin(s: str) -> str:
    return re.sub(r"[^\x20-\x7E]", "", s).strip()


def pdf_report(r: dict, cur: str, insights: list) -> bytes | None:
    try:
        from fpdf import FPDF
    except ImportError:
        return None
    f = lambda v: f"{cur} {v:,.2f}"  # noqa: E731
    pdf = FPDF()
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    # rainbow strip
    for i, c in enumerate(RAINBOW):
        pdf.set_fill_color(*[int(c[j:j + 2], 16) for j in (1, 3, 5)])
        pdf.rect(i * 21, 0, 21, 4, "F")
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 14, "FinWise AI - Budget Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Generated {date.today():%d %b %Y}  |  v{APP_VERSION}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    def section(t):
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(120, 60, 220)
        pdf.cell(0, 9, t, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)

    def row(a, b):
        pdf.cell(95, 7, a, border="B")
        pdf.cell(0, 7, b, border="B", align="R", new_x="LMARGIN", new_y="NEXT")

    section("Overview")
    for a, b in [("Monthly income", f(r["income"])), ("Total expenses", f(r["total"])),
                 ("Remaining after expenses", f(r["remaining"])), ("Monthly savings", f(r["savings"])),
                 ("Unassigned each month", f(r["unassigned"])), ("Savings ratio", f"{r['savings_ratio']:.1f}%"),
                 ("Expense ratio", f"{r['expense_ratio']:.1f}%"), ("Debt share of income", f"{r['debt_ratio']:.1f}%"),
                 ("Emergency fund", f"{r['ef_months']:.1f} months"),
                 ("Health score", f"{r['score']}/100 ({_latin(r['score_label'])})")]:
        row(a, b)
    pdf.ln(3)
    section("Expenses")
    for k, v in sorted(r["exp"].items(), key=lambda x: -x[1]):
        if v > 0:
            row(CAT_LABEL[k], f"{f(v)}  ({v / r['total'] * 100:.0f}%)")
    pdf.ln(3)
    section("Insights")
    for _e, t, txt, _c in insights:
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(0, 6, _latin(t), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _latin(txt.replace(CURRENCIES.get(cur, ""), cur + " ")), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(0, 4, _latin(DISCLAIMER))
    return bytes(pdf.output())


# ──────────────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────
if LOGO_PATH.exists():
    try:
        st.logo(str(LOGO_PATH), size="large")
    except TypeError:
        st.logo(str(LOGO_PATH))

with st.sidebar:
    st.markdown(f"### 🤖 FinWise AI <span style='font-size:.7rem;color:#A9A4CF'>v{APP_VERSION}</span>",
                unsafe_allow_html=True)
    st.caption("Clarity · Balance · Growth")

    st.markdown("**⚡ Quick start**")
    for i, name in enumerate(PRESETS):
        st.button(name, key=f"preset_{i}", on_click=load_preset, args=(name,), width="stretch")

    st.selectbox("💱 Currency", list(CURRENCIES), key="currency")

    with st.expander("🧠 AI model settings"):
        st.selectbox("Chat model", ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"], key="model")
        st.slider("Creativity (temperature)", 0.0, 1.0, 0.2, 0.05, key="temperature")
        st.text_input("OpenAI API key", type="password", key="api_key",
                      help="Held in server memory for this session. Or set OPENAI_API_KEY in .env / Streamlit secrets.")
    with st.expander("ℹ️ About this project"):
        st.markdown("A LangChain + Streamlit prototype. **Python** calculates every ratio and the score; an "
                    "**OpenAI model** (optional) writes insights and answers chat questions. With no key, a built-in "
                    "**offline agent** generates rule-based tips.")
    st.button("🔄 Reset session", on_click=reset_all, width="stretch")

# ──────────────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────────────
cur = st.session_state["currency"]
sym = CURRENCIES[cur]
fmth = lambda v: (f"-{sym}{abs(v):,.0f}" if v < 0 else f"{sym}{v:,.0f}")  # noqa: E731  (HTML / plain text)
fmt = lambda v: fmth(v).replace("$", "\\$")  # noqa: E731  (markdown-safe: stops $…$ becoming LaTeX)
llm_on = bool(configured_api_key())
pill = ('<span class="fw-pill"><span class="fw-dot"></span>AI agent online</span>' if llm_on else
        '<span class="fw-pill off"><span class="fw-dot"></span>Offline agent</span>')
st.markdown(f"""
<div class="fw-hero">
  <img src="{logo_data_uri()}" alt="FinWise AI agent logo"/>
  <div>
    <div><span class="fw-title">FinWise AI</span>{pill}</div>
    <div class="fw-sub">✨ Your personal AI budget agent — analyse, plan, simulate and chat about your money.</div>
  </div>
</div>
<div class="fw-note" style="margin-top:8px">🎓 For education only · not financial advice · no bank connection.</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Inputs
# ──────────────────────────────────────────────────────────────────────────────
with st.container(border=True):
    t_inc, t_exp, t_goal, t_csv = st.tabs(["💵 Income & savings", "🧾 Monthly expenses", "🎯 Goal", "📥 Import CSV"])
    with t_inc:
        c1, c2, c3 = st.columns(3)
        c1.number_input(f"💰 Monthly income ({sym.strip()})", min_value=0.0, step=100.0, key="income")
        c2.number_input(f"🐷 Monthly savings ({sym.strip()})", min_value=0.0, step=50.0, key="savings")
        c3.number_input(f"🏦 Already saved ({sym.strip()})", min_value=0.0, step=100.0, key="saved",
                        help="Total savings balance today — used for emergency-fund and goal progress.")
    with t_exp:
        cols = st.columns(5)
        for i, (k, label, emo, _b) in enumerate(CATEGORIES):
            cols[i % 5].number_input(f"{emo} {label}", min_value=0.0, step=10.0, key=f"exp_{k}")
    with t_goal:
        g1, g2 = st.columns([2, 1])
        g1.selectbox("Financial goal", list(GOALS), key="goal")
        g2.number_input(f"Target amount ({sym.strip()})", min_value=0.0, step=500.0, key="goal_amt")
    with t_csv:
        st.caption("Columns: `category`, `amount`, optional `month` (e.g. 2026-09). Names are matched by keyword "
                   "(rent → Housing, netflix → Entertainment…); unknown ones go to *Other*. Multi-month files are averaged.")
        st.file_uploader("Expense CSV", type="csv", key="csv_file", on_change=import_csv, label_visibility="collapsed")
        sample = pd.DataFrame({"category": ["Rent", "Groceries", "Uber", "Netflix", "Electricity"],
                               "amount": [900, 380, 120, 15, 70], "month": ["2026-09"] * 5})
        st.download_button("⬇️ Sample CSV", sample.to_csv(index=False), "finwise_sample.csv", "text/csv")
        if msg := st.session_state.get("csv_msg"):
            getattr(st, msg[0])(msg[1])

    if st.button("🚀 Analyse my finances", type="primary", width="stretch"):
        st.session_state["analysed"] = True
        st.session_state["ai_text"] = None

expenses = {k: float(st.session_state[f"exp_{k}"]) for k in CAT_KEYS}
R = compute(float(st.session_state["income"]), float(st.session_state["savings"]),
            float(st.session_state["saved"]), expenses, float(st.session_state["goal_amt"]))

# Generated insights and chat belong to the budget and model that produced them.
fingerprint = hashlib.sha256(json.dumps(
    [R, cur, st.session_state["goal"], st.session_state.get("model"),
     st.session_state.get("temperature"), configured_api_key()], sort_keys=True,
    default=str).encode()).hexdigest()
if st.session_state.get("budget_fingerprint") != fingerprint:
    st.session_state["ai_text"] = None
    st.session_state["chat"] = []
    st.session_state["budget_fingerprint"] = fingerprint

if not st.session_state["analysed"]:
    st.info("👆 Fill in your month (or tap a ⚡ Quick start preset in the sidebar), then hit **Analyse**.")
    st.stop()
if R["income"] <= 0:
    st.warning("💵 Please enter a monthly income above zero.")
    st.stop()

INSIGHTS = rule_insights(R, fmth)

# ──────────────────────────────────────────────────────────────────────────────
# Results
# ──────────────────────────────────────────────────────────────────────────────
tabs = st.tabs(["📊 Overview", "⚖️ 50/30/20", "🔮 What-if", "🎯 Goal & growth", "🤖 AI agent", "💾 Export"])

# ── Overview ──
with tabs[0]:
    def kpi(label, value, sub, color):
        return f'<div class="kpi" style="--c:{color}"><div class="l">{label}</div><div class="v">{value}</div><div class="d">{sub}</div></div>'

    cards = [
        kpi("💰 Income", fmth(R["income"]), "per month", "#4D96FF"),
        kpi("🧾 Expenses", fmth(R["total"]), f"{R['expense_ratio']:.1f}% of income", "#FF4D8D"),
        kpi("💧 Remaining", fmth(R["remaining"]), "after expenses", "#3DE8FF"),
        kpi("🐷 Saving", fmth(R["savings"]), f"{R['savings_ratio']:.1f}% of income", "#3DDC97"),
        kpi("🧩 Unassigned", fmth(R["unassigned"]), "not budgeted yet", "#FFD93D"),
        kpi("💳 Debt share", f"{R['debt_ratio']:.1f}%", "of income", "#FF9F43"),
        kpi("🛟 Safety net", f"{R['ef_months']:.1f} mo", "of expenses covered", "#8B6CFF"),
    ]
    c1, c2 = st.columns([3, 1.15])
    with c1:
        st.markdown(f'<div class="kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
    with c2:
        with st.container(border=True):
            st.markdown(f"<div style='text-align:center;font-weight:600'>🩺 Health score · {R['score_label']}</div>",
                        unsafe_allow_html=True)
            st.plotly_chart(gauge(R["score"]), width="stretch", config={"displayModeBar": False})

    if R["total"] > 0:
        a, b = st.columns([1.2, 1])
        a.plotly_chart(bar_chart(R["exp"], sym), width="stretch", config={"displayModeBar": False})
        b.plotly_chart(donut_chart(R["exp"], R["total"], sym), width="stretch",
                       config={"displayModeBar": False})

    st.markdown("**🏅 Achievements**")
    st.markdown("".join(f'<span class="badge {"on" if ok else "off"}">{e} {t}</span>' for e, t, ok in badges(R)),
                unsafe_allow_html=True)

    with st.expander("🧮 How the score works"):
        st.markdown("Starts at **100**, then deducts points for each rule below. Pure Python — same inputs, same score.")
        if R["breakdown"]:
            st.table(pd.DataFrame(R["breakdown"], columns=["Rule triggered", "Points"]))
        else:
            st.success("No deductions — every rule passed 🎉")
        st.caption("Rules: savings ratio (<10% −25, <20% −10) · expense ratio (>90% −30, >70% −15) · debt share "
                   "(>36% −20, >15% −8) · emergency fund (<1 mo −10, <3 mo −5) · overspending −20.")

# ── 50/30/20 ──
with tabs[1]:
    st.markdown("A popular rule of thumb: **50%** needs · **30%** wants · **20%** savings.")
    rows = [("🏠 Needs", R["needs"], R["needs_pct"], 50, "#4D96FF"),
            ("🎬 Wants", R["wants"], R["wants_pct"], 30, "#D35CFF"),
            ("🐷 Savings", R["savings"], R["savings_ratio"], 20, "#3DDC97")]
    cols = st.columns(3)
    for col, (name, amt, p, target, color) in zip(cols, rows):
        ok = p <= target if name != "🐷 Savings" else p >= target
        with col.container(border=True):
            st.markdown(f"**{name}** {'✅' if ok else '⚠️'}")
            st.markdown(f"<span style='font-family:Space Grotesk,system-ui,sans-serif;font-size:1.6rem;color:{color}'>{p:.1f}%</span>"
                        f" <span style='color:#A9A4CF'>/ {target}% target</span>", unsafe_allow_html=True)
            st.markdown(f'<div class="bar-wrap"><div class="bar-fill" style="width:{min(p / target * 100, 100):.0f}%"></div></div>',
                        unsafe_allow_html=True)
            ideal = R["income"] * target / 100
            st.caption(f"{fmt(amt)} now · ideal {fmt(ideal)} · {'gap' if not ok else 'headroom'} {fmt(abs(ideal - amt))}")
    fig = go.Figure()
    for name, amt, p, target, color in rows:
        fig.add_trace(go.Bar(name=name, x=["You", "50/30/20"], y=[p, target], marker_color=color,
                             text=[f"{p:.0f}%", f"{target}%"], textposition="inside"))
    fig.update_layout(**PLOT_LAYOUT, barmode="stack", height=300, title="📐 Your split vs the rule",
                      yaxis=dict(ticksuffix="%", gridcolor="rgba(255,255,255,.06)"),
                      legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

# ── What-if ──
with tabs[2]:
    st.markdown("🔮 **Simulate cuts** — drag a slider to see how trimming a category changes your month.")
    active = [k for k in CAT_KEYS if R["exp"][k] > 0]
    cols = st.columns(3)
    for i, k in enumerate(active):
        cols[i % 3].slider(f"{CAT_EMOJI[k]} {CAT_LABEL[k]} ({fmt(R['exp'][k])})", 0, 50, step=5, key=f"cut_{k}",
                           format="%d%% cut")
    freed = sum(R["exp"][k] * st.session_state[f"cut_{k}"] / 100 for k in active)
    new_exp = {k: R["exp"][k] * (1 - st.session_state[f"cut_{k}"] / 100) for k in CAT_KEYS}
    R2 = compute(R["income"], R["savings"] + freed, R["saved"], new_exp, R["goal_amt"])
    m = st.columns(4)
    m[0].metric("✂️ Freed per month", fmth(freed))
    m[1].metric("📅 Freed per year", fmth(freed * 12))
    m[2].metric("🐷 New savings rate", f"{R2['savings_ratio']:.1f}%", f"{R2['savings_ratio'] - R['savings_ratio']:+.1f} pts")
    m[3].metric("🩺 New score", f"{R2['score']}/100", f"{R2['score'] - R['score']:+d}")
    if freed and R2["months_to_goal"] and R["months_to_goal"]:
        st.success(f"🎯 Redirecting the freed money to savings reaches your goal **{R['months_to_goal'] - R2['months_to_goal']} "
                   f"months sooner** ({R2['months_to_goal']} vs {R['months_to_goal']}).")

# ── Goal & growth ──
with tabs[3]:
    g1, g2 = st.columns([1, 1.4])
    with g1:
        with st.container(border=True):
            st.markdown(f"**{st.session_state['goal']}**")
            if R["goal_amt"] > 0:
                prog = min(R["saved"] / R["goal_amt"], 1.0)
                st.markdown(f"<span style='font-family:Space Grotesk,system-ui,sans-serif;font-size:1.5rem'>{prog * 100:.0f}%</span> "
                            f"<span style='color:#A9A4CF'>of {fmth(R['goal_amt'])}</span>", unsafe_allow_html=True)
                st.markdown(f'<div class="bar-wrap"><div class="bar-fill" style="width:{prog * 100:.0f}%"></div></div>',
                            unsafe_allow_html=True)
                if R["goal_left"] == 0:
                    st.balloons() if not st.session_state.get("_ballooned") else None
                    st.session_state["_ballooned"] = True
                    st.success("🎉 Goal reached!")
                elif R["months_to_goal"]:
                    eta = pd.Timestamp.today() + pd.DateOffset(months=R["months_to_goal"])
                    st.info(f"⏳ ~**{R['months_to_goal']} months** → around **{eta:%b %Y}**")
                else:
                    st.warning("Add monthly savings to estimate a timeline.")
                st.slider("🗓️ Want it sooner? Target months", 1, 120, key="target_months")
                need = R["goal_left"] / st.session_state["target_months"]
                st.caption(f"Save **{fmt(need)}/month** to finish in {st.session_state['target_months']} months "
                           f"({'✅ within' if need <= max(R['remaining'], 0) else '⚠️ above'} what's left after expenses).")
            else:
                st.caption("Set a target amount in the 🎯 Goal tab above.")
    with g2:
        c1, c2 = st.columns(2)
        c1.slider("📈 Assumed annual return", 0.0, 12.0, step=0.5, key="rate", format="%.1f%%")
        c2.slider("⏱️ Years", 1, 40, key="years")
        df = project_growth(R["savings"], R["saved"], st.session_state["rate"], st.session_state["years"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.year, y=df.contributed, name="💵 You put in", mode="lines",
                                 line=dict(color="#4D96FF", width=2), fill="tozeroy", fillcolor="rgba(77,150,255,.15)"))
        fig.add_trace(go.Scatter(x=df.year, y=df.balance, name="🌱 With growth", mode="lines",
                                 line=dict(color="#FF4D8D", width=3), fill="tonexty", fillcolor="rgba(255,77,141,.18)"))
        fig.update_layout(**PLOT_LAYOUT, height=300, title="🌈 Savings projection",
                          xaxis=dict(title="Years", gridcolor="rgba(255,255,255,.06)"),
                          yaxis=dict(tickprefix=sym, gridcolor="rgba(255,255,255,.06)"),
                          legend=dict(orientation="h", y=-0.2), hovermode="x unified")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        last = df.iloc[-1]
        st.caption(f"After {st.session_state['years']} years: **{fmt(last.balance)}** "
                   f"({fmt(last.balance - last.contributed)} from growth). Illustrative only — returns aren't guaranteed.")

# ── AI agent ──
with tabs[4]:
    left, right = st.columns([1, 1])
    with left:
        st.markdown("#### 💡 Insights")
        llm = get_llm()
        if llm:
            if st.session_state["ai_text"] is None:
                try:
                    msgs = [("system", SYSTEM),
                            ("human", "Here is my month as JSON: " + summary_for_llm(R, cur) +
                             "\nGive 4–6 prioritised budgeting insights and one clear next step.")]
                    with st.container(border=True):
                        st.session_state["ai_text"] = st.write_stream(stream_text(llm, msgs))
                except Exception as e:  # noqa: BLE001
                    st.error(f"AI call failed ({e.__class__.__name__}). Showing offline insights instead.")
                    st.session_state["ai_text"] = ""
            else:
                with st.container(border=True):
                    st.markdown(st.session_state["ai_text"] or "_No AI response._")
            if st.button("♻️ Regenerate"):
                st.session_state["ai_text"] = None
                st.rerun()
        if not llm or not st.session_state.get("ai_text"):
            for e, t, txt, c in INSIGHTS:
                st.markdown(f'<div class="ins" style="--c:{c}"><b>{e} {t}</b><p>{txt}</p></div>',
                            unsafe_allow_html=True)
            if not llm:
                st.caption("🔌 Offline agent (rule-based). Add an OpenAI key in the sidebar for AI-written insights.")
    with right:
        st.markdown("#### 💬 Chat with FinWise")
        box = st.container(height=380, border=True)
        if not st.session_state["chat"]:
            box.chat_message("assistant", avatar="🤖").markdown(
                "Hi! 👋 I've read your numbers. Ask me things like *“how can I save more?”* or *“when will I hit my goal?”*")
        for m_ in st.session_state["chat"]:
            box.chat_message(m_["role"], avatar="🤖" if m_["role"] == "assistant" else "🧑").markdown(m_["content"])
        chips = st.columns(3)
        quick = None
        for col, (lbl, qtext) in zip(chips, [("🐷 Save more", "How can I save more?"),
                                            ("🛟 Safety net", "Is my emergency fund OK?"),
                                            ("✂️ What to cut", "Which expenses should I cut?")]):
            if col.button(lbl, width="stretch"):
                quick = qtext
        q = st.chat_input("Ask about your budget…") or quick
        if q:
            st.session_state["chat"].append({"role": "user", "content": q})
            box.chat_message("user", avatar="🧑").markdown(q)
            with box.chat_message("assistant", avatar="🤖"):
                if llm:
                    try:
                        hist = [("system", SYSTEM + " Data: " + summary_for_llm(R, cur))]
                        hist += [(m_["role"].replace("user", "human").replace("assistant", "ai"), m_["content"])
                                 for m_ in st.session_state["chat"][-8:]]
                        ans = st.write_stream(stream_text(llm, hist))
                    except Exception as e:  # noqa: BLE001
                        ans = rule_chat(q, R, fmt) + f"\n\n_(AI unavailable: {e.__class__.__name__})_"
                        st.markdown(ans)
                else:
                    ans = rule_chat(q, R, fmt)
                    st.markdown(ans)
            st.session_state["chat"].append({"role": "assistant", "content": ans})
        if st.session_state["chat"] and st.button("🧹 Clear chat"):
            st.session_state["chat"] = []
            st.rerun()

# ── Export ──
with tabs[5]:
    st.markdown("💾 **Save your results**")
    payload = {"generated": str(date.today()), "version": APP_VERSION, "currency": cur,
               "goal": GOALS[st.session_state["goal"]],
               **{k: v for k, v in R.items() if k not in ("breakdown",)},
               "score_breakdown": R["breakdown"]}
    e1, e2, e3 = st.columns(3)
    pdf = pdf_report(R, cur, INSIGHTS)
    if pdf:
        e1.download_button("📄 PDF report", pdf, "finwise_report.pdf", "application/pdf", width="stretch")
    else:
        e1.caption("Install fpdf2 for PDF export.")
    e2.download_button("🧾 Data (JSON)", json.dumps(payload, indent=2, default=str), "finwise_data.json",
                       "application/json", width="stretch")
    exp_df = pd.DataFrame([{"category": CAT_LABEL[k], "amount": v, "share_%": round(v / R["total"] * 100, 1) if R["total"] else 0}
                           for k, v in R["exp"].items()])
    e3.download_button("📊 Expenses (CSV)", exp_df.to_csv(index=False), "finwise_expenses.csv", "text/csv",
                       width="stretch")
    st.dataframe(exp_df, hide_index=True, width="stretch",
                 column_config={"amount": st.column_config.NumberColumn(format=f"{sym}%.2f"),
                                "share_%": st.column_config.ProgressColumn("Share", format="%.1f%%", min_value=0, max_value=100)})

st.markdown(f"<div class='fw-note' style='margin-top:14px'>⚠️ {DISCLAIMER}</div>", unsafe_allow_html=True)

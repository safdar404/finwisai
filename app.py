"""FinWise AI — AI-powered personal financial analysis and smart budget assistant.

Run:  streamlit run app.py

Flow: form -> Python calculations (src/financial_calculator.py) -> LangChain LLMChain
returns structured JSON (src/chains.py) -> dashboard -> streamed recommendation.
Educational prototype only — not financial advice.
"""
from __future__ import annotations
from src import config as C

import html
import json
import time
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from src import config as C
from src.cache_manager import (CACHE_COMPARISON, active_cache_name, cache_entry_count, cache_file_size_kb,
                               clear_cache, configure_cache)
from src.chains import (build_conversation, build_message_demo, get_llm, narrative_inputs, run_financial_analysis,
                        stream_follow_up, stream_recommendations)
from src.financial_calculator import FinancialInput, analyse, build_prompt_inputs, format_money
from src.prompts import ANALYSIS_CHAT_TEMPLATE, ANALYSIS_PROMPT
from src.report import build_pdf_report
from src.utils import md_safe, md_safe_stream, parse_expense_csv, risk_style

st.set_page_config(page_title="FinWise AI — Smart Budget Assistant", page_icon="🌱", layout="wide")

# ═════════════════════════════════════════════════════════════════════════
# Styling
# ═════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Public+Sans:wght@400;500;600;700&display=swap');
:root{--ink:#14382E;--paper:#F2F6F3;--line:#D5DFD9;--muted:#5C6B64;--saffron:#E3A92B;--saffron-soft:#FBEFD2;
      --grow:#2F7D57;--caution:#B8433A}
html,body,.stApp,[class*="css"],button,input,textarea,select{font-family:"Public Sans",system-ui,sans-serif}
.stApp{background:var(--paper);color:var(--ink)}
.block-container{max-width:1180px;padding-top:2rem}
h1,h2,h3,h4{font-family:"Bricolage Grotesque","Public Sans",sans-serif!important;color:var(--ink);letter-spacing:-.01em}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--line)}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 16px}
[data-testid="stMetricValue"]{font-variant-numeric:tabular-nums;font-family:"Bricolage Grotesque",sans-serif;color:var(--ink)}
[data-testid="stForm"]{background:#fff;border:1px solid var(--line);border-radius:14px;padding:1.2rem 1.4rem}
[data-testid="stExpander"]{background:#fff;border-color:var(--line);border-radius:10px}
button[kind="primary"],button[kind="primaryFormSubmit"]{background:var(--ink)!important;border:0!important;color:#fff!important}
button[kind="primary"]:hover,button[kind="primaryFormSubmit"]:hover{background:#0d2620!important}
:focus-visible{outline:2px solid var(--saffron)!important;outline-offset:2px}

.fw-head{display:flex;align-items:flex-end;justify-content:space-between;gap:1.5rem;flex-wrap:wrap;margin-bottom:.9rem}
.fw-word{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:clamp(2.4rem,5vw,3.6rem);
         line-height:.95;color:var(--ink);letter-spacing:-.035em;margin:0}
.fw-word small{display:block;font-family:"Public Sans",sans-serif;font-weight:500;font-size:1rem;letter-spacing:0;
               color:var(--muted);margin-top:.55rem}
.fw-note{max-width:430px;font-size:.84rem;line-height:1.45;color:#5a4410;background:var(--saffron-soft);
         border-left:3px solid var(--saffron);padding:.6rem .8rem;border-radius:0 8px 8px 0}
.fw-section{display:flex;align-items:baseline;gap:.7rem;margin:2.2rem 0 .7rem;flex-wrap:wrap}
.fw-section h2{margin:0;padding:0;font-size:1.55rem}
.fw-src{font-size:.78rem;font-weight:600;padding:.15rem .6rem;border-radius:999px;border:1px solid}
.fw-src.py{color:var(--ink);border-color:var(--ink)}
.fw-src.ai{color:#7a5608;border-color:var(--saffron);background:var(--saffron-soft)}
.fw-section p{margin:0;color:var(--muted);font-size:.9rem}

.fw-score{background:#fff;border:1px solid var(--line);border-radius:14px;padding:1.3rem 1.4rem 1.1rem}
.fw-nums{display:flex;gap:2.6rem;flex-wrap:wrap;margin-bottom:1.1rem}
.fw-num b{display:block;font-family:"Bricolage Grotesque",sans-serif;font-size:3.4rem;line-height:1;font-weight:800;
          font-variant-numeric:tabular-nums;color:var(--ink)}
.fw-num b span{font-size:1.1rem;font-weight:600;color:var(--muted)}
.fw-num em{font-style:normal;font-size:.86rem;color:var(--muted)}
.fw-track{position:relative;margin:2.4rem 0 .45rem}
.fw-ruler{height:14px;display:flex;border-radius:7px;overflow:hidden}
.fw-ruler i{display:block;height:100%}
.fw-mark{position:absolute;top:-7px;height:28px;width:3px;border-radius:2px;background:var(--ink);transform:translateX(-50%)}
.fw-mark.ai{background:var(--saffron);width:4px}
.fw-mark em{position:absolute;bottom:calc(100% + 4px);left:50%;white-space:nowrap;font-style:normal;
            font-size:.76rem;font-weight:700;color:var(--ink)}
.fw-mark.ai em{color:#7a5608}
.fw-bands{display:flex;font-size:.75rem;color:var(--muted)}
.fw-bands span{display:block}
.fw-foot{margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--line);font-size:.8rem;color:var(--muted)}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>
""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════
# Session state
# ═════════════════════════════════════════════════════════════════════════
ss = st.session_state
FORM_KEYS = ["f_income", "f_savings", "f_currency", "f_goal", "f_goal_target", "f_goal_saved",
             *[f"f_exp_{k}" for k in C.EXPENSE_CATEGORIES]]
RESULT_KEYS = ["data", "metrics", "inputs", "result", "narrative", "stream_pending", "chat", "ai_error", "last_call"]


def fill_form(income: float, savings: float, expenses: dict[str, float]) -> None:
    ss.f_income, ss.f_savings = float(income), float(savings)
    for key in C.EXPENSE_CATEGORIES:
        ss[f"f_exp_{key}"] = float(expenses.get(key, 0))


if "f_income" not in ss:
    fill_form(C.DEFAULT_FORM["income"], C.DEFAULT_FORM["savings"], C.DEFAULT_FORM["expenses"])
    ss.f_currency, ss.f_goal, ss.f_goal_target, ss.f_goal_saved = "USD", C.FINANCIAL_GOALS[0], 0.0, 0.0
for key, default in {"history": [], "chat": [], "csv_months": {}, **{k: None for k in RESULT_KEYS if k != "chat"}}.items():
    ss.setdefault(key, default)


def load_selected_scenario() -> None:
    s = C.TEST_SCENARIOS[ss.scenario_pick]
    fill_form(s["income"], s["savings"], s["expenses"])


def load_csv_month() -> None:
    fill_form(ss.f_income, ss.f_savings, ss.csv_months[ss.csv_month_pick])


def reset_session() -> None:
    for key in list(ss.keys()):
        if key not in ("api_key_override",):
            del ss[key]


def friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    messages = {
        "AuthenticationError": "The OpenAI API key was rejected. Check the key in your .env file or the sidebar.",
        "RateLimitError": "OpenAI rate limit or quota reached. Check your billing/limits and try again.",
        "NotFoundError": "That model isn't available to your account. Pick another model in the sidebar.",
        "PermissionDeniedError": "Your API key doesn't have access to this model.",
        "APIConnectionError": "Couldn't reach OpenAI. Check your internet connection and try again.",
        "APITimeoutError": "OpenAI took too long to respond. Try again.",
    }
    return messages.get(name, f"The AI request failed ({name}). Your Python results are still shown below.")


# ═════════════════════════════════════════════════════════════════════════
# Sidebar
# ═════════════════════════════════════════════════════════════════════════
env_key = C.get_openai_api_key()
with st.sidebar:
    st.markdown("## 🌱 FinWise AI")
    st.caption(f"Smart budget assistant · v{C.APP_VERSION}")
    with st.expander("About this project"):
        st.markdown(
            "An educational LangChain + Streamlit prototype. Python calculates your ratios and a "
            "rule-based score; an OpenAI model, called through a LangChain **LLMChain**, turns those "
            "numbers into structured budgeting insights and a streamed recommendation.")
    st.warning(C.DISCLAIMER, icon="⚠️")

    st.markdown("#### Model settings")
    model = st.selectbox("Chat model", C.AVAILABLE_MODELS, index=C.AVAILABLE_MODELS.index(C.DEFAULT_MODEL))
    temperature = st.slider("Temperature", 0.0, 1.0, C.DEFAULT_TEMPERATURE, 0.1,
                            help="Lower = more consistent answers. Changing it creates new cache entries.")
    if env_key:
        st.caption("✓ API key loaded from `.env`")
    else:
        ss.api_key_override = st.text_input("OpenAI API key", type="password", value=ss.get("api_key_override", ""),
                                            help="Kept in this browser session only. Prefer a .env file.")
    api_key = env_key or (ss.get("api_key_override") or "").strip()

    st.markdown("#### Response cache")
    cache_mode = st.radio("Cache type", C.CACHE_OPTIONS, label_visibility="collapsed",
                          captions=["RAM · fastest · cleared on restart",
                                    "File on disk · survives restarts", "Every request calls the API"])
    configure_cache(cache_mode)
    if cache_mode != C.CACHE_NONE:
        entries = cache_entry_count(cache_mode)
        detail = f" · {cache_file_size_kb()} KB" if cache_mode == C.CACHE_SQLITE else ""
        st.caption(f"Active: `{active_cache_name()}` · {entries} stored response(s){detail}")
        if st.button("Clear this cache", width="stretch", disabled=entries == 0):
            clear_cache(cache_mode)
            st.rerun()

    st.markdown("#### Session")
    st.button("Reset session", on_click=reset_session, width="stretch",
              help="Clears the form, results, chat and history (the disk cache is kept).")

# ═════════════════════════════════════════════════════════════════════════
# Header
# ═════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="fw-head">
  <h1 class="fw-word">FinWise AI<small>{C.APP_TAGLINE}</small></h1>
  <div class="fw-note"><b>For education only.</b> Not financial advice, no guaranteed outcomes, and no connection
  to any bank account. Talk to a qualified financial professional before making money decisions.</div>
</div>""", unsafe_allow_html=True)


def marker_label_shifts(py_score: int, ai_score: int) -> tuple[str, str]:
    """CSS transforms that keep the two ruler labels from overlapping or leaving the card."""
    def shift(side: str) -> str:
        return {"left": "translateX(-4px)", "right": "translateX(calc(-100% + 4px))", "center": "translateX(-50%)"}[side]

    py_side = ai_side = "center"
    if abs(py_score - ai_score) < 14:                      # close scores: push labels apart
        py_side, ai_side = ("right", "left") if py_score <= ai_score else ("left", "right")
    for score, side_name in ((py_score, "py"), (ai_score, "ai")):
        side = py_side if side_name == "py" else ai_side
        if score < 8 and side != "left":
            side = "left"
        elif score > 92 and side != "right":
            side = "right"
        if side_name == "py":
            py_side = side
        else:
            ai_side = side
    return shift(py_side), shift(ai_side)


def section(title: str, source: str, note: str) -> None:
    tag = '<span class="fw-src py">Calculated in Python</span>' if source == "py" else \
          '<span class="fw-src ai">Generated by AI</span>' if source == "ai" else ""
    st.markdown(f'<div class="fw-section"><h2>{html.escape(title)}</h2>{tag}<p>{html.escape(note)}</p></div>',
                unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════
# Inputs
# ═════════════════════════════════════════════════════════════════════════
with st.expander("Quick fill — load a test scenario or import expenses from CSV"):
    t_scen, t_csv = st.tabs(["Test scenarios", "Import CSV"])
    with t_scen:
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        c1.selectbox("Assignment test scenario", list(C.TEST_SCENARIOS), key="scenario_pick")
        c2.button("Load scenario", width="stretch", on_click=load_selected_scenario)
    with t_csv:
        st.caption("Columns: `category`, `amount`, and optionally `month` (e.g. 2026-09). Category names are "
                   "matched to the ten form categories; unknown ones go to *Other*.")
        upload = st.file_uploader("Expense CSV", type=["csv"], label_visibility="collapsed")
        if upload is not None:
            months, warnings = parse_expense_csv(upload.getvalue())
            for w in warnings:
                st.warning(w)
            if months:
                ss.csv_months = months
                c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
                c1.selectbox("Month to load into the form", list(months), index=len(months) - 1,
                             key="csv_month_pick")
                c2.button("Use these expenses", width="stretch", on_click=load_csv_month)
                st.caption(f"Found {len(months)} month(s). With 2 or more months a comparison appears at the bottom.")

symbol = C.CURRENCIES[ss.f_currency][0].strip()
with st.form("finance_form"):
    st.markdown("### Your month")
    tab_income, tab_exp, tab_goal = st.tabs(["Income & savings", "Monthly expenses", "Goal"])
    with tab_income:
        c1, c2, c3 = st.columns(3)
        c1.number_input(f"Monthly income ({symbol})", min_value=0.0, step=100.0, key="f_income",
                        help="Take-home pay after tax.")
        c2.number_input(f"Current monthly savings ({symbol})", min_value=0.0, step=50.0, key="f_savings",
                        help="What you set aside each month.")
        c3.selectbox("Currency", list(C.CURRENCIES), key="f_currency",
                     format_func=lambda c: f"{c} — {C.CURRENCIES[c][1]}")
    with tab_exp:
        cols = st.columns(2)
        for i, (key, label) in enumerate(C.EXPENSE_CATEGORIES.items()):
            cols[i % 2].number_input(f"{label} ({symbol})", min_value=0.0, step=25.0, key=f"f_exp_{key}",
                                     help=C.EXPENSE_HELP[key])
    with tab_goal:
        c1, c2, c3 = st.columns(3)
        c1.selectbox("Financial goal", C.FINANCIAL_GOALS, key="f_goal")
        c2.number_input(f"Goal target amount ({symbol}, optional)", min_value=0.0, step=500.0, key="f_goal_target",
                        help="Leave at 0 to skip the goal tracker.")
        c3.number_input(f"Already saved toward it ({symbol})", min_value=0.0, step=100.0, key="f_goal_saved")
    submitted = st.form_submit_button("Analyse my finances", type="primary")

if submitted:
    data = FinancialInput(
        monthly_income=ss.f_income, savings=ss.f_savings, financial_goal=ss.f_goal, currency=ss.f_currency,
        expenses={k: ss[f"f_exp_{k}"] for k in C.EXPENSE_CATEGORIES},
        goal_target=ss.f_goal_target, goal_saved=ss.f_goal_saved)
    metrics = analyse(data)                           # 1) deterministic Python
    inputs = build_prompt_inputs(data, metrics)       # 2) variables for the prompts
    ss.update(data=data, metrics=metrics, inputs=inputs, result=None, narrative=None, stream_pending=False,
              chat=[], ai_error=None, last_call=None)
    if not api_key:
        ss.ai_error = "Add your OpenAI API key (in .env or the sidebar) to get AI insights. Python results are below."
    elif metrics.monthly_income <= 0:
        ss.ai_error = "Enter a monthly income above zero to get AI insights."
    else:
        before = cache_entry_count(cache_mode)
        started = time.perf_counter()
        try:
            with st.spinner("Analysing your numbers with the AI…"):
                result = run_financial_analysis(get_llm(api_key, model, temperature), inputs, data, metrics)  # 3)
            ss.result = result.__dict__
            ss.stream_pending = True
        except Exception as exc:  # noqa: BLE001 — show a clear message, keep Python results
            ss.ai_error = friendly_error(exc)
        hit = cache_mode != C.CACHE_NONE and before > 0 and cache_entry_count(cache_mode) == before
        ss.last_call = {"seconds": round(time.perf_counter() - started, 2), "cache": cache_mode, "hit": hit}
    ss.history.append({
        "Run": len(ss.history) + 1, "Time": datetime.now().strftime("%H:%M:%S"), "Currency": data.currency,
        "Income": metrics.monthly_income, "Expenses": metrics.total_expenses, "Remaining": metrics.remaining_income,
        "Savings %": metrics.savings_ratio, "Python score": metrics.preliminary_score,
        "AI score": (ss.result or {}).get("analysis", {}).get("financial_health_score"),
        "Risk": (ss.result or {}).get("analysis", {}).get("risk_level", metrics.rule_risk_level),
    })

# ═════════════════════════════════════════════════════════════════════════
# Results
# ═════════════════════════════════════════════════════════════════════════
if ss.metrics is None:
    st.info("Fill in your month above (or load a test scenario) and select **Analyse my finances**.", icon="👆")
else:
    data: FinancialInput = ss.data
    m = ss.metrics
    cur = data.currency
    money = lambda v: format_money(v, cur)  # noqa: E731

    # ── Financial overview (Python) ──
    section("Financial overview", "py", "Exact and repeatable: the same inputs always give these numbers.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Monthly income", money(m.monthly_income))
    c2.metric("Total expenses", money(m.total_expenses), f"{m.expense_ratio:.1f}% of income", delta_color="off",
              delta_arrow="off")
    c3.metric("Remaining balance", money(m.remaining_income),
              "Over budget" if m.remaining_income < 0 else "Left after expenses",
              delta_color="inverse" if m.remaining_income < 0 else "normal")
    c4.metric("Current savings", money(m.savings), f"{m.savings_ratio:.1f}% of income", delta_color="off",
              delta_arrow="off")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Savings ratio", f"{m.savings_ratio:.1f}%")
    c2.metric("Expense ratio", f"{m.expense_ratio:.1f}%")
    c3.metric("Debt share of income", f"{m.debt_ratio:.1f}%")
    c4.metric("Preliminary score", f"{m.preliminary_score}/100", m.score_band, delta_color="off", delta_arrow="off")
    for flag in m.flags:
        st.warning(flag, icon="⚠️")

    rows = [{"Category": C.EXPENSE_CATEGORIES[k], "Amount": v, "Share": m.category_shares.get(k, 0)}
            for k, v in data.expenses.items() if v > 0]
    if rows:
        df = pd.DataFrame(rows).sort_values("Amount", ascending=False)
        left, right = st.columns([3, 2])
        with left:
            st.markdown("**Where the money goes**")
            bars = alt.Chart(df).mark_bar(cornerRadiusEnd=4, color="#14382E").encode(
                x=alt.X("Amount:Q", title=f"Amount ({cur})"),
                y=alt.Y("Category:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
                tooltip=["Category", alt.Tooltip("Amount:Q", format=",.2f"), alt.Tooltip("Share:Q", format=".1f")])
            st.altair_chart(bars.properties(height=300), width="stretch")
        with right:
            st.markdown("**Share of total expenses**")
            # Green ramp ordered by amount: darkest = biggest share. Saffron/red stay reserved for risk.
            ramp = ["#14382E", "#1F5A47", "#2F7D57", "#4A9670", "#6FAE8A", "#8FC2A4", "#A9CDB7", "#C2DCCB",
                    "#D5E6DB", "#E4EFE8"]
            order = list(df["Category"])
            donut = alt.Chart(df).mark_arc(innerRadius=62, stroke="#F2F6F3", strokeWidth=2).encode(
                theta=alt.Theta("Amount:Q", sort="descending"),
                order=alt.Order("Amount:Q", sort="descending"),
                color=alt.Color("Category:N", sort=order,
                                scale=alt.Scale(domain=order, range=ramp[:len(order)]),
                                legend=alt.Legend(orient="bottom", columns=2, title=None)),
                tooltip=["Category", alt.Tooltip("Share:Q", format=".1f", title="% of expenses")])
            st.altair_chart(donut.properties(height=300), width="stretch")

    with st.expander("How the preliminary score is calculated"):
        st.markdown(
            "| Component | Full points when… | Weight | Points |\n|---|---|---|---|\n"
            f"| Savings ratio | 20% or more of income saved | 30 | {m.score_breakdown['savings']} |\n"
            f"| Money left over | 20% or more of income left after expenses | 25 | {m.score_breakdown['leftover']} |\n"
            f"| Expense ratio | 50% or less of income spent (0 at 100%) | 25 | {m.score_breakdown['expenses']} |\n"
            f"| Debt burden | repayments ≤ 10% of income (0 at 40%) | 20 | {m.score_breakdown['debt']} |\n"
            f"| **Total** | | **100** | **{m.preliminary_score}** |")
        st.caption("Bands: 80–100 strong · 60–79 generally healthy · 40–59 needs improvement · below 40 high attention.")

    if data.goal_target > 0:
        st.markdown(f"**Goal tracker — {data.financial_goal.lower()}**")
        st.progress(int(m.goal_progress or 0) / 100,
                    text=md_safe(f"{money(data.goal_saved)} of {money(data.goal_target)} saved ({m.goal_progress:.0f}%)"))
        if m.months_to_goal == 0:
            st.success("Goal reached — well done.", icon="🎯")
        elif m.months_to_goal is not None:
            st.caption(md_safe(f"At {money(m.savings)} a month, about **{m.months_to_goal:g} months** to go "
                               "(simple estimate, no interest or changes assumed)."))
        else:
            st.caption("Add a monthly saving amount to estimate how long the goal will take.")

    # ── AI analysis ──
    section("AI insights", "ai", "Written by the language model from the numbers above. Educational only.")
    if ss.ai_error:
        st.error(ss.ai_error, icon="🔌")
    result = ss.result
    if result:
        a = result["analysis"]
        if result["source"] == "fallback":
            st.warning("The AI's reply couldn't be read as valid JSON, so this section shows a rule-based summary "
                       "instead. Details are under *Under the hood*.", icon="⚠️")
        elif result["source"] == "ai-repaired":
            st.info("The first AI reply had a JSON formatting problem and was repaired automatically.", icon="🛠️")
        if ss.last_call:
            note = "served from cache — no new API call" if ss.last_call["hit"] else "fresh API call"
            st.caption(f"Structured analysis: {ss.last_call['seconds']} s · {note} · {ss.last_call['cache']}")

        ai_score, py_score = a["financial_health_score"], m.preliminary_score
        py_shift, ai_shift = marker_label_shifts(py_score, ai_score)
        bands = [(40, "#E8B4AE", "High attention"), (20, "#F3D58E", "Needs improvement"),
                 (20, "#BFDCC9", "Generally healthy"), (20, "#6FAE8A", "Strong")]
        st.markdown(f"""
<div class="fw-score">
  <div class="fw-nums">
    <div class="fw-num"><b>{ai_score}<span> /100</span></b><em>AI health score · {html.escape(
        next(lbl for lo, lbl, _ in C.SCORE_BANDS if ai_score >= lo))}</em></div>
    <div class="fw-num"><b>{py_score}<span> /100</span></b><em>Python preliminary score · {html.escape(m.score_band)}</em></div>
  </div>
  <div class="fw-track" role="img" aria-label="AI score {ai_score}, Python score {py_score} out of 100">
    <div class="fw-ruler">{''.join(f'<i style="width:{w}%;background:{c}"></i>' for w, c, _ in bands)}</div>
    <span class="fw-mark" style="left:{py_score}%"><em style="transform:{py_shift}">Python {py_score}</em></span>
    <span class="fw-mark ai" style="left:{ai_score}%"><em style="transform:{ai_shift}">AI {ai_score}</em></span>
  </div>
  <div class="fw-bands">{''.join(f'<span style="width:{w}%">{lbl}</span>' for w, _, lbl in bands)}</div>
</div>""", unsafe_allow_html=True)
        st.progress(ai_score / 100, text=f"AI financial health score: {ai_score}/100")

        icon, kind = risk_style(a["risk_level"])
        risk_text = f"**Risk level: {a['risk_level']}** {icon}"
        if a["risk_level"] != m.rule_risk_level:
            risk_text += f" — Python's rule-based check says {m.rule_risk_level}."
        getattr(st, kind)(risk_text)
        st.info(md_safe(a["financial_summary"]), icon="📝")

        # Streamed written recommendation
        st.markdown("### Your written recommendation")
        llm_ok = bool(api_key) and result["source"] != "fallback"
        if ss.stream_pending and llm_ok:
            try:
                shown = st.write_stream(md_safe_stream(stream_recommendations(
                    get_llm(api_key, model, temperature), narrative_inputs(ss.inputs, a))))
                ss.narrative = shown.replace("\\$", "$")       # keep the raw text for the PDF/JSON
            except Exception as exc:  # noqa: BLE001
                st.error(friendly_error(exc))
            ss.stream_pending = False
        elif ss.narrative:
            st.markdown(md_safe(ss.narrative))
        elif not llm_ok:
            st.caption("The written recommendation needs a working AI response.")

        t_spend, t_prio, t_budget, t_plan, t_chat, t_hood = st.tabs(
            ["Spending analysis", "Top priorities", "Budget & savings", "Next month's plan",
             "Ask a follow-up", "Under the hood"])
        with t_spend:
            if not a["spending_analysis"]:
                st.caption("No category notes were returned.")
            for i, item in enumerate(a["spending_analysis"]):
                with st.expander(item["category"] or "Category", expanded=i == 0):
                    st.markdown(f"**What we see:** {md_safe(item['observation'])}")
                    st.markdown(f"**Try this:** {md_safe(item['recommendation'])}")
        with t_prio:
            for i, p in enumerate(a["top_priorities"], 1):
                st.markdown(f"**{i}.** {md_safe(p)}")
        with t_budget:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### Budget recommendations")
                for r in a["budget_recommendations"]:
                    st.markdown(f"- {md_safe(r)}")
            with c2:
                st.markdown("#### Savings strategy")
                for r in a["savings_strategy"]:
                    st.markdown(f"- {md_safe(r)}")
        with t_plan:
            st.caption("Tick items off as you go — a simple checklist for next month.")
            for i, step in enumerate(a["next_month_action_plan"]):
                st.checkbox(md_safe(step), key=f"plan_{len(ss.history)}_{i}")
        with t_chat:
            st.caption("Ask about this analysis. The conversation is sent as System → Human → AI messages.")
            for turn in ss.chat:
                st.chat_message("user").markdown(md_safe(turn["question"]))
                st.chat_message("assistant").markdown(md_safe(turn["answer"]))
            question = st.chat_input("e.g. How could I cut my food spending by 10%?", disabled=not llm_ok)
            if question:
                st.chat_message("user").markdown(md_safe(question))
                with st.chat_message("assistant"):
                    try:
                        messages = build_conversation(ss.inputs, a, ss.chat, question)
                        shown = st.write_stream(md_safe_stream(
                            stream_follow_up(get_llm(api_key, model, temperature), messages)))
                        ss.chat.append({"question": question, "answer": shown.replace("\\$", "$")})
                    except Exception as exc:  # noqa: BLE001
                        st.error(friendly_error(exc))
        with t_hood:
            st.markdown("**Pipeline:** form → Python calculations → `PromptTemplate` (inside a "
                        "`ChatPromptTemplate`) → `LLMChain` with `ChatOpenAI` in JSON mode → safe JSON "
                        "parsing → dashboard → `llm.stream()` → `st.write_stream()`.")
            with st.expander("Messages sent to the LLMChain (ChatPromptTemplate output)"):
                for msg in ANALYSIS_CHAT_TEMPLATE.format_messages(**ss.inputs):
                    st.markdown(f"**{type(msg).__name__}**")
                    st.code(msg.content, language=None, wrap_lines=True)
            with st.expander("System / Human / AI message example"):
                for msg in build_message_demo(ss.inputs, a):
                    st.markdown(f"**{type(msg).__name__}**")
                    st.code(msg.content, language=None, wrap_lines=True)
            with st.expander("PromptTemplate variables"):
                st.json({k: ss.inputs[k] for k in ANALYSIS_PROMPT.input_variables})
            with st.expander("Raw model output and validation"):
                st.code(result["raw_output"] or "(empty)", language="json", wrap_lines=True)
                for p in result["problems"]:
                    st.caption(f"• {p}")
                if not result["problems"]:
                    st.caption("Parsed and validated without issues.")
            with st.expander("Caching explained"):
                st.dataframe(pd.DataFrame(CACHE_COMPARISON).set_index(""), width="stretch")
                st.caption("`set_llm_cache(...)` registers one global cache. LangChain checks it before each "
                           "call; repeating the same prompt returns instantly with no new API call.")

    # ── History & comparison (bonus) ──
    if len(ss.history) > 1 or len(ss.csv_months) > 1:
        section("History & comparison", "py", "Runs from this session and months from your CSV.")
    if len(ss.history) > 1:
        hist = pd.DataFrame(ss.history)
        st.dataframe(hist, hide_index=True, width="stretch",
                     column_config={"Savings %": st.column_config.NumberColumn(format="%.1f%%")})
        long = hist.melt(id_vars="Run", value_vars=["Python score", "AI score"], var_name="Score",
                         value_name="Value").dropna()
        st.altair_chart(alt.Chart(long).mark_line(point=True).encode(
            x=alt.X("Run:O"), y=alt.Y("Value:Q", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("Score:N", scale=alt.Scale(range=["#14382E", "#E3A92B"]))).properties(height=220),
            width="stretch")
    if len(ss.csv_months) > 1:
        st.markdown("**Month-to-month expenses (from CSV)**")
        rows = [{"Month": mon, "Category": C.EXPENSE_CATEGORIES[k], "Amount": v}
                for mon, cats in ss.csv_months.items() for k, v in cats.items() if v > 0]
        st.altair_chart(alt.Chart(pd.DataFrame(rows)).mark_bar().encode(
            x="Month:O", y=alt.Y("sum(Amount):Q", title="Total expenses"),
            color=alt.Color("Category:N", scale=alt.Scale(scheme="greens")),
            tooltip=["Month", "Category", alt.Tooltip("Amount:Q", format=",.2f")]).properties(height=280),
            width="stretch")
        totals = pd.DataFrame([{"Month": mon, "Total": sum(c.values())} for mon, c in ss.csv_months.items()])
        totals["Change vs previous"] = totals["Total"].diff()
        st.dataframe(totals, hide_index=True, width="stretch",
                     column_config={"Total": st.column_config.NumberColumn(format="%.2f"),
                                    "Change vs previous": st.column_config.NumberColumn(format="%+.2f")})

    # ── Downloads ──
    st.markdown("#### Save your results")
    analysis = (ss.result or {}).get("analysis")
    c1, c2 = st.columns(2)
    c1.download_button("Download PDF report", build_pdf_report(data, m, analysis, ss.narrative),
                       f"finwise-report-{datetime.now():%Y%m%d}.pdf", "application/pdf", width="stretch")
    c2.download_button("Download data (JSON)", json.dumps(
        {"inputs": data.__dict__, "python_metrics": m.to_dict(), "ai_analysis": analysis,
         "recommendation": ss.narrative, "disclaimer": C.DISCLAIMER}, indent=2, default=str),
        f"finwise-{datetime.now():%Y%m%d}.json", "application/json", width="stretch")

st.markdown(f'<div class="fw-foot">{html.escape(C.DISCLAIMER)}</div>', unsafe_allow_html=True)

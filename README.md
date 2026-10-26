# FinWise AI v2

A Streamlit budget assistant with rainbow styling, interactive charts, what-if controls, savings goals, and optional AI insights. Python computes the figures; without an API key, rule-based insights and chat remain available.

## Run locally

Use Python 3.12 and run these commands from the project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

On Linux or macOS, activate your virtual environment and run `python -m pip install -r requirements.txt` followed by `python -m streamlit run app.py`.

## Streamlit Cloud

Use `app.py` as the main file. The existing app is at https://finwis-ai.streamlit.app/.

AI is optional. Enter an OpenAI key in the sidebar, set `OPENAI_API_KEY` in the environment or `.env`, or add it in Streamlit Secrets:

```toml
OPENAI_API_KEY = "your-key-here"
```

Keep credentials out of Git. The key and budget are held in server session memory. Budget summaries and chat are sent to OpenAI when AI features are enabled; API usage may incur charges.

## Features

- Quick-start presets and editable income, savings, ten expense categories, currency, and goal.
- Deterministic balance, ratios, emergency-fund coverage, transparent rule score, and goal timing.
- Expense bars and donut chart, score gauge, 50/30/20 comparison.
- What-if expense cuts and updated savings figures.
- Goal and compound-growth projections with an adjustable assumed return.
- Offline insights and chat; optional LangChain/OpenAI streaming.
- CSV import with `category`, `amount`, and optional `month` columns. Multi-month amounts are averaged; negative amounts are treated as positive spending, so refunds should be prepared separately.
- PDF, JSON, and expense CSV downloads.
- Generated insights and chat clear when the underlying budget, currency, goal, or AI configuration changes.

## Tests

```bash
python -m pip install pytest
python -m pytest -q
```

Tests cover the v2 interface, calculation arithmetic, CSV monthly averaging, zero-return projections, mocked AI/Secrets integration, and the retained legacy modules. The files under `src/` remain for compatibility; the v2 Streamlit entry point is self-contained in `app.py`.

## Interpretation

For education only; this is not personalized financial, investment, tax, or legal advice. The health score is a rule-based heuristic, not a validated assessment. Projected returns are assumptions, not forecasts or guarantees. The app does not connect to bank accounts or move money. Currency selection changes labels, without converting amounts. Export files before resetting or ending a session.

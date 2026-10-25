"""End-to-end Streamlit test using a fake chat model (no API key or network)."""
from pathlib import Path

import pytest

import src.chains as chains
from conftest import RoutingFakeChat

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(chains, "get_llm", lambda *a, **k: RoutingFakeChat())
    return AppTest.from_file(APP, default_timeout=60)


def submit(at):
    next(b for b in at.button if b.label == "Analyse my finances").click().run()
    assert not at.exception, at.exception


def test_initial_page(app):
    app.run()
    assert not app.exception
    assert any("For education only" in m.value for m in app.markdown)


def test_full_analysis_flow(app):
    app.run()
    submit(app)
    ss = app.session_state
    assert ss["metrics"].total_expenses == 3750
    assert ss["result"]["source"] == "ai"
    assert ss["result"]["analysis"]["financial_health_score"] == 82
    assert "educational" in ss["narrative"]
    assert [m.label for m in app.metric][:4] == ["Monthly income", "Total expenses", "Remaining balance",
                                                 "Current savings"]
    # follow-up conversation
    app.chat_input[0].set_value("How can I spend less on food?").run()
    assert not app.exception and len(app.session_state["chat"]) == 1


def test_scenario_loading_and_history(app):
    app.run()
    next(s for s in app.selectbox if s.label == "Assignment test scenario").set_value("2 · Spending above income")
    next(b for b in app.button if b.label == "Load scenario").click().run()
    submit(app)
    m = app.session_state["metrics"]
    assert m.remaining_income == -600 and m.rule_risk_level == "HIGH"
    submit(app)
    assert len(app.session_state["history"]) == 2


def test_without_api_key_shows_python_results(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("src.config.get_openai_api_key", lambda: "")
    at = AppTest.from_file(APP, default_timeout=60).run()
    submit(at)
    assert at.session_state["result"] is None and "API key" in at.session_state["ai_error"]
    assert at.session_state["metrics"].preliminary_score > 0


def test_reset_session(app):
    app.run()
    submit(app)
    next(b for b in app.button if b.label == "Reset session").click().run()
    assert not app.exception and app.session_state["metrics"] is None


def test_repeat_analysis_is_served_from_cache(app):
    from src import cache_manager as cm
    from src.config import CACHE_MEMORY
    cm.clear_cache(CACHE_MEMORY)
    app.run()
    submit(app)
    assert app.session_state["last_call"]["hit"] is False
    submit(app)
    assert app.session_state["last_call"]["hit"] is True

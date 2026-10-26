"""FinWise v2 interface checks; API calls are replaced with a local fake."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'app.py')

@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr('streamlit.secrets', {})
    return AppTest.from_file(APP, default_timeout=40).run()

def checked(app):
    assert not app.exception, [e.message for e in app.exception]

def preset(app):
    next(b for b in app.button if 'Assignment test' in b.label).click().run()
    checked(app)

def test_initial_page(app):
    checked(app)
    assert not app.session_state['analysed']
    assert any('For education only' in m.value for m in app.markdown)

def test_zero_income_validation(app):
    next(b for b in app.button if 'Analyse my finances' in b.label).click().run()
    checked(app)
    assert any('above zero' in w.value for w in app.warning)

def test_preset_metrics_and_exports(app):
    preset(app)
    cards = next(m.value for m in app.markdown if 'kpi-grid' in m.value and '$8,000' in m.value)
    assert '$2,000' in cards and '$6,000' in cards
    assert len(app.get('download_button')) >= 4

def test_offline_chat_and_budget_change(app):
    preset(app)
    app.chat_input[0].set_value('How can I save more?').run()
    checked(app)
    assert len(app.session_state['chat']) == 2
    app.session_state['ai_text'] = 'Stale insight'
    app.number_input(key='income').set_value(9000.0).run()
    checked(app)
    assert app.session_state['chat'] == []
    assert app.session_state['ai_text'] is None

def test_reset(app):
    preset(app)
    next(b for b in app.button if 'Reset session' in b.label).click().run()
    checked(app)
    assert app.session_state['income'] == 0
    assert not app.session_state['analysed']

def test_streamlit_secret_and_fake_ai(app, monkeypatch):
    class FakeChat:
        def __init__(self, **kwargs):
            assert kwargs['api_key'] == 'test-secret'
        def stream(self, messages):
            yield SimpleNamespace(content='Educational budget insight from fake AI.')
    monkeypatch.setattr('streamlit.secrets', {'OPENAI_API_KEY': 'test-secret'})
    monkeypatch.setattr('langchain_openai.ChatOpenAI', FakeChat)
    preset(app)
    checked(app)
    assert 'fake AI' in app.session_state['ai_text']
    app.chat_input[0].set_value('How can I save more?').run()
    checked(app)
    assert 'fake AI' in app.session_state['chat'][-1]['content']

"""LLMChain, JSON repair/fallback, streaming, messages and caching — with a fake model."""
from langchain_core.globals import set_llm_cache
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from conftest import VALID_ANALYSIS
from src import cache_manager as cm
from src.chains import (LLMChain, build_analysis_chain, build_conversation, build_message_demo,
                        narrative_inputs, run_financial_analysis, stream_recommendations)
from src.config import CACHE_MEMORY, CACHE_NONE, CACHE_SQLITE, TEST_SCENARIOS
from src.financial_calculator import FinancialInput, analyse, build_prompt_inputs


def scenario():
    s = TEST_SCENARIOS["4 · Strong saver"]
    data = FinancialInput(s["income"], s["expenses"], s["savings"], "Build an emergency fund")
    metrics = analyse(data)
    return data, metrics, build_prompt_inputs(data, metrics)


def test_llmchain_returns_structured_json(fake_llm):
    data, metrics, inputs = scenario()
    assert isinstance(build_analysis_chain(fake_llm), LLMChain)
    result = run_financial_analysis(fake_llm, inputs, data, metrics)
    assert result.source == "ai" and result.analysis["financial_health_score"] == 82


def test_invalid_json_is_repaired(fake_llm):
    data, metrics, inputs = scenario()
    first = {"n": 0}
    original = fake_llm._reply

    def reply(messages):
        text = "\n".join(str(m.content) for m in messages)
        if "Return ONLY valid JSON" in text and first["n"] == 0:
            first["n"] += 1
            return "Here you go: {not valid json"
        return original(messages)

    object.__setattr__(fake_llm, "_reply", reply)
    result = run_financial_analysis(fake_llm, inputs, data, metrics)
    assert result.source == "ai-repaired" and result.problems


def test_fallback_when_json_never_valid(fake_llm):
    data, metrics, inputs = scenario()
    fake_llm.analysis_reply = "I cannot produce JSON."
    result = run_financial_analysis(fake_llm, inputs, data, metrics)
    assert result.source == "fallback"
    assert result.analysis["financial_health_score"] == metrics.preliminary_score


def test_streaming_yields_chunks(fake_llm):
    _, _, inputs = scenario()
    chunks = list(stream_recommendations(fake_llm, narrative_inputs(inputs, VALID_ANALYSIS)))
    assert len(chunks) > 3 and "educational" in "".join(chunks)


def test_conversation_message_types():
    _, _, inputs = scenario()
    msgs = build_conversation(inputs, VALID_ANALYSIS, [{"question": "q1", "answer": "a1"}], "q2")
    assert [type(m) for m in msgs] == [SystemMessage, HumanMessage, AIMessage, HumanMessage, AIMessage, HumanMessage]
    demo = build_message_demo(inputs, VALID_ANALYSIS)
    assert [type(m) for m in demo] == [SystemMessage, HumanMessage, AIMessage]


def test_in_memory_cache_avoids_second_call(fake_llm):
    data, metrics, inputs = scenario()
    cm.configure_cache(CACHE_MEMORY)
    cm.clear_cache(CACHE_MEMORY)
    run_financial_analysis(fake_llm, inputs, data, metrics)
    calls = fake_llm.calls
    run_financial_analysis(fake_llm, inputs, data, metrics)
    assert fake_llm.calls == calls                       # served from cache
    assert cm.cache_entry_count(CACHE_MEMORY) >= 1
    assert cm.active_cache_name() == "InMemoryCache"


def test_sqlite_cache_persists(tmp_path, fake_llm):
    data, metrics, inputs = scenario()
    db = tmp_path / "cache.db"
    cm.configure_cache(CACHE_SQLITE, db)
    run_financial_analysis(fake_llm, inputs, data, metrics)
    assert db.exists() and cm.cache_entry_count(CACHE_SQLITE, db) >= 1
    calls = fake_llm.calls
    run_financial_analysis(fake_llm, inputs, data, metrics)
    assert fake_llm.calls == calls
    cm.clear_cache(CACHE_SQLITE, db)
    assert cm.cache_entry_count(CACHE_SQLITE, db) == 0


def test_no_cache_calls_every_time(fake_llm):
    data, metrics, inputs = scenario()
    assert cm.configure_cache(CACHE_NONE) == CACHE_NONE
    run_financial_analysis(fake_llm, inputs, data, metrics)
    calls = fake_llm.calls
    run_financial_analysis(fake_llm, inputs, data, metrics)
    assert fake_llm.calls == calls + 1

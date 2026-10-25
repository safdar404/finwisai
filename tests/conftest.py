"""Shared test fixtures: a fake chat model so no API key or network is needed."""
import json
import sys
from pathlib import Path

import pytest
from langchain_core.globals import set_llm_cache
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

VALID_ANALYSIS = {
    "financial_summary": "Spending is under control with a healthy savings habit.",
    "financial_health_score": 82,
    "spending_analysis": [{"category": "Housing / rent", "observation": "Largest cost at 30% of income.",
                           "recommendation": "Keep it stable; review at lease renewal."}],
    "risk_level": "LOW",
    "top_priorities": ["Keep saving 10%", "Trim dining out", "Build an emergency fund"],
    "budget_recommendations": ["Cap entertainment at $200"],
    "savings_strategy": ["Automate a transfer on payday"],
    "next_month_action_plan": ["Track every expense for 30 days"],
}


class RoutingFakeChat(BaseChatModel):
    """Returns JSON for analysis prompts, prose otherwise. Counts calls."""
    calls: int = 0
    analysis_reply: str = json.dumps(VALID_ANALYSIS)

    @property
    def _llm_type(self) -> str:
        return "routing-fake-chat"

    def _reply(self, messages) -> str:
        text = "\n".join(str(m.content) for m in messages)
        if "Return ONLY valid JSON" in text or "Return ONLY the corrected" in text:
            return self.analysis_reply
        if "follow-up questions" in text:
            return "Cooking at home two more nights a week could free up some money. Educational only."
        return "**What's going well:** you save every month. This is educational, not financial advice."

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self._reply(messages)))])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        for word in self._reply(messages).split(" "):
            yield ChatGenerationChunk(message=AIMessageChunk(content=word + " "))


@pytest.fixture
def fake_llm():
    return RoutingFakeChat()


@pytest.fixture(autouse=True)
def no_global_cache():
    set_llm_cache(None)
    yield
    set_llm_cache(None)

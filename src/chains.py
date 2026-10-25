"""LangChain logic: ChatOpenAI, the reusable LLMChain, streaming and messages."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

try:                                    # LangChain 0.x
    from langchain.chains import LLMChain
except ImportError:                     # LangChain 1.x moved legacy chains to langchain-classic
    from langchain_classic.chains import LLMChain

from .config import DEFAULT_MODEL, DEFAULT_TEMPERATURE, REQUEST_TIMEOUT_SECONDS
from .financial_calculator import FinancialInput, FinancialMetrics
from .prompts import (ANALYSIS_CHAT_TEMPLATE, ANALYSIS_PROMPT, FOLLOW_UP_SYSTEM, NARRATIVE_CHAT_TEMPLATE,
                      REPAIR_TEMPLATE)
from .utils import build_fallback_analysis, parse_financial_json


# ── Model ───────────────────────────────────────────────────────────────
def get_llm(api_key: str, model: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE) -> ChatOpenAI:
    """Create the OpenAI chat model used by every chain."""
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=2,
    )


# ── Reusable LLMChain ───────────────────────────────────────────────────
def build_analysis_chain(llm) -> LLMChain:
    """LLMChain = ChatPromptTemplate (system + human) -> ChatOpenAI in JSON mode.

    JSON mode makes the model return a JSON object; we still validate it,
    because "valid JSON" does not guarantee "matches our schema".
    """
    json_llm = llm.bind(response_format={"type": "json_object"}) if isinstance(llm, ChatOpenAI) else llm
    return LLMChain(llm=json_llm, prompt=ANALYSIS_CHAT_TEMPLATE, output_key="analysis_json")


@dataclass
class AnalysisResult:
    analysis: dict
    raw_output: str
    source: str                      # "ai", "ai-repaired" or "fallback"
    problems: list = field(default_factory=list)


def run_financial_analysis(llm, inputs: dict, data: FinancialInput, metrics: FinancialMetrics) -> AnalysisResult:
    """Run the chain, parse its JSON safely, try one repair, else fall back to rules."""
    chain = build_analysis_chain(llm)
    raw = chain.invoke(inputs)["analysis_json"]
    analysis, problems = parse_financial_json(raw)
    if analysis is not None:
        return AnalysisResult(analysis, raw, "ai", problems)

    # One repair attempt: show the model its own output and the problems.
    try:
        repair_prompt = REPAIR_TEMPLATE.format(errors="; ".join(problems), bad_output=raw[:6000])
        repaired = llm.invoke(repair_prompt).content
        analysis, more = parse_financial_json(repaired)
        if analysis is not None:
            return AnalysisResult(analysis, repaired, "ai-repaired", problems + more)
        problems += more
    except Exception as exc:  # noqa: BLE001 — repair is best effort
        problems.append(f"Repair attempt failed: {type(exc).__name__}")

    return AnalysisResult(build_fallback_analysis(data, metrics), raw, "fallback", problems)


# ── Streaming ───────────────────────────────────────────────────────────
def narrative_inputs(inputs: dict, analysis: dict) -> dict:
    return {
        **inputs,
        "health_score": analysis.get("financial_health_score", ""),
        "risk_level": analysis.get("risk_level", ""),
        "top_priorities": "; ".join(analysis.get("top_priorities", [])) or "none listed",
    }


def stream_recommendations(llm, inputs: dict) -> Iterator[str]:
    """Yield the written recommendation chunk by chunk (for st.write_stream)."""
    messages = NARRATIVE_CHAT_TEMPLATE.format_messages(**inputs)
    for chunk in llm.stream(messages):
        if chunk.content:
            yield chunk.content


# ── Messages: System / Human / AI ───────────────────────────────────────
def analysis_as_ai_message(analysis: dict) -> AIMessage:
    """Represent the assistant's earlier reply in the conversation."""
    return AIMessage(content=json.dumps(analysis, ensure_ascii=False))


def build_conversation(inputs: dict, analysis: dict, history: list[dict], question: str) -> list[BaseMessage]:
    """System rules + the user's data (Human) + the analysis (AI) + chat turns + new question."""
    messages: list[BaseMessage] = [
        SystemMessage(content=FOLLOW_UP_SYSTEM),
        HumanMessage(content=ANALYSIS_PROMPT.format(**{k: inputs[k] for k in ANALYSIS_PROMPT.input_variables})),
        analysis_as_ai_message(analysis),
    ]
    for turn in history[-6:]:
        messages.append(HumanMessage(content=turn["question"]))
        messages.append(AIMessage(content=turn["answer"]))
    messages.append(HumanMessage(content=question))
    return messages


def stream_follow_up(llm, messages: list[BaseMessage]) -> Iterator[str]:
    for chunk in llm.stream(messages):
        if chunk.content:
            yield chunk.content


def build_message_demo(inputs: dict, analysis: dict | None) -> list[BaseMessage]:
    """A small, readable example of how a conversation is represented."""
    return [
        SystemMessage(content="You are FinWise AI, an educational budgeting assistant. "
                              "Never give investment advice or guarantee outcomes."),
        HumanMessage(content=f"My income is {inputs['monthly_income']} and I spend {inputs['total_expenses']} "
                             f"a month. My goal: {inputs['financial_goal']}. How am I doing?"),
        AIMessage(content=(analysis or {}).get("financial_summary")
                  or "(The assistant's reply appears here after you run an analysis.)"),
    ]

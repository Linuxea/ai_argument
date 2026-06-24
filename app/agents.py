"""PydanticAI agent factories (thin adapters over app.prompts).

All prompt content and assembly lives in ``app.prompts``; this module only
constructs PydanticAI ``Agent`` instances with the right model, tools, and
model settings (thinking on/off, token caps).
"""

from __future__ import annotations

from pydantic_ai import Agent

from app import prompts
from app.engine.state import DebaterDeps


def _make_model(model_name: str, base_url: str | None = None, api_key: str | None = None):
    """Build an OpenAI-compatible model for PydanticAI.

    Uses ``OpenAIChatModel`` (the post-rename class). The legacy ``OpenAIModel``
    alias was deprecated in pydantic-ai 1.7x and removed thereafter.
    """
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    provider = OpenAIProvider(base_url=base_url, api_key=api_key)
    return OpenAIChatModel(model_name, provider=provider)


def create_debater_agent(
    model_name: str,
    base_url: str | None = None,
    api_key: str | None = None,
    *,
    enable_search: bool = True,
) -> Agent[DebaterDeps, str]:
    """Create a PydanticAI debater Agent.

    ``enable_search`` controls whether the ``web_search`` tool is registered.
    Thinking/reasoning is always enabled for debaters via ``extra_body`` —
    the unified ``thinking`` field in ModelSettings is silently dropped by
    PydanticAI 1.x's capability layer, so ``extra_body`` is the only path
    that's reliably forwarded to the upstream OpenAI-compatible API.
    """
    tools = []
    if enable_search:
        from app.tools import web_search

        tools.append(web_search)

    return Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=DebaterDeps,
        output_type=str,
        instructions=lambda ctx: prompts.build_debater_system_prompt(ctx.deps),
        tools=tools,
        model_settings={"extra_body": {"thinking": {"type": "enabled"}}},
    )


def create_judge_agent(
    model_name: str, base_url: str | None = None, api_key: str | None = None
) -> Agent[None, str]:
    """Create a PydanticAI Agent configured for debate judging.

    Thinking is explicitly disabled via ``extra_body`` so judging latency is
    bounded — the judge produces an analysis, not a chain-of-thought.
    """
    return Agent(
        _make_model(model_name, base_url, api_key),
        output_type=str,
        instructions=prompts.JUDGE_SYSTEM_PROMPT,
        model_settings={"extra_body": {"thinking": {"type": "disabled"}}},
    )


def create_extractor_agent(
    model_name: str, base_url: str | None = None, api_key: str | None = None
) -> Agent[None, str]:
    """Create a lightweight agent for extracting key argument points.

    Thinking is explicitly disabled via ``extra_body``: extraction is a simple
    classification task, and leaving thinking on wastes latency and tokens.
    """
    return Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=None,
        output_type=str,
        instructions=prompts.EXTRACT_POINTS_PROMPT,
        tools=[],
        model_settings={"extra_body": {"thinking": {"type": "disabled"}}},
    )


def create_topic_refiner_agent(
    model_name: str,
    base_url: str | None = None,
    api_key: str | None = None,
) -> Agent[None, str]:
    """Create a one-shot topic-refinement agent.

    Bounded ``max_tokens`` keeps latency low; thinking is disabled (refinement
    is a paraphrase, not a reasoning task).
    """
    return Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=None,
        output_type=str,
        instructions=prompts.TOPIC_REFINE_PROMPT,
        tools=[],
        model_settings={
            "max_tokens": 512,
            "temperature": 0.7,
            "extra_body": {"thinking": {"type": "disabled"}},
        },
    )

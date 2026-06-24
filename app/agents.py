"""PydanticAI agent definitions and prompt templates for debaters/judge."""

from __future__ import annotations

from pathlib import Path

from pydantic_ai import Agent, RunContext

from app.engine.state import DebaterDeps
from app.models import Stance

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt template from prompts/<name>.md.

    Prompts live outside the Python package so their content can be iterated
    on without touching code (no ruff/coverage/test cycle). Read once at
    import; a missing file fails loudly at startup.
    """
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


# Prompt text lives in prompts/*.md — edit there, not here.
DEBATE_RULES = _load_prompt("debate_rules")
SEARCH_INSTRUCTIONS = _load_prompt("search_instructions")
SEARCH_OPENING_INSTRUCTIONS = _load_prompt("search_opening")
JUDGE_PROMPT = _load_prompt("judge")
STRATEGY_INSTRUCTIONS = _load_prompt("strategy_instructions")
MEMORY_INSTRUCTIONS = _load_prompt("memory_instructions")
EXTRACT_POINTS_PROMPT = _load_prompt("extract_points")

STANCE_INSTRUCTIONS: dict[Stance, str] = {
    "正方": (
        "You SUPPORT the topic. Argue in favor of it. "
        "Your role: champion the proposition with conviction. "
        "Strategies — (1) build positive cases with evidence and examples; "
        "(2) rebut opponents by attacking logical gaps, not the person; "
        "(3) concede small weaknesses to strengthen your credibility, then pivot back; "
        "(4) frame the debate's stakes — show why this matters. "
        "When opponents land a strong hit, absorb it calmly and reframe — never get defensive."
    ),
    "反方": (
        "You OPPOSE the topic. Argue against it. "
        "Your role: challenge every assumption and expose flaws in the proposition. "
        "Strategies — (1) scrutinise evidence quality: was the study flawed? sample too small?; "
        "(2) surface unintended consequences the other side ignores; "
        "(3) press on slippery slopes and double standards; "
        "(4) paint the counterfactual — what happens if this idea fails. "
        "When supporters dodge a tough question, pin them on it. "
        "You may briefly acknowledge strong opposing points, then immediately pivot to their weakest link."
    ),
    "中立": (
        "You take a balanced, analytical view. "
        "Your role: cut through rhetoric with structure and evidence — not to split the difference, "
        "but to identify where each side is strongest and weakest. "
        "Strategies — (1) define the evaluation criteria upfront ('by what standard?'); "
        "(2) reject false dichotomies — reframe the debate if it's framed as binary when it isn't; "
        "(3) compare both sides on the same yardstick (feasibility, cost, ethics, evidence quality); "
        "(4) point out when a debater is avoiding their own side's hardest challenge. "
        "Be calm, structured, and precise. Do not simply say 'both sides have points' — "
        "show which arguments are empirically or logically stronger and why."
    ),
}


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

    agent: Agent[DebaterDeps, str] = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
        tools=tools,
        model_settings={"extra_body": {"thinking": {"type": "enabled"}}},
    )
    return agent


def _build_debater_instructions(ctx: RunContext[DebaterDeps]) -> str:
    """Build system instructions from deps. Called fresh on every run."""
    from datetime import datetime

    debater = ctx.deps.debater
    stance = STANCE_INSTRUCTIONS.get(debater.stance, STANCE_INSTRUCTIONS["中立"])

    # Build date context with strong emphasis on current year
    now = datetime.now()
    current_year = now.year
    current_date = now.strftime("%Y-%m-%d")
    date_context = (
        f"**CURRENT DATE: {current_date}**\n"
        f"The current year is **{current_year}**. "
        f"When discussing 'recent' or 'current' events, this means {current_year}. "
        f"Any information dated before {current_year} may be outdated."
    )

    parts = [
        date_context,
        DEBATE_RULES,
    ]

    if ctx.deps.round_number >= 1:
        parts.append(STRATEGY_INSTRUCTIONS)
        parts.append(MEMORY_INSTRUCTIONS)

    parts.extend(
        [
            f"Your stance: {stance}",
            # Frame the personality as the authoritative voice/tone persona.
            # Without this framing it was just raw text appended to the prompt,
            # so the generic "be professional / back up claims / no bare
            # assertions" rules above easily overrode playful or contrarian
            # characters (e.g. a "talks nonsense" debater staying earnest).
            # Voice/tone guidance is now subordinate to the character;
            # structural rules (length, [[Name]] mentions, no headers) remain.
            (
                "## Your Character (HIGHEST priority for voice and tone)\n"
                "Below is your character description. You MUST stay fully in character "
                "at all times — it defines your personality, tone, vocabulary, humor, "
                "and rhetorical style. This OVERRIDES ALL style, tone, and "
                "argumentation guidance above whenever there is a conflict: your "
                "character's voice always wins. Structural rules still apply: keep "
                "responses 80-200 words, use [[Name]] mentions to refer to others, "
                "no headers or section labels.\n\n"
                f"{debater.personality}"
            ),
        ]
    )

    if debater.enable_search:
        if ctx.deps.round_number == 0:
            parts.append(SEARCH_OPENING_INSTRUCTIONS)
        else:
            parts.append(SEARCH_INSTRUCTIONS)

    if ctx.deps.max_rounds:
        current = ctx.deps.round_number + 1
        max_r = ctx.deps.max_rounds
        remaining = max_r - ctx.deps.round_number
        if remaining <= 1:
            parts.append(
                f"This is round {current} of {max_r} - "
                f"FINAL ROUND. Make your strongest closing argument. No holding back."
            )
        else:
            plural = "s" if remaining - 1 != 1 else ""
            parts.append(
                f"This is round {current} of {max_r}. "
                f"There {'is' if remaining - 1 == 1 else 'are'} {remaining - 1} "
                f"round{plural} remaining after this one."
            )

    return "\n\n---\n\n".join(parts)


def create_judge_agent(
    model_name: str, base_url: str | None = None, api_key: str | None = None
) -> Agent[None, str]:
    """Create a PydanticAI Agent configured for debate judging.

    Thinking is explicitly disabled via ``extra_body`` so judging latency is
    bounded — the judge produces an analysis, not a chain-of-thought.
    """
    agent: Agent[None, str] = Agent(
        _make_model(model_name, base_url, api_key),
        output_type=str,
        instructions=JUDGE_PROMPT,
        model_settings={"extra_body": {"thinking": {"type": "disabled"}}},
    )
    return agent


def create_extractor_agent(
    model_name: str, base_url: str | None = None, api_key: str | None = None
) -> Agent[None, str]:
    """Create a lightweight agent for extracting key argument points.

    Thinking is explicitly disabled via ``extra_body`` (same reason as judge):
    extraction is a simple classification task, and leaving DeepSeek V4's
    default thinking mode on wastes ~62% latency and ~86% output tokens.
    """
    agent: Agent[None, str] = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=None,
        output_type=str,
        instructions=EXTRACT_POINTS_PROMPT,
        tools=[],
        model_settings={"extra_body": {"thinking": {"type": "disabled"}}},
    )
    return agent


_TOPIC_REFINE_PROMPT = _load_prompt("topic_refine")


def create_topic_refiner_agent(
    model_name: str,
    base_url: str | None = None,
    api_key: str | None = None,
) -> Agent[None, str]:
    """Create a one-shot topic-refinement agent.

    Replaces the raw ``AsyncOpenAI`` call that ``app.routes.topic`` used to
    make, so the LLM layer is uniformly PydanticAI. Bounded ``max_tokens``
    keeps latency low; thinking is disabled (refinement is a paraphrase, not
    a reasoning task).
    """
    agent: Agent[None, str] = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=None,
        output_type=str,
        instructions=_TOPIC_REFINE_PROMPT,
        tools=[],
        model_settings={
            "max_tokens": 512,
            "temperature": 0.7,
            "extra_body": {"thinking": {"type": "disabled"}},
        },
    )
    return agent

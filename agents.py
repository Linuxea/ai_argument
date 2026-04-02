from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from models import Debater


DEBATE_RULES = """\
You are a participant in a multi-party debate. Follow these rules:

- Use the same language as the debate topic.
- Keep each response concise: 80-200 words. Prefer shorter, sharper arguments over long essays.
- Respond directly to what others said. Engage with their actual points, don't just state your position.
- When you refer to another debater by name, wrap their name in double square brackets, e.g. [[The Optimist]], [[The Skeptic]]. This makes it clear who you are responding to.
- Back up claims with reasoning or examples. No bare assertions.
- Be professional and respectful. No personal attacks.
- Don't repeat yourself. Push the discussion forward each round.
- When rebutting opponents, do not just deny their claims - use each rebuttal as a stepping stone to deepen and advance your own argument. Build upward, don't spin in circles.
- Express yourself naturally, like a real debater would. Do NOT use headers, labels, or numbered sections in your speech. No "Rebuttal:", "Argument:", "Evidence:" or similar formatting. Just speak.
"""

SEARCH_INSTRUCTIONS = """\

## Web Search Tool

You have access to a `web_search` function for real-time information.

**IMPORTANT: Check the current date shown above. When searching, prefer results from \
the current year. Include the year in your query when looking for recent data.**

### Round-Based Search Strategy

**First Round (Opening):** This is your ONLY chance to build a knowledge foundation. \
Search actively to gather current facts, recent developments, and key data about the \
debate topic. A well-informed opening argument is worth the search cost.

**Later Rounds:** Switch to strict conservation mode. Search is now a last resort — \
rely on reasoning and the information you've already gathered.

### When to Search in Later Rounds (Narrow Cases)

From round 2 onward, only call `web_search` when ALL of these conditions are met:

1. **A specific factual claim is central** to the current exchange
2. **The claim is verifiable** (not a matter of opinion or prediction)
3. **You genuinely cannot proceed** without this information
4. **The claim is surprising or controversial** (not common knowledge)

### When NOT to Search

- General argumentation and logical reasoning
- Common knowledge (even if you're slightly fuzzy on details)
- Historical events that are well-established
- Making analogies or thought experiments
- Responding to opinions, predictions, or value judgments
- "I want to double-check" or "It would be nice to have data"
- **When in doubt: argue, don't search.**

### Rate Limit (Later Rounds)

From round 2 onward, search **at most once per debate round**. If you've already \
searched this round, rely on reasoning and existing knowledge.

### How to Search

1. Briefly state what you're looking for: "Let me check the latest data on..."
2. CALL `web_search` with a targeted query — **include the current year** if recency matters
3. Use the result directly in your argument
"""

STANCE_INSTRUCTIONS = {
    "for": "You support the topic. Argue in favor of it. Focus on rebutting arguments from the opposing side - find their flaws, press hard, and do not let weak points slide.",
    "against": "You oppose the topic. Argue against it. Focus on rebutting arguments from the supporting side - find their flaws, press hard, and do not let weak points slide.",
    "neutral": "You take a balanced view. Weigh evidence from both sides.",
}

JUDGE_PROMPT = """\
You are an impartial debate judge. Analyze the debate fairly and write your assessment \
in the same language as the debate topic.

Your judgment should include:
1. A short summary of each debater's position.
2. Strengths and weaknesses for each debater.
3. The most memorable exchange or turning point.
4. Your final verdict: who made the more compelling case, and why.

Be concise. Cite actual arguments from the debate. Do not let your own opinions on the \
topic influence your judgment.\
"""


@dataclass
class DebaterDeps:
    """Dependencies injected into each debater agent run."""

    topic: str
    debater: Debater
    round_number: int
    max_rounds: int | None
    brave_api_key: str | None = None


def _make_model(model_name: str, base_url: str | None = None, api_key: str | None = None):
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.openai import OpenAIProvider

    provider = OpenAIProvider(base_url=base_url, api_key=api_key)
    return OpenAIModel(model_name, provider=provider)


def create_debater_agent(model_name: str, base_url: str | None = None, api_key: str | None = None) -> Agent[DebaterDeps, str]:
    """Create a PydanticAI Agent with web search capability."""
    from tools import web_search

    agent: Agent[DebaterDeps, str] = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
        tools=[web_search],
    )
    return agent


def create_debater_agent_no_search(model_name: str, base_url: str | None = None, api_key: str | None = None) -> Agent[DebaterDeps, str]:
    """Create a PydanticAI Agent without web search."""
    agent: Agent[DebaterDeps, str] = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
        tools=[],
    )
    return agent


def _build_debater_instructions(ctx: RunContext[DebaterDeps]) -> str:
    """Build system instructions from deps. Called fresh on every run."""
    from datetime import datetime

    debater = ctx.deps.debater
    stance = STANCE_INSTRUCTIONS.get(debater.stance, STANCE_INSTRUCTIONS["neutral"])

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
        date_context,  # Move to FIRST position for maximum visibility
        DEBATE_RULES,
        f"Your stance: {stance}",
        debater.personality,
    ]

    if debater.enable_search:
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


def create_judge_agent(model_name: str, base_url: str | None = None, api_key: str | None = None) -> Agent[None, str]:
    """Create a PydanticAI Agent configured for debate judging."""
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.openai import OpenAIProvider

    provider = OpenAIProvider(base_url=base_url, api_key=api_key)
    model = OpenAIModel(model_name, provider=provider)

    agent: Agent[None, str] = Agent(
        model,
        output_type=str,
        instructions=JUDGE_PROMPT,
    )
    return agent

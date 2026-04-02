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

## Web Search Tool

You have a `web_search` tool you can call to look up real-time information on the internet.

CRITICAL: When you decide you need facts, you MUST actually CALL the `web_search` function. \
Do NOT just write "let me search" or "I will look this up" in your text — that does nothing. \
You must invoke the tool.

**How to search:**
1. First, write one sentence explaining WHY you are searching. Example: \
"Let me check the latest data on renewable energy costs to respond to that claim."
2. Then immediately CALL `web_search` with a concise query. Do NOT hesitate.
3. After you receive the results, continue your argument using what you found.

**When to search:** When you need statistics, recent events, verifiable data, or when an opponent \
makes a factual claim you suspect is wrong. If you are unsure about a number or fact — search.
**When NOT to search:** For common knowledge, your own reasoning, or general argumentation. \
Do not search every turn — only when real data would strengthen your case.
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


def create_debater_agent(model: str) -> Agent[DebaterDeps, str]:
    """Create a PydanticAI Agent configured for debate participants."""
    from tools import web_search

    agent: Agent[DebaterDeps, str] = Agent(
        model,
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
        tools=[web_search],
    )
    return agent


def _build_debater_instructions(ctx: RunContext[DebaterDeps]) -> str:
    """Build system instructions from deps. Called fresh on every run."""
    debater = ctx.deps.debater
    stance = STANCE_INSTRUCTIONS.get(debater.stance, STANCE_INSTRUCTIONS["neutral"])

    parts = [
        DEBATE_RULES,
        f"Your stance: {stance}",
        debater.personality,
    ]

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


def create_judge_agent(model: str) -> Agent[None, str]:
    """Create a PydanticAI Agent configured for debate judging."""
    agent: Agent[None, str] = Agent(
        model,
        output_type=str,
        instructions=JUDGE_PROMPT,
    )
    return agent

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

**IMPORTANT: Check the current date shown above. When searching, include the current year \
in your query to get recent results.**

---

### Round 1: Knowledge Gathering Phase

**This is your ONLY opportunity to research. Use it wisely.**

Your first-round response must follow this structure:

1. **Search actively** — Call `web_search` multiple times to gather:
   - Latest facts and statistics about the topic
   - Recent developments (from the current year)
   - Key arguments from multiple perspectives
   - Notable examples or case studies

2. **Summarize what you learned** — After searching, briefly synthesize the key findings:
   - "Based on my research, here's what I've learned..."
   - List 2-4 important facts or data points

3. **Declare readiness** — End with a clear statement:
   - "我已准备好，可以开始辩论。" (I am ready to begin the debate.)
   - Or equivalent in the debate's language

**Do NOT make your opening argument yet.** This round is for preparation only.

---

### Round 2+: Conservation Mode

**From round 2 onward, search is disabled.** Rely entirely on:
- The knowledge you gathered in round 1
- Your reasoning and argumentation skills
- Responding to opponents' points

You may ONLY search if ALL conditions are met:
- A specific verifiable claim is central AND
- You cannot proceed without it AND
- The claim is surprising (not common knowledge)

Maximum: **one search per round** after round 1.

---

### Strategic Search Keywords

**Search with your stance in mind.** Frame queries to find evidence that supports YOUR position:

- **Supporting the topic (正方)**: Use positive/affirming keywords
  - `"benefits of X"`, `"X success stories"`, `"why X works"`, `"evidence for X"`
- **Opposing the topic (反方)**: Use critical/skeptical keywords
  - `"problems with X"`, `"X failure cases"`, `"criticism of X"`, `"risks of X"`
- **Neutral stance (中立)**: Seek balanced coverage
  - `"X pros and cons"`, `"X debate analysis"`, `"X controversy explained"`

Don't search generic terms. A well-framed query finds ammunition for YOUR argument.

---

### Search Best Practices

1. State what you're looking for, then immediately CALL `web_search`
2. Use specific queries: `"renewable energy growth 2026"` not just `"energy"`
3. After receiving results, extract key facts and move on
"""

STANCE_INSTRUCTIONS = {
    "正方": "You support the topic. Argue in favor of it. Focus on rebutting arguments from the opposing side - find their flaws, press hard, and do not let weak points slide.",
    "反方": "You oppose the topic. Argue against it. Focus on rebutting arguments from the supporting side - find their flaws, press hard, and do not let weak points slide.",
    "中立": "You take a balanced view. Weigh evidence from both sides.",
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

CONCESSION_INSTRUCTIONS = """\
## Strategic Concession

A skilled debater knows when to yield ground to gain credibility:

- When an opponent makes a valid point on a **non-core** issue, acknowledge it honestly using the markup: \
[退让]your acknowledgement here[/退让]
- After conceding, immediately **reframe** the issue or pivot to a stronger argument — never concede without \
following up with a stronger position
- Never concede your **core** position — only peripheral or secondary points
- Use concessions strategically: they build trust and make your strongest arguments more credible
- A good concession sounds like: "You raise a fair point about X, but that actually reinforces my argument \
because Y"
"""

STRATEGY_INSTRUCTIONS = """\
## Dynamic Strategy

Before responding, observe your opponent's argumentation style and adapt your counter-strategy:

- If they rely on **data and statistics** → counter with human stories, emotional narratives, and real-world impact
- If they use **emotional narratives** → counter with rigorous logic, statistics, and systematic analysis
- If they are **aggressive and combative** → stay calm, measured, and precise — composure beats aggression
- If they are **cautious and reserved** → seize the initiative, push harder, force engagement
- If they argue in **abstract terms** → ground the debate in concrete examples and practical consequences

Your adaptation should feel natural and seamless — not mechanical or formulaic. Choose ONE dominant \
counter-strategy per round.
"""

MEMORY_INSTRUCTIONS = """\
## Memory and Citation

Build narrative continuity across rounds:

- **Reference specific arguments** from earlier rounds: "In round 1, [[Name]] claimed X..."
- **Point out contradictions** if an opponent's position has shifted between rounds
- **Track unanswered questions**: if you raised a challenge and no one addressed it, raise it again explicitly
- **Build on allies' arguments**: "As [[Name]] demonstrated earlier..." — strengthen shared positions
- **Evolve your own arguments** — do not repeat previous points verbatim; deepen and extend them each round
- Use the "[Key arguments raised so far]" section provided in the conversation to track what has been said
"""

EXTRACT_POINTS_PROMPT = """\
You are an argument extraction tool. Extract 2-3 key claims from the debate argument below.

Return ONLY a JSON object with this exact format:
{"points": ["claim 1", "claim 2", "claim 3"]}

Rules:
- Each claim should be one concise sentence
- Extract the strongest, most distinct arguments
- Do not paraphrase — keep the speaker's intent
- If fewer than 2 meaningful claims exist, extract whatever is available
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


def create_debater_agent(
    model_name: str,
    base_url: str | None = None,
    api_key: str | None = None,
    *,
    enable_search: bool = True,
) -> Agent[DebaterDeps, str]:
    """Create a PydanticAI debater Agent.

    ``enable_search`` controls whether the ``web_search`` tool is registered.
    Thinking/reasoning is always enabled for debaters.
    """
    tools = []
    if enable_search:
        from tools import web_search
        tools.append(web_search)

    agent: Agent[DebaterDeps, str] = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=DebaterDeps,
        output_type=str,
        instructions=_build_debater_instructions,
        tools=tools,
        model_settings={'thinking': True},
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
        parts.append(CONCESSION_INSTRUCTIONS)
        parts.append(STRATEGY_INSTRUCTIONS)
        parts.append(MEMORY_INSTRUCTIONS)

    parts.extend([
        f"Your stance: {stance}",
        debater.personality,
    ])

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
    agent: Agent[None, str] = Agent(
        _make_model(model_name, base_url, api_key),
        output_type=str,
        instructions=JUDGE_PROMPT,
    )
    return agent


def create_extractor_agent(model_name: str, base_url: str | None = None, api_key: str | None = None) -> Agent[None, str]:
    """Create a lightweight agent for extracting key argument points."""
    agent: Agent[None, str] = Agent(
        _make_model(model_name, base_url, api_key),
        deps_type=None,
        output_type=str,
        instructions=EXTRACT_POINTS_PROMPT,
        tools=[],
    )
    return agent

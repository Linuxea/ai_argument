import pytest
from unittest.mock import MagicMock

from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    ModelMessage, PartStartEvent, PartDeltaEvent, TextPartDelta,
    ThinkingPart, ThinkingPartDelta,
)


class _MockRunStreamResult:
    """Mimics the async context manager returned by Agent.run_stream()."""

    def __init__(self, text: str):
        self._text = text
        self._messages: list[ModelMessage] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def stream_text(self, delta=True):
        if delta:
            words = self._text.split()
            for i, word in enumerate(words):
                yield word if i == 0 else " " + word
        else:
            yield self._text

    def all_messages(self) -> list[ModelMessage]:
        return self._messages


class _MockStreamEvents:
    """Mimics the async iterable returned by Agent.run_stream_events()."""

    def __init__(self, text: str, thinking: str = ""):
        self._text = text
        self._thinking = thinking
        self._messages: list[ModelMessage] = []

    async def __aiter__(self):
        # Emit thinking events first, if any
        if self._thinking:
            yield PartStartEvent(index=0, part=ThinkingPart(content=self._thinking))
            yield PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta=""))

        # Emit text deltas
        words = self._text.split()
        for i, word in enumerate(words):
            delta = word if i == 0 else " " + word
            yield PartDeltaEvent(index=0, delta=TextPartDelta(content_delta=delta))

        result = MagicMock()
        result.all_messages.return_value = self._messages
        yield AgentRunResultEvent(result=result)


class MockDebateAgent:
    """Mock that replaces both debater_agent and judge_agent for testing."""

    def __init__(self, responses: list[str] = None, thinking: list[str] = None):
        self.responses = responses or ["This is a mock response."]
        self.thinking = thinking or [""] * len(self.responses)
        self.call_count = 0
        self.last_user_prompt = None
        self.last_kwargs = None

    def run_stream_events(self, user_prompt: str, **kwargs):
        self.last_user_prompt = user_prompt
        self.last_kwargs = kwargs
        response = self.responses[self.call_count % len(self.responses)]
        thinking = self.thinking[self.call_count % len(self.thinking)]
        self.call_count += 1
        return _MockStreamEvents(response, thinking=thinking)

    def run_stream(self, user_prompt: str, **kwargs):
        """For judge agent which still uses run_stream()."""
        self.last_user_prompt = user_prompt
        self.last_kwargs = kwargs
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return _MockRunStreamResult(response)

    async def run(self, user_prompt: str, **kwargs):
        """For extractor agent which uses Agent.run()."""
        self.last_user_prompt = user_prompt
        self.last_kwargs = kwargs
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        result = MagicMock()
        result.output = response
        return result


@pytest.fixture
def mock_agent():
    return MockDebateAgent()

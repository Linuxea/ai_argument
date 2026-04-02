# tests/conftest.py
import pytest
from pydantic_ai.messages import ModelMessage


class MockStreamResult:
    """Mimics the async context manager returned by Agent.run_stream()."""

    def __init__(self, text: str):
        self._text = text
        self._messages: list[ModelMessage] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def stream_text(self, delta=True):
        words = self._text.split()
        for i, word in enumerate(words):
            if delta:
                yield word if i == 0 else " " + word
            else:
                yield " ".join(words[: i + 1])

    def all_messages(self) -> list[ModelMessage]:
        return self._messages


class MockDebateAgent:
    """Mock that replaces both debater_agent and judge_agent for testing."""

    def __init__(self, responses: list[str] = None):
        self.responses = responses or ["This is a mock response."]
        self.call_count = 0
        self.last_user_prompt = None

    def run_stream(self, user_prompt: str, **kwargs):
        self.last_user_prompt = user_prompt
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return MockStreamResult(response)


@pytest.fixture
def mock_agent():
    return MockDebateAgent()

# tests/conftest.py
import pytest


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, responses: list[str] = None):
        self.responses = responses or ["This is a mock response."]
        self.call_count = 0
        self.last_messages = None

    async def stream(self, messages: list[dict]):
        self.last_messages = messages
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        # Yield word by word to simulate streaming
        words = response.split()
        for i, word in enumerate(words):
            if i == 0:
                yield word
            else:
                yield " " + word


@pytest.fixture
def mock_llm():
    return MockLLMClient()

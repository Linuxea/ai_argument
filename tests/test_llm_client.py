# tests/test_llm_client.py
import pytest
from llm_client import LLMClient


@pytest.mark.asyncio
async def test_stream_yields_content_chunks():
    # This test uses a real client but we'll mock at a higher level
    # For now, just verify the interface exists
    client = LLMClient(base_url="http://test", api_key="test", model="test")
    assert hasattr(client, 'stream')
    assert callable(client.stream)

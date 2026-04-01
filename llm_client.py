from openai import AsyncOpenAI
from typing import AsyncGenerator


class LLMClient:
    """Async wrapper around OpenAI-compatible API with streaming support."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    async def stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Stream response from the LLM, yielding text chunks."""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            # Yield error as content so frontend can display it
            yield f"[Error: {str(e)}]"

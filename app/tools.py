"""Brave Search web_search tool with rate limiting."""
import asyncio
import time

import httpx
from pydantic_ai import RunContext

from app.agents import DebaterDeps

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
MAX_RESULTS = 5
MAX_TOTAL_CHARS = 1000


class _RateLimiter:
    """Simple rate limiter: max 1 call per min_interval seconds."""

    def __init__(self, min_interval: float = 1.0):
        self._min_interval = min_interval
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


_limiter = _RateLimiter(min_interval=1.0)


async def web_search(ctx: RunContext[DebaterDeps], query: str) -> str:
    """Search the web for factual information to support your argument.

    Use this when you need data, statistics, recent events, or verifiable
    facts. Do NOT use for opinions or general reasoning.

    Args:
        query: A concise search query (1-10 words recommended).
    """
    await _limiter.acquire()
    api_key = ctx.deps.brave_api_key
    if not api_key:
        return "Search is not configured (no API key). Proceed without search results."

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                BRAVE_ENDPOINT,
                headers={"X-Subscription-Token": api_key},
                params={"q": query, "count": MAX_RESULTS},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        return f"Search failed: {e}. Proceed without search results."

    results = []
    total_chars = 0
    for item in data.get("web", {}).get("results", []):
        snippet = f"- {item['title']}: {item.get('description', '')}"
        if total_chars + len(snippet) > MAX_TOTAL_CHARS:
            break
        results.append(snippet)
        total_chars += len(snippet)

    if not results:
        return f"No results found for '{query}'."

    return f"Search results for '{query}':\n" + "\n".join(results)

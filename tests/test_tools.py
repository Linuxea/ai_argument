from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.state import DebaterDeps
from app.models import Debater
from app.tools import web_search


def _make_ctx(api_key: str = "test-key") -> MagicMock:
    """Create a mock RunContext with DebaterDeps."""
    ctx = MagicMock()
    ctx.deps = DebaterDeps(
        topic="Test topic",
        debater=Debater(name="Test", personality="Test."),
        round_number=0,
        max_rounds=None,
        brave_api_key=api_key,
    )
    return ctx


@pytest.mark.asyncio
async def test_web_search_returns_no_key_message():
    ctx = _make_ctx(api_key=None)
    result = await web_search(ctx, "solar energy")
    assert "not configured" in result.lower()


@pytest.mark.asyncio
async def test_web_search_returns_results():
    ctx = _make_ctx(api_key="valid-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"title": "Solar Power", "description": "Solar costs dropped 89%."},
                {"title": "Wind Energy", "description": "Wind is cheaper than coal."},
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch("app.tools.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await web_search(ctx, "renewable energy cost")

    assert "renewable energy cost" in result
    assert "Solar Power" in result
    assert "Wind Energy" in result


@pytest.mark.asyncio
async def test_web_search_returns_no_results():
    ctx = _make_ctx(api_key="valid-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {"web": {"results": []}}
    mock_response.raise_for_status = MagicMock()

    with patch("app.tools.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await web_search(ctx, "obscure topic xyz")

    assert "No results found" in result


@pytest.mark.asyncio
async def test_web_search_handles_api_error():
    ctx = _make_ctx(api_key="valid-key")

    import httpx

    with patch("app.tools.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.side_effect = httpx.HTTPStatusError(
            "Rate limited",
            request=MagicMock(),
            response=MagicMock(status_code=429),
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await web_search(ctx, "anything")

    assert "error" in result.lower() or "failed" in result.lower()


@pytest.mark.asyncio
async def test_web_search_truncates_long_results():
    ctx = _make_ctx(api_key="valid-key")

    long_results = [{"title": f"Result {i}", "description": "X" * 300} for i in range(20)]

    mock_response = MagicMock()
    mock_response.json.return_value = {"web": {"results": long_results}}
    mock_response.raise_for_status = MagicMock()

    with patch("app.tools.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await web_search(ctx, "long topic")

    assert len(result) < 10000

"""Integration tests for SUI client — RPC fallback and error handling."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.chains.sui.client import SuiClient
from src.config import ChainConfig


@pytest.fixture()
def client() -> SuiClient:
    return SuiClient(
        ChainConfig(
            rpc_endpoints=(
                "https://rpc1.example.com",
                "https://rpc2.example.com",
                "https://rpc3.example.com",
            ),
            rpc_timeout=5,
        )
    )


def _mock_session(response_data: dict | None = None, error: Exception | None = None):
    """Create a mock aiohttp session that returns given data or raises error."""
    mock_response = AsyncMock()
    if error:
        mock_response.json = AsyncMock(side_effect=error)
    else:
        mock_response.json = AsyncMock(return_value=response_data or {})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    if error:
        mock_session.post = MagicMock(side_effect=error)
    else:
        mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


class TestRpcCall:
    @pytest.mark.asyncio
    async def test_successful_call(self, client: SuiClient) -> None:
        mock_session = _mock_session({"jsonrpc": "2.0", "result": {"data": "ok"}})

        with patch("src.chains.sui.client.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.chains.sui.client.aiohttp.TCPConnector"):
                result = await client.rpc_call("test_method", [])

        assert result == {"data": "ok"}

    @pytest.mark.asyncio
    async def test_rpc_error_raises(self, client: SuiClient) -> None:
        mock_session = _mock_session(
            {"jsonrpc": "2.0", "error": {"code": -32000, "message": "bad"}}
        )

        with patch("src.chains.sui.client.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.chains.sui.client.aiohttp.TCPConnector"):
                with pytest.raises(RuntimeError, match="All RPC endpoints failed"):
                    await client.rpc_call("test_method", [])

    @pytest.mark.asyncio
    async def test_fallback_on_connection_error(self, client: SuiClient) -> None:
        """When first endpoint fails, should try the next one."""
        call_count = 0

        error_response = AsyncMock()
        error_response.__aenter__ = AsyncMock(return_value=error_response)
        error_response.__aexit__ = AsyncMock(return_value=None)

        success_response = AsyncMock()
        success_response.json = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": {"ok": True}}
        )
        success_response.__aenter__ = AsyncMock(return_value=success_response)
        success_response.__aexit__ = AsyncMock(return_value=None)

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("first endpoint down")
            return success_response

        mock_session = AsyncMock()
        mock_session.post = MagicMock(side_effect=side_effect)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.chains.sui.client.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.chains.sui.client.aiohttp.TCPConnector"):
                result = await client.rpc_call("test_method", [])

        assert result == {"ok": True}
        assert client.current_rpc_index == 1

    @pytest.mark.asyncio
    async def test_all_endpoints_fail(self, client: SuiClient) -> None:
        mock_session = _mock_session(error=ConnectionError("down"))

        with patch("src.chains.sui.client.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.chains.sui.client.aiohttp.TCPConnector"):
                with pytest.raises(RuntimeError, match="All RPC endpoints failed"):
                    await client.rpc_call("test_method", [])


class TestGetOwnedObjects:
    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, client: SuiClient) -> None:
        mock_session = _mock_session(error=ConnectionError("down"))

        with patch("src.chains.sui.client.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.chains.sui.client.aiohttp.TCPConnector"):
                result = await client.get_owned_objects("0xWALLET")

        assert result == []


class TestGetObject:
    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, client: SuiClient) -> None:
        mock_session = _mock_session(error=ConnectionError("down"))

        with patch("src.chains.sui.client.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.chains.sui.client.aiohttp.TCPConnector"):
                result = await client.get_object("0xOBJECT")

        assert result == {}


class TestGetDynamicFieldObject:
    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, client: SuiClient) -> None:
        mock_session = _mock_session(error=ConnectionError("down"))

        with patch("src.chains.sui.client.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.chains.sui.client.aiohttp.TCPConnector"):
                result = await client.get_dynamic_field_object("0xP", "u64", "1")

        assert result == {}

"""Unit tests for Pyth oracle — price response parsing and error handling."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import PythConfig
from src.oracles.pyth import PythOracle


@pytest.fixture()
def oracle() -> PythOracle:
    return PythOracle(
        PythConfig(
            hermes_url="https://hermes.example.com/v2/updates/price/latest",
            feeds={"SUI": "aaa111", "BTC": "bbb222", "USDC": "ccc333"},
        )
    )


def _make_pyth_response(items: list[dict]) -> dict:
    return {"parsed": items}


class TestPythOracleFetchPrices:
    @pytest.mark.asyncio
    async def test_parses_response_correctly(self, oracle: PythOracle) -> None:
        mock_data = _make_pyth_response(
            [
                {"id": "aaa111", "price": {"price": "350000000", "expo": "-8"}},
                {"id": "bbb222", "price": {"price": "10000000000000", "expo": "-8"}},
                {"id": "ccc333", "price": {"price": "100000000", "expo": "-8"}},
            ]
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.oracles.pyth.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.oracles.pyth.aiohttp.TCPConnector"):
                prices = await oracle.fetch_prices()

        assert prices["SUI"] == pytest.approx(3.5)
        assert prices["BTC"] == pytest.approx(100000.0)
        assert prices["USDC"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_handles_http_error(self, oracle: PythOracle) -> None:
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.oracles.pyth.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.oracles.pyth.aiohttp.TCPConnector"):
                prices = await oracle.fetch_prices()

        assert prices == {}

    @pytest.mark.asyncio
    async def test_handles_network_error(self, oracle: PythOracle) -> None:
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=ConnectionError("timeout"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.oracles.pyth.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.oracles.pyth.aiohttp.TCPConnector"):
                prices = await oracle.fetch_prices()

        assert prices == {}

    @pytest.mark.asyncio
    async def test_symbol_filter(self, oracle: PythOracle) -> None:
        mock_data = _make_pyth_response(
            [
                {"id": "aaa111", "price": {"price": "350000000", "expo": "-8"}},
            ]
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.oracles.pyth.aiohttp.ClientSession", return_value=mock_session):
            with patch("src.oracles.pyth.aiohttp.TCPConnector"):
                prices = await oracle.fetch_prices(symbols=["SUI"])

        assert "SUI" in prices
        # BTC and USDC not requested
        assert "BTC" not in prices

    @pytest.mark.asyncio
    async def test_empty_feeds_returns_empty(self) -> None:
        oracle = PythOracle(PythConfig(hermes_url="https://x.com", feeds={}))
        prices = await oracle.fetch_prices()
        assert prices == {}

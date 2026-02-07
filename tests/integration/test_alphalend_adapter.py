"""Integration tests for AlphaLend adapter with mocked chain client."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.config import ProtocolConfig
from src.protocols.alphalend.adapter import AlphaLendAdapter


@pytest.fixture()
def mock_chain_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def adapter(
    mock_chain_client: AsyncMock, sample_protocol_config: ProtocolConfig
) -> AlphaLendAdapter:
    return AlphaLendAdapter(mock_chain_client, sample_protocol_config)


class TestAlphaLendAdapter:
    def test_protocol_name(self, adapter: AlphaLendAdapter) -> None:
        assert adapter.protocol_name == "alphalend"

    @pytest.mark.asyncio
    async def test_no_position_caps_returns_empty(
        self, adapter: AlphaLendAdapter, mock_chain_client: AsyncMock
    ) -> None:
        mock_chain_client.get_owned_objects.return_value = []
        positions = await adapter.fetch_positions("0xWALLET", {"SUI": 3.5})
        assert positions == []

    @pytest.mark.asyncio
    async def test_full_position_flow(
        self,
        adapter: AlphaLendAdapter,
        mock_chain_client: AsyncMock,
        sample_prices: dict[str, float],
    ) -> None:
        """Test full flow: find cap → get position → parse → return PositionData."""
        # get_owned_objects returns one PositionCap
        mock_chain_client.get_owned_objects.return_value = [
            {
                "data": {
                    "type": f"{adapter._package_id}::position::PositionCap",
                    "objectId": "0xCAP1",
                }
            }
        ]

        # get_object returns PositionCap details with position_id
        mock_chain_client.get_object.return_value = {
            "data": {
                "content": {
                    "fields": {"position_id": "0xPOS1"}
                }
            }
        }

        # get_dynamic_field_object for position data
        position_data = {
            "content": {
                "fields": {
                    "value": {
                        "fields": {
                            "collaterals": {
                                "fields": {
                                    "contents": [
                                        {
                                            "fields": {
                                                "key": "1",
                                                "value": "1000000000000",  # shares
                                            }
                                        }
                                    ]
                                }
                            },
                            "loans": [
                                {
                                    "fields": {
                                        "amount": "5000000000",  # 5000 USDC
                                        "coin_type": {
                                            "fields": {
                                                "name": "0xabc::coin::USDC"
                                            }
                                        },
                                    }
                                }
                            ],
                            "is_position_healthy": True,
                            "is_position_liquidatable": False,
                        }
                    }
                }
            }
        }

        # market info
        market_info = {
            "content": {
                "fields": {
                    "value": {
                        "fields": {
                            "coin_type": {
                                "fields": {"name": "0x2::sui::SUI"}
                            },
                            "xtoken_ratio": {
                                "fields": {"value": str(10**18)}
                            },
                        }
                    }
                }
            }
        }

        call_count = 0

        async def mock_dynamic_field(parent_id, key_type, key_value):
            nonlocal call_count
            call_count += 1
            if parent_id == adapter._positions_table_id:
                return position_data.get("content", {}).get("fields", {}).get("value", {}).get("fields", {}) and position_data
            # market info
            return market_info

        mock_chain_client.get_dynamic_field_object = AsyncMock(
            side_effect=mock_dynamic_field
        )

        positions = await adapter.fetch_positions("0xWALLET", sample_prices)

        assert len(positions) == 1
        pos = positions[0]
        assert pos.protocol_name == "alphalend"
        assert pos.collateral_value > 0
        assert pos.borrowed_value > 0
        assert pos.ltv > 0
        assert len(pos.collateral_assets) == 1
        assert len(pos.borrowed_assets) == 1
        assert pos.collateral_assets[0].symbol == "SUI"
        assert pos.borrowed_assets[0].symbol == "USDC"

    @pytest.mark.asyncio
    async def test_position_cap_without_position_id(
        self,
        adapter: AlphaLendAdapter,
        mock_chain_client: AsyncMock,
    ) -> None:
        """Position cap found but no position_id inside."""
        mock_chain_client.get_owned_objects.return_value = [
            {
                "data": {
                    "type": f"{adapter._package_id}::position::PositionCap",
                    "objectId": "0xCAP1",
                }
            }
        ]
        mock_chain_client.get_object.return_value = {
            "data": {"content": {"fields": {}}}
        }

        positions = await adapter.fetch_positions("0xWALLET", {"SUI": 3.5})
        assert positions == []

    @pytest.mark.asyncio
    async def test_empty_position_data(
        self,
        adapter: AlphaLendAdapter,
        mock_chain_client: AsyncMock,
    ) -> None:
        """Position cap found, position_id present, but position data is empty."""
        mock_chain_client.get_owned_objects.return_value = [
            {
                "data": {
                    "type": f"{adapter._package_id}::position::PositionCap",
                    "objectId": "0xCAP1",
                }
            }
        ]
        mock_chain_client.get_object.return_value = {
            "data": {"content": {"fields": {"position_id": "0xPOS1"}}}
        }
        mock_chain_client.get_dynamic_field_object.return_value = {}

        positions = await adapter.fetch_positions("0xWALLET", {"SUI": 3.5})
        assert positions == []

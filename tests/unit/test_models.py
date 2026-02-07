"""Unit tests for data models."""
from __future__ import annotations

import pytest

from src.models import AssetDetail, PositionData


class TestAssetDetail:
    def test_creation(self) -> None:
        a = AssetDetail(symbol="SUI", amount=100.0, price=3.5, usd_value=350.0)
        assert a.symbol == "SUI"
        assert a.amount == 100.0
        assert a.usd_value == 350.0

    def test_frozen(self) -> None:
        a = AssetDetail(symbol="SUI", amount=100.0, price=3.5, usd_value=350.0)
        with pytest.raises(AttributeError):
            a.amount = 200.0  # type: ignore[misc]

    def test_equality(self) -> None:
        a1 = AssetDetail(symbol="SUI", amount=100.0, price=3.5, usd_value=350.0)
        a2 = AssetDetail(symbol="SUI", amount=100.0, price=3.5, usd_value=350.0)
        assert a1 == a2


class TestPositionData:
    def test_creation(self, sample_position: PositionData) -> None:
        assert sample_position.ltv == 50.0
        assert sample_position.protocol_name == "alphalend"
        assert len(sample_position.collateral_assets) == 1
        assert len(sample_position.borrowed_assets) == 1

    def test_frozen(self, sample_position: PositionData) -> None:
        with pytest.raises(AttributeError):
            sample_position.ltv = 99.0  # type: ignore[misc]

    def test_defaults(self) -> None:
        p = PositionData(
            collateral_value=1.0,
            borrowed_value=0.5,
            ltv=50.0,
            health_factor=1.7,
            liquidation_threshold=85.0,
            asset="SUI",
            borrowed_asset="USDC",
        )
        assert p.protocol_name == ""
        assert p.wallet_label == ""
        assert p.collateral_assets == ()
        assert p.borrowed_assets == ()

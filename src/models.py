"""Data models — all frozen (immutable)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssetDetail:
    """Single asset within a position (collateral or borrow)."""

    symbol: str
    amount: float
    price: float
    usd_value: float


@dataclass(frozen=True)
class PositionData:
    """Aggregated lending position data."""

    collateral_value: float
    borrowed_value: float
    ltv: float
    health_factor: float
    liquidation_threshold: float
    asset: str
    borrowed_asset: str
    protocol_name: str = ""
    wallet_label: str = ""
    collateral_assets: tuple[AssetDetail, ...] = ()
    borrowed_assets: tuple[AssetDetail, ...] = ()

"""Data models"""
from dataclasses import dataclass


@dataclass
class PositionData:
    """Data class for lending position"""
    collateral_value: float
    borrowed_value: float
    ltv: float
    health_factor: float
    liquidation_threshold: float
    asset: str
    borrowed_asset: str

"""Protocol adapter — per-protocol position fetching."""
from typing import Protocol

from ..models import PositionData


class ProtocolAdapter(Protocol):
    """Abstract interface for fetching positions from a lending protocol."""

    @property
    def protocol_name(self) -> str: ...

    async def fetch_positions(
        self, wallet_address: str, prices: dict[str, float]
    ) -> list[PositionData]: ...

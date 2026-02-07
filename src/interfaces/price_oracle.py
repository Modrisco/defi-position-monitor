"""Price oracle protocol — price feed abstraction."""
from typing import Protocol


class PriceOracle(Protocol):
    """Abstract interface for fetching asset prices."""

    async def fetch_prices(self, symbols: list[str] | None = None) -> dict[str, float]: ...
